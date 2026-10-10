"""Prints every table with its columns and row count."""
import asyncio

import asyncpg

from app import config


async def main():
    conn = await asyncpg.connect(config.DATABASE_URL)
    tables = await conn.fetch(
        "select table_name from information_schema.tables "
        "where table_schema='public' and table_type='BASE TABLE' order by 1")
    for t in tables:
        name = t["table_name"]
        n = await conn.fetchval(f'select count(*) from "{name}"')
        cols = await conn.fetch(
            "select column_name from information_schema.columns "
            "where table_schema='public' and table_name=$1 order by ordinal_position", name)
        print(f"{name}: {n} rows | " + ", ".join(c["column_name"] for c in cols))
    await conn.close()


asyncio.run(main())
