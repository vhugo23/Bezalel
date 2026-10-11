"""Queue acceptance on the E2E harness's disposable schema, never real users.

Runs recorded model fixtures, shutdown/recovery, two workers contending,
cancellation during generation, cancellation/publication races and retry bounds.
"""
import asyncio
from contextlib import suppress
from uuid import uuid4

from fastapi import HTTPException

from app import config
from app.v2 import db, jobs, generation
from app.v2.models import Critique


async def verify(source, schema):
    assert schema.startswith('prepcrew_e2e_') and schema.replace('_', '').isalnum()
    prior_url, prior_schema = config.DATABASE_URL, config.V2_DATABASE_SCHEMA
    prior_handler = jobs.handle
    assert db._pool is None, 'Acceptance requires its own process and connection pool'
    config.DATABASE_URL, config.V2_DATABASE_SCHEMA = source, schema
    owner = 'synthetic-queue-' + uuid4().hex
    tasks = []
    try:
        await db.execute('INSERT INTO users(id,display_name) VALUES($1,$2)', owner, 'Synthetic queue acceptance')
        async def enqueue(key):
            return await jobs.enqueue('lesson', owner, key, {'synthetic': True, 'key': key})
        first = await enqueue('recovery')
        assert (await enqueue('recovery')).id == first.id
        entered, release = asyncio.Event(), asyncio.Event()
        calls = 0
        async def recorded(row):
            nonlocal calls
            calls += 1
            await generation.generate('lesson', row['subject_id'], 'Synthetic queue acceptance', Critique,
                cached={'marks': []}, prefer_cache=True, user_id=owner, subject_type='lesson')
            entered.set()
            await release.wait()
            async with (await db.pool()).acquire() as conn, conn.transaction():
                await jobs.publication_guard(conn)
                await jobs.published(conn, {'synthetic': True})
            return {'synthetic': True}
        jobs.handle = recorded
        task = asyncio.create_task(jobs.execute(first.id)); tasks.append(task)
        await asyncio.wait_for(entered.wait(), 5)
        await jobs.execute(first.id)  # A second worker must not run it concurrently.
        assert calls == 1
        task.cancel()
        with suppress(asyncio.CancelledError): await task
        assert (await jobs.read(first.id)).status == 'running'
        release.set()
        await jobs.execute(first.id)
        saved = await jobs.read(first.id)
        assert saved.status == 'succeeded' and saved.attempts == 2 and saved.result == {'synthetic': True}
        assert await db.one('SELECT id FROM generation_jobs WHERE work_item_id=$1', first.id)

        entered.clear(); release.clear()
        item = await enqueue('cancel-before-publication')
        task = asyncio.create_task(jobs.execute(item.id)); tasks.append(task)
        await asyncio.wait_for(entered.wait(), 5)
        assert (await jobs.cancel(item.id)).status == 'cancelled'
        await asyncio.wait_for(task, 5)
        assert (await jobs.read(item.id)).result is None

        entered.clear(); release.clear()
        async def publishing(row):
            async with (await db.pool()).acquire() as conn, conn.transaction():
                await jobs.publication_guard(conn)
                entered.set()
                await release.wait()
                await jobs.published(conn, {'published': True})
            return {'published': True}
        jobs.handle = publishing
        item = await enqueue('publication-wins')
        task = asyncio.create_task(jobs.execute(item.id)); tasks.append(task)
        await asyncio.wait_for(entered.wait(), 5)
        cancellation = asyncio.create_task(jobs.cancel(item.id)); tasks.append(cancellation)
        await asyncio.sleep(.05)
        assert not cancellation.done()  # Waits behind the publication transaction.
        release.set()
        await asyncio.wait_for(task, 5)
        try:
            await cancellation
            raise AssertionError('Cancellation must not be accepted after publication')
        except HTTPException as exc:
            assert exc.status_code == 409
        assert (await jobs.read(item.id)).status == 'succeeded'

        async def fail(_): raise RuntimeError('sensitive-dsn-must-not-be-stored')
        jobs.handle = fail
        item = await enqueue('bounded-retries')
        for attempt in range(1, 4):
            await jobs.execute(item.id)
            failed = await jobs.read(item.id)
            assert failed.status == 'failed' and failed.attempts == attempt
            assert 'sensitive' not in failed.error
            if attempt < 3: await jobs.retry(item.id)
        try:
            await jobs.retry(item.id)
            raise AssertionError('Retry bound must be enforced')
        except HTTPException as exc:
            assert exc.status_code == 409
        print('Queue acceptance: idempotence, worker exclusion, restart recovery, cancellation, atomic publication and retry bounds passed (recorded fixtures).')
    finally:
        for task in tasks:
            if not task.done(): task.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)
        jobs.handle = prior_handler
        if db._pool:
            await db._pool.close()
            db._pool = None
        config.DATABASE_URL, config.V2_DATABASE_SCHEMA = prior_url, prior_schema
