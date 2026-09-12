"""Replays every completed game through the shared ELO logic and rewrites all ratings.

Run with: uv run python -m scripts.backfill_elo
"""

import asyncio
from collections import defaultdict

from sqlalchemy import select

from constants import ELO_STARTING
from database import AsyncSessionLocal
from elo import compute_elo_updates
from models import Game as DBGame
from models import Player as DBPlayer
from models import User as DBUser
from models import Vote as DBVote


async def run() -> None:
    async with AsyncSessionLocal() as session:
        users = (await session.execute(select(DBUser))).scalars().all()
        ratings = {u.user_id: (float(ELO_STARTING), float(ELO_STARTING)) for u in users}
        evaded: dict[int, int] = defaultdict(int)

        games = (await session.execute(select(DBGame).order_by(DBGame.created_at))).scalars().all()
        processed = skipped = 0

        for game in games:
            players = (await session.execute(select(DBPlayer).where(DBPlayer.game_id == game.game_id))).scalars().all()
            channels = list(dict.fromkeys(p.channel_id for p in players))
            if game.winning_channel_id not in channels or len(channels) != 2:
                skipped += 1
                continue

            roster = [[(p.user_id, p.is_thrower) for p in players if p.channel_id == channel] for channel in channels]
            team_of = {user_id: idx for idx, team in enumerate(roster) for user_id, _ in team}

            votes: dict[int, dict[int, int]] = {}
            rows = (await session.execute(select(DBVote).where(DBVote.game_id == game.game_id))).scalars().all()
            for vote in rows:
                if vote.target_id in team_of:
                    votes.setdefault(vote.voter_id, {}).setdefault(team_of[vote.target_id], vote.target_id)

            updates = compute_elo_updates(roster, votes, channels.index(game.winning_channel_id), ratings)
            for user_id, update in updates.items():
                ratings[user_id] = (update.innocent_elo, update.thrower_elo)
                if update.evaded:
                    evaded[user_id] += 1
            processed += 1

        for db_user in users:
            db_user.innocent_elo, db_user.thrower_elo = ratings[db_user.user_id]
            db_user.games_evaded = evaded[db_user.user_id]

        await session.commit()

    print(f"Replayed {processed} game(s), skipped {skipped}.")
    for user_id, (innocent, thrower) in sorted(ratings.items()):
        print(f"  {user_id}: innocent={innocent:.1f} thrower={thrower:.1f} evaded={evaded[user_id]}")


if __name__ == "__main__":
    asyncio.run(run())
