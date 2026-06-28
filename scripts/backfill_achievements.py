"""
Backfill achievement bitmasks for all existing users based on their current stats.
Run with: uv run python scripts/backfill_achievements.py
"""

import asyncio
import os

import asyncpg
from dotenv import load_dotenv

load_dotenv()

# Must mirror achievements.py exactly
ACHIEVEMENTS = [
    (0, "First Blood",  lambda u: u["games_played"] >= 1),
    (1, "Sharp Eye",    lambda u: u["votes_cast_on_thrower"] >= 10),
    (2, "Eagle Eye",    lambda u: u["votes_cast_on_thrower"] >= 50),
    (3, "Mastermind",   lambda u: u["games_evaded"] >= 10),
    (4, "Ghost",        lambda u: u["games_evaded"] >= 25),
    (5, "Team Player",  lambda u: max(0, u["games_won"] - (u["games_as_thrower"] - u["games_thrown"])) >= 25),
    (6, "Veteran",      lambda u: u["games_played"] >= 100),
    (7, "Elite",        lambda u: u["innocent_elo"] >= 75.0),
]


def compute_mask(user: dict) -> int:
    mask = 0
    for bit, _, condition in ACHIEVEMENTS:
        if condition(user):
            mask |= (1 << bit)
    return mask


async def run() -> None:
    url = os.getenv("DATABASE_URL", "").replace("postgresql+asyncpg://", "postgresql://")
    conn = await asyncpg.connect(url)

    users = await conn.fetch("""
        SELECT user_id, username, games_played, games_won, games_as_thrower,
               games_thrown, games_evaded, votes_cast_on_thrower, innocent_elo, achievements
        FROM users
    """)

    updates: list[tuple[int, int]] = []
    name_width = max((len(u["username"]) for u in users), default=8)

    print(f"{'User':<{name_width}}  {'Old':>6}  {'New':>6}  Newly unlocked")
    print("-" * (name_width + 40))

    for user in users:
        correct = compute_mask(dict(user))
        current = user["achievements"]
        if correct == current:
            continue

        newly = correct & ~current
        new_names = [name for bit, name, _ in ACHIEVEMENTS if newly & (1 << bit)]
        print(f"{user['username']:<{name_width}}  {current:>6}  {correct:>6}  {', '.join(new_names)}")
        updates.append((correct, user["user_id"]))

    if not updates:
        print("All users already have correct achievements — nothing to update.")
        await conn.close()
        return

    await conn.executemany("UPDATE users SET achievements = $1 WHERE user_id = $2", updates)
    await conn.close()
    print(f"\nUpdated {len(updates)} user(s).")


asyncio.run(run())
