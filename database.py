import os

import redis.asyncio as redis
from dotenv import load_dotenv
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker

load_dotenv()

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
