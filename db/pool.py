import asyncpg
from fastapi import HTTPException

from util.config import Env

_pool: asyncpg.Pool | None = None


async def create_pool() -> asyncpg.Pool | None:
    global _pool
    if not Env.SUPABASE_DB_URL:
        return None
    _pool = await asyncpg.create_pool(Env.SUPABASE_DB_URL)
    return _pool


async def close_pool() -> None:
    global _pool
    if _pool is not None:
        await _pool.close()
        _pool = None


def get_pool() -> asyncpg.Pool:
    if _pool is None:
        raise HTTPException(
            status_code=500,
            detail="Direct database connection is not configured",
        )
    return _pool
