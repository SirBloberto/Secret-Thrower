"""
One-time script to grant achievements to existing users based on their current stats.
No DMs are sent.

Usage (from project root, with your .env in place):
    uv run python backfill_achievements.py
"""
import asyncio
import os

from dotenv import load_dotenv

load_dotenv()

# Must happen before database import so the module reads the patched URL
_raw = os.getenv("DATABASE_URL", "")
os.environ["DATABASE_URL"] = (
    _raw.replace("postgresql://", "postgresql+asyncpg://")
        .replace("postgres://", "postgresql+asyncpg://")
)

from sqlalchemy import select  # noqa: E402

from achievements import ACHIEVEMENTS, check_new_achievements  # noqa: E402
from database import AsyncSessionLocal  # noqa: E402
from models import User as DBUser  # noqa: E402


async def main() -> None:
    async with AsyncSessionLocal() as session:
        users = (await session.execute(select(DBUser))).scalars().all()

        updated = 0
        for user in users:
            newly = check_new_achievements(user)
            if newly:
                user.achievements |= newly
                names = [a.name for a in ACHIEVEMENTS if newly & a.mask]
                print(f"  {user.username}: {', '.join(names)}")
                updated += 1

        await session.commit()

    print(f"\nDone — granted achievements to {updated}/{len(users)} user(s).")


asyncio.run(main())
