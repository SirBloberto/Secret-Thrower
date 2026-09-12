from __future__ import annotations

from dataclasses import dataclass

from constants import (
    ELO_ABSTAIN_PENALTY,
    ELO_INCORRECT_PENALTY,
    ELO_K,
    ELO_K_FLEX,
    ELO_STARTING,
)

Roster = list[list[tuple[int, bool]]]
Votes = dict[int, dict[int, int]]
Ratings = dict[int, tuple[float, float]]

DEFAULT_DETECTION = 0.5 - ELO_ABSTAIN_PENALTY


@dataclass(frozen=True)
class EloUpdate:
    innocent_elo: float
    thrower_elo: float
    evaded: bool


def k_factor(elo: float, delta: float) -> float:
    """K scales with distance from the baseline: gaining is easier below it, harder above."""
    deviation = (elo - ELO_STARTING) / ELO_STARTING
    factor = 1.0 - deviation * ELO_K_FLEX if delta >= 0 else 1.0 + deviation * ELO_K_FLEX
    return ELO_K * max(0.4, factor)


def _clamp(elo: float) -> float:
    return max(0.0, min(100.0, elo))


def _vote_tallies(roster: Roster, votes: Votes) -> list[dict[int, int]]:
    tallies = [{user_id: 0 for user_id, _ in team} for team in roster]
    for team_votes in votes.values():
        for team_idx, target_id in team_votes.items():
            if target_id in tallies[team_idx]:
                tallies[team_idx][target_id] += 1
    return tallies


def _most_accused(tallies: list[dict[int, int]]) -> list[int | None]:
    return [max(t, key=t.get) if any(v > 0 for v in t.values()) else None for t in tallies]


def _detection_scores(roster: Roster, votes: Votes, thrower_ids: set[int]) -> dict[int, float]:
    num_teams = len(roster)
    scores: dict[int, float] = {}
    for voter_id, team_votes in votes.items():
        targets = list(team_votes.values())
        correct = sum(1 for target_id in targets if target_id in thrower_ids)
        incorrect = len(targets) - correct
        abstentions = num_teams - len(targets)
        scores[voter_id] = (
            0.5
            + (correct / num_teams) * 0.5
            - (incorrect / num_teams) * ELO_INCORRECT_PENALTY
            - (abstentions / num_teams) * ELO_ABSTAIN_PENALTY
        )
    return scores


def _thrower_actual(team_won: bool, caught: bool) -> float:
    if not team_won:
        return 0.2 if caught else 1.0
    return 0.0 if caught else 0.25


def compute_elo_updates(
    roster: Roster,
    votes: Votes,
    winning_team_idx: int | None,
    ratings: Ratings,
) -> dict[int, EloUpdate]:
    """Score one finished game. `roster` is per-team [(user_id, is_thrower)]; votes is
    voter_id -> {team_idx: target_id}. Pure: the same inputs always give the same output."""
    thrower_ids = {user_id for team in roster for user_id, is_thrower in team if is_thrower}
    most_accused = _most_accused(_vote_tallies(roster, votes))
    detection = _detection_scores(roster, votes, thrower_ids)

    innocent_scores = [
        detection.get(user_id, DEFAULT_DETECTION) for team in roster for user_id, is_thrower in team if not is_thrower
    ]
    avg_detection = sum(innocent_scores) / len(innocent_scores) if innocent_scores else 0.5

    thrower_counts = [max(1, sum(1 for _, is_thrower in team if is_thrower)) for team in roster]
    innocent_counts = [sum(1 for _, is_thrower in team if not is_thrower) for team in roster]
    total_innocents = sum(innocent_counts)

    updates: dict[int, EloUpdate] = {}
    for team_idx, team in enumerate(roster):
        team_won = team_idx == winning_team_idx

        for user_id, is_thrower in team:
            innocent_elo, thrower_elo = ratings.get(user_id, (float(ELO_STARTING), float(ELO_STARTING)))
            evaded = False

            if is_thrower:
                caught = most_accused[team_idx] == user_id
                evaded = not team_won and not caught
                delta = _thrower_actual(team_won, caught) - 0.5
                k = k_factor(thrower_elo, delta) / thrower_counts[team_idx]
                thrower_elo = _clamp(thrower_elo + k * delta)
            else:
                count = innocent_counts[team_idx]
                win_weight = (total_innocents / 2) / count if count > 0 else 1.0
                win_score = 1.0 if team_won else 0.0
                detection_score = 0.5 + (detection.get(user_id, DEFAULT_DETECTION) - avg_detection)
                delta = 0.6 * win_score * win_weight + 0.4 * detection_score - 0.5
                k = k_factor(innocent_elo, delta)
                innocent_elo = _clamp(innocent_elo + k * delta)

            updates[user_id] = EloUpdate(innocent_elo, thrower_elo, evaded)

    return updates
