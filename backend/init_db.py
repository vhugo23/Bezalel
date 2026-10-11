"""Creates all tables (core first, then module files). Safe to run any number of times.

    python init_db.py                 # into DATABASE_SCHEMA from .env (recommended), or public if it is blank
    python init_db.py --schema NAME   # into another schema

With a schema it creates the schema if needed and never touches public. Your other schemas and tables are left alone.
"""
import argparse
import asyncio
from pathlib import Path

import asyncpg

from app import config, db


async def main(schema: str):
    conn = await asyncpg.connect(config.DATABASE_URL)
    try:
        ext = await conn.fetchval("select n.nspname from pg_extension e join pg_namespace n on n.oid = e.extnamespace "
                                  "where e.extname = 'timescaledb'")
        if ext is None:
            raise SystemExit("timescaledb is not installed in this database (Tiger has it). Stopping, nothing changed.")
        if schema:
            if not db.SCHEMA_NAME.match(schema):
                raise SystemExit(f"schema name '{schema}' must be lowercase letters, digits and _ only")
            if ext != "public":
                print(f"note: timescaledb lives in schema '{ext}', not public; the app expects public")
            await conn.execute(f'CREATE SCHEMA IF NOT EXISTS "{schema}"')
            await conn.execute(f'SET search_path TO "{schema}", "{ext}"')
        target = schema or "public"
        print(f"creating tables in schema '{target}'")
        files = sorted(Path("sql").glob("*.sql"), key=lambda p: (p.name != "schema.sql", p.name))
        for f in files:
            await conn.execute(f.read_text(encoding="utf-8"))
            print("ran", f.as_posix())
        rows = await conn.fetch("select table_name from information_schema.tables "
                                "where table_schema = $1 and table_type = 'BASE TABLE' order by 1", target)
        print(f"{len(rows)} tables in '{target}':", ", ".join(r["table_name"] for r in rows))
        if schema and schema != config.DATABASE_SCHEMA:
            print(f"\nTo use it, set DATABASE_SCHEMA={schema} in backend/.env and restart the server.")
    finally:
        await conn.close()


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--schema", default=None, help="schema to create the tables in (default: DATABASE_SCHEMA)")
    args = ap.parse_args()
    asyncio.run(main(args.schema if args.schema is not None else config.DATABASE_SCHEMA))
