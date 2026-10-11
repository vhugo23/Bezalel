"""Thin asyncpg wrapper. Works with any Postgres (Tiger Data included).
With DATABASE_SCHEMA set, every connection searches that schema first, then public."""
import json
import re

from app import config

_pool = None
SCHEMA_NAME = re.compile(r"^[a-z_][a-z0-9_]{0,62}$")


def search_path() -> str | None:
    """The search_path for DATABASE_SCHEMA, or None to keep the database default (public)."""
    schema = config.DATABASE_SCHEMA
    if not schema:
        return None
    if not SCHEMA_NAME.match(schema):
        raise ValueError(f"DATABASE_SCHEMA '{schema}' must be lowercase letters, digits and _ only")
    return f'"{schema}", public'


async def _init_connection(conn):
    # Let jsonb columns accept and return plain Python dicts/lists
    await conn.set_type_codec(
        "jsonb", encoder=json.dumps, decoder=json.loads, schema="pg_catalog"
    )


async def get_pool():
    global _pool
    if _pool is None:
        import asyncpg  # lazy so the app runs without a database
        path = search_path()
        _pool = await asyncpg.create_pool(config.DATABASE_URL, init=_init_connection,
                                          server_settings={"search_path": path} if path else None)
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
