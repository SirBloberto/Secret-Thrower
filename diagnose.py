"""
Diagnostic script — shows exactly what is in the DB and why roles/achievements
are or are not being assigned.

Usage (from project root, with your .env in place):
    uv run python diagnose.py
"""
import asyncio
import os

from dotenv import load_dotenv

load_dotenv()

_raw = os.getenv("DATABASE_URL", "")
os.environ["DATABASE_URL"] = (
    _raw.replace("postgresql://", "postgresql+asyncpg://")
        .replace("postgres://", "postgresql+asyncpg://")
)

from sqlalchemy import select  # noqa: E402

from achievements import ACHIEVEMENTS, check_new_achievements  # noqa: E402
from database import AsyncSessionLocal  # noqa: E402
from models import GuildEloRole, User as DBUser  # noqa: E402


async def main() -> None:
    async with AsyncSessionLocal() as session:
        users = (await session.execute(select(DBUser))).scalars().all()
        elo_roles = (await session.execute(select(GuildEloRole))).scalars().all()

    # ── Users ────────────────────────────────────────────────────────────────
    print(f"{'='*60}")
    print(f"USERS  ({len(users)} found)")
    print(f"{'='*60}")

    if not users:
        print("  No users in the database. Stats are not being saved.")
        print("  Check that games are completing fully (voting phase ends).")
    else:
        for u in users:
            newly = check_new_achievements(u)
            earned_names = [a.name for a in ACHIEVEMENTS if u.achievements & a.mask]
            would_earn = [a.name for a in ACHIEVEMENTS if newly & a.mask]
            print(f"\n  {u.username} (id={u.user_id})")
            print(f"    games_played={u.games_played}  games_won={u.games_won}")
            print(f"    innocent_elo={u.innocent_elo:.2f}  thrower_elo={u.thrower_elo:.2f}")
            print(f"    votes_cast_on_thrower={u.votes_cast_on_thrower}  games_evaded={u.games_evaded}")
            print(f"    win_streak={u.win_streak}  best_win_streak={u.best_win_streak}")
            print(f"    achievements held : {earned_names or 'none'}")
            print(f"    achievements to grant now: {would_earn or 'none'}")

    # ── ELO roles ────────────────────────────────────────────────────────────
    print(f"\n{'='*60}")
    print(f"ELO ROLE MAPPINGS  ({len(elo_roles)} found)")
    print(f"{'='*60}")

    if not elo_roles:
        print("  No ELO role mappings configured.")
    else:
        by_guild: dict[int, list[GuildEloRole]] = {}
        for r in elo_roles:
            by_guild.setdefault(r.guild_id, []).append(r)

        for guild_id, rows in by_guild.items():
            print(f"\n  Guild {guild_id}")
            innocent_tiers = sorted([r for r in rows if r.elo_type == "innocent"], key=lambda r: r.min_elo, reverse=True)
            thrower_tiers  = sorted([r for r in rows if r.elo_type == "thrower"],  key=lambda r: r.min_elo, reverse=True)

            for r in innocent_tiers:
                print(f"    Innocent ELO >= {r.min_elo:.0f}  →  role_id={r.role_id}")
            for r in thrower_tiers:
                print(f"    Thrower  ELO >= {r.min_elo:.0f}  →  role_id={r.role_id}")

            print(f"\n  Who qualifies in guild {guild_id}?")
            for u in users:
                innocent_role = next((r for r in innocent_tiers if u.innocent_elo >= r.min_elo), None)
                thrower_role  = next((r for r in thrower_tiers  if u.thrower_elo  >= r.min_elo), None)
                i_str = f"role {innocent_role.role_id} (elo={u.innocent_elo:.1f} >= {innocent_role.min_elo:.0f})" if innocent_role else f"none (elo={u.innocent_elo:.1f})"
                t_str = f"role {thrower_role.role_id}  (elo={u.thrower_elo:.1f} >= {thrower_role.min_elo:.0f})"  if thrower_role  else f"none (elo={u.thrower_elo:.1f})"
                print(f"    {u.username}: innocent→{i_str}  thrower→{t_str}")

    print(f"\n{'='*60}")
    print("Run `uv run python backfill_achievements.py` to grant overdue achievements.")
    print(f"{'='*60}\n")


asyncio.run(main())
