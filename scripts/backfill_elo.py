"""
Replays all completed games in chronological order and writes correct ELO values.
Run once with: uv run python scripts/backfill_elo.py
"""

import asyncio
import os
from collections import defaultdict

import asyncpg
from dotenv import load_dotenv

load_dotenv()

ELO_K = 20
ELO_STARTING = 50.0
ELO_ABSTAIN_PENALTY = 0.05
ELO_INCORRECT_PENALTY = 0.15
ELO_K_FLEX = 0.5


def k_factor(elo: float, delta: float) -> float:
    deviation = (elo - 50.0) / 50.0
    factor = 1.0 - deviation * ELO_K_FLEX if delta >= 0 else 1.0 + deviation * ELO_K_FLEX
    return ELO_K * max(0.4, factor)


async def run() -> None:
    url = os.getenv("DATABASE_URL", "").replace("postgresql+asyncpg://", "postgresql://")
    conn = await asyncpg.connect(url)

    # Seed current ELO values (all ELO_STARTING since this is a fresh backfill)
    elos: dict[int, list[float]] = {}  # user_id -> [innocent_elo, thrower_elo]
    for row in await conn.fetch("SELECT user_id FROM users"):
        elos[row["user_id"]] = [ELO_STARTING, ELO_STARTING]

    games = await conn.fetch("SELECT game_id, winning_channel_id FROM games ORDER BY created_at ASC")

    processed = 0
    skipped = 0

    for game in games:
        game_id = game["game_id"]
        winning_channel_id = game["winning_channel_id"]

        if winning_channel_id is None:
            skipped += 1
            continue

        players = await conn.fetch(
            "SELECT user_id, channel_id, is_thrower FROM game_players WHERE game_id = $1",
            game_id,
        )
        if not players:
            skipped += 1
            continue

        # Group players into teams by channel_id
        team_map: dict[int, list[tuple[int, bool]]] = defaultdict(list)
        for p in players:
            team_map[p["channel_id"]].append((p["user_id"], p["is_thrower"]))

        team_channels = list(team_map.keys())
        if len(team_channels) != 2:
            skipped += 1
            continue

        thrower_ids = {p["user_id"] for p in players if p["is_thrower"]}

        votes = await conn.fetch("SELECT voter_id, target_id FROM votes WHERE game_id = $1", game_id)

        # Which players each voter accused
        voter_targets: dict[int, list[int]] = defaultdict(list)
        for v in votes:
            voter_targets[v["voter_id"]].append(v["target_id"])

        # Vote tallies per team to determine most-accused (for catch detection)
        team_player_ids: list[set[int]] = [{uid for uid, _ in team_map[ch]} for ch in team_channels]
        vote_tallies: list[dict[int, int]] = [{uid: 0 for uid, _ in team_map[ch]} for ch in team_channels]
        for _, targets in voter_targets.items():
            for tid in targets:
                for ti, player_ids in enumerate(team_player_ids):
                    if tid in player_ids:
                        vote_tallies[ti][tid] = vote_tallies[ti].get(tid, 0) + 1

        most_accused: list[int | None] = [
            max(tally, key=tally.get) if any(v > 0 for v in tally.values()) else None for tally in vote_tallies
        ]

        # Detection score: correct guess bonus, wrong guess penalty, abstain minor penalty.
        num_teams = len(team_channels)
        default_detection = 0.5 - ELO_ABSTAIN_PENALTY
        voter_detection: dict[int, float] = {}
        for vid, targets in voter_targets.items():
            correct = sum(1 for tid in targets if tid in thrower_ids)
            incorrect = sum(1 for tid in targets if tid not in thrower_ids)
            abstentions = num_teams - len(targets)
            voter_detection[vid] = (
                0.5
                + (correct / num_teams) * 0.5
                - (incorrect / num_teams) * ELO_INCORRECT_PENALTY
                - (abstentions / num_teams) * ELO_ABSTAIN_PENALTY
            )

        innocent_scores = [
            voter_detection.get(uid, default_detection)
            for ch in team_channels
            for uid, is_thrower in team_map[ch]
            if not is_thrower
        ]
        game_avg_detection = sum(innocent_scores) / len(innocent_scores) if innocent_scores else 0.5

        # Counts per team (no ELO snapshots — no opponent comparison)
        team_thrower_counts = [
            max(1, sum(1 for _, is_thrower in team_map[ch] if is_thrower)) for ch in team_channels
        ]
        team_innocent_counts = [
            sum(1 for _, is_thrower in team_map[ch] if not is_thrower) for ch in team_channels
        ]
        total_innocents = sum(team_innocent_counts)

        for team_idx, ch in enumerate(team_channels):
            team_won = ch == winning_channel_id

            for uid, is_thrower in team_map[ch]:
                if uid not in elos:
                    elos[uid] = [ELO_STARTING, ELO_STARTING]

                if is_thrower:
                    individually_caught = most_accused[team_idx] == uid
                    if not team_won and not individually_caught:
                        actual = 1.0   # clean throw
                    elif not team_won and individually_caught:
                        actual = 0.2   # team lost but caught
                    elif team_won and not individually_caught:
                        actual = 0.25  # failed throw, survived
                    else:
                        actual = 0.0   # worst: team won and caught
                    delta = actual - 0.5
                    kk = k_factor(elos[uid][1], delta) / team_thrower_counts[team_idx]
                    elos[uid][1] = max(0.0, min(100.0, elos[uid][1] + kk * delta))
                else:
                    win_score = 1.0 if team_won else 0.0
                    n_this = team_innocent_counts[team_idx]
                    win_weight = (total_innocents / 2) / n_this if n_this > 0 else 1.0
                    raw_detection = voter_detection.get(uid, default_detection)
                    detection_score = 0.5 + (raw_detection - game_avg_detection)
                    actual = 0.6 * win_score * win_weight + 0.4 * detection_score
                    delta = actual - 0.5
                    kk = k_factor(elos[uid][0], delta)
                    elos[uid][0] = max(0.0, min(100.0, elos[uid][0] + kk * delta))

        processed += 1

    # Write back to DB
    for uid, (innocent_elo, thrower_elo) in elos.items():
        await conn.execute(
            "UPDATE users SET innocent_elo = $1, thrower_elo = $2 WHERE user_id = $3",
            innocent_elo,
            thrower_elo,
            uid,
        )

    await conn.close()

    print(f"Done — {processed} games processed, {skipped} skipped (no winner or bad data)")
    print(f"Updated {len(elos)} user ELO records")
    for uid, (ie, te) in sorted(elos.items()):
        print(f"  user {uid}: innocent_elo={ie:.1f}  thrower_elo={te:.1f}")


asyncio.run(run())
