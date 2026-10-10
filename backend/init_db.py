"""Creates all tables (core first, then module files). Safe to run any number of times."""
import asyncio
from pathlib import Path

import asyncpg

from app import config


async def main():
    conn = await asyncpg.connect(config.DATABASE_URL)
    files = sorted(Path("sql").glob("*.sql"), key=lambda p: (p.name != "schema.sql", p.name))
    for f in files:
        await conn.execute(f.read_text())
        print("ran", f)
    rows = await conn.fetch(
        "select table_name from information_schema.tables "
        "where table_schema='public' and table_type='BASE TABLE' order by 1")
    print("tables:", [r["table_name"] for r in rows])
    await conn.close()


asyncio.run(main())
