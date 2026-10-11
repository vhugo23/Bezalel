import asyncio
import os
from pathlib import Path
from alembic import context
from dotenv import load_dotenv
from sqlalchemy.ext.asyncio import create_async_engine

load_dotenv(Path(__file__).resolve().parents[2] / '.env')

def run(connection):
    context.configure(connection=connection, version_table_schema='prepcrew')
    with context.begin_transaction():
        context.run_migrations()

async def main():
    url = os.environ['DATABASE_URL'].replace('postgres://', 'postgresql://', 1).replace('postgresql://', 'postgresql+asyncpg://', 1)
    # asyncpg's SSL option differs from libpq's URL spelling.
    from sqlalchemy.engine import make_url
    parsed = make_url(url)
    opts = {}
    if 'sslmode' in parsed.query:
        opts['ssl'] = parsed.query['sslmode']
        parsed = parsed.difference_update_query(['sslmode'])
    engine = create_async_engine(parsed, connect_args=opts)
    async with engine.begin() as connection:
        await connection.exec_driver_sql('CREATE SCHEMA IF NOT EXISTS prepcrew')
    async with engine.connect() as connection:
        await connection.run_sync(run)
    await engine.dispose()

if context.is_offline_mode():
    raise RuntimeError('Timescale migrations require an online database connection.')
asyncio.run(main())
