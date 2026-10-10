"""Thin asyncpg wrapper. Works with any Postgres (Tiger Data included)."""
import json

from app import config

_pool = None


async def _init_connection(conn):
    # Let jsonb columns accept and return plain Python dicts/lists
    await conn.set_type_codec(
        "jsonb", encoder=json.dumps, decoder=json.loads, schema="pg_catalog"
    )


async def get_pool():
    global _pool
    if _pool is None:
        import asyncpg  # lazy so the app runs without a database
        _pool = await asyncpg.create_pool(config.DATABASE_URL, init=_init_connection)
    return _pool


async def fetch(query: str, *args):
    pool = await get_pool()
    return await pool.fetch(query, *args)


async def fetchrow(query: str, *args):
    pool = await get_pool()
    return await pool.fetchrow(query, *args)


async def execute(query: str, *args):
    pool = await get_pool()
    return await pool.execute(query, *args)
