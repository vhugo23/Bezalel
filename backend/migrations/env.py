import asyncio
import os
import re
from alembic import context
from app.environment import load_environment
from sqlalchemy.ext.asyncio import create_async_engine

load_environment()
schema = os.getenv('V2_DATABASE_SCHEMA', 'prepcrew')
if not re.fullmatch(r'[a-z][a-z0-9_]{0,62}', schema):
    raise ValueError('Invalid V2_DATABASE_SCHEMA')
context.config.attributes['schema'] = schema

def run(connection):
    connection.exec_driver_sql(f'SET search_path TO "{schema}", public')
    connection.commit()
    context.configure(connection=connection, version_table_schema=schema)
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
        await connection.exec_driver_sql(f'CREATE SCHEMA IF NOT EXISTS "{schema}"')
    async with engine.connect() as connection:
        await connection.run_sync(run)
    await engine.dispose()

if context.is_offline_mode():
    raise RuntimeError('Timescale migrations require an online database connection.')
asyncio.run(main())
