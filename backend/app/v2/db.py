import json
import asyncpg
from app import config

_pool = None

async def init(conn):
    await conn.set_type_codec('jsonb', encoder=json.dumps, decoder=json.loads, schema='pg_catalog')

async def pool():
    global _pool
    if _pool is None:
        _pool = await asyncpg.create_pool(config.DATABASE_URL, min_size=1, max_size=6, init=init,
                                         server_settings={'search_path': config.V2_DATABASE_SCHEMA + ',public'})
    return _pool

async def fetch(sql, *args):
    return await (await pool()).fetch(sql, *args)

async def one(sql, *args):
    return await (await pool()).fetchrow(sql, *args)

async def execute(sql, *args):
    return await (await pool()).execute(sql, *args)
