import json
import os

import redis.asyncio as redis
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker

from models import GuildSettings as DBGuildSettings
from models import Subscription, SubscriptionType

_raw_url = os.getenv("DATABASE_URL", "")
DATABASE_URL = _raw_url.replace("postgresql://", "postgresql+asyncpg://").replace(
    "postgres://", "postgresql+asyncpg://"
)

REDIS_HOST = os.getenv("REDIS_HOST", "redis")
REDIS_PORT = int(os.getenv("REDIS_PORT", 6379))

engine = create_async_engine(DATABASE_URL, echo=False)

AsyncSessionLocal: sessionmaker[AsyncSession] = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

redis_client: redis.Redis = redis.Redis(host=REDIS_HOST, port=REDIS_PORT, decode_responses=True)


async def save_game_state(game_id: int, json_str: str) -> None:
    await redis_client.set(f"game:{game_id}", json_str, ex=7200)


async def load_game_state(game_id: int) -> str | None:
    return await redis_client.get(f"game:{game_id}")


async def delete_game_state(game_id: int) -> None:
    await redis_client.delete(f"game:{game_id}")



async def save_guild_settings(guild_id: int, settings: dict) -> None:
    """Write settings to Redis (fast) and DB (durable)."""
    await redis_client.set(f"settings:{guild_id}", json.dumps(settings))
    async with AsyncSessionLocal() as session:
        row = await session.get(DBGuildSettings, guild_id)
        if row:
            row.voting_timer = settings.get("voting_timer", 60)
            row.thrower_info = settings.get("thrower_info", False)
        else:
            session.add(DBGuildSettings(
                guild_id=guild_id,
                voting_timer=settings.get("voting_timer", 60),
                thrower_info=settings.get("thrower_info", False),
            ))
        await session.commit()


async def is_premium(guild_id: int) -> bool:
    """Return True if the guild has an active premium subscription."""
    async with AsyncSessionLocal() as session:
        result = await session.execute(
            select(Subscription).where(
                Subscription.target_id == guild_id,
                Subscription.type == SubscriptionType.GUILD,
                Subscription.is_active == True,  # noqa: E712
            )
        )
        return result.scalar_one_or_none() is not None


async def load_guild_settings(guild_id: int) -> dict | None:
    """Redis-first read; falls back to DB and repopulates Redis on a cache miss."""
    data = await redis_client.get(f"settings:{guild_id}")
    if data:
        return json.loads(data)

    async with AsyncSessionLocal() as session:
        row = await session.get(DBGuildSettings, guild_id)
        if row:
            settings = {"voting_timer": row.voting_timer, "thrower_info": row.thrower_info}
            await redis_client.set(f"settings:{guild_id}", json.dumps(settings))
            return settings

    return None
