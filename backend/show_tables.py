"""Prints every table in the app's schema (DATABASE_SCHEMA, or public) with its columns and row count."""
import asyncio

import asyncpg

from app import config


async def main():
    schema = config.DATABASE_SCHEMA or "public"
    conn = await asyncpg.connect(config.DATABASE_URL)
    try:
        tables = await conn.fetch("select table_name from information_schema.tables "
                                  "where table_schema = $1 and table_type = 'BASE TABLE' order by 1", schema)
        print(f"schema '{schema}': {len(tables)} tables")
        for t in tables:
            name = t["table_name"]
            n = await conn.fetchval(f'select count(*) from "{schema}"."{name}"')
            cols = await conn.fetch("select column_name from information_schema.columns "
                                    "where table_schema = $1 and table_name = $2 order by ordinal_position", schema, name)
            print(f"{name}: {n} rows | " + ", ".join(c["column_name"] for c in cols))
    finally:
        await conn.close()


asyncio.run(main())
