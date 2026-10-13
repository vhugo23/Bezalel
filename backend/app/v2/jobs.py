"""Postgres-backed, bounded work queue with restart recovery and atomic publication.

One orchestration row can have multiple generation_jobs, one for each model
attempt. No automatic retries after a provider/validation failure; the user
chooses retry. A lost worker can resume at most three times, with an audit trail.
"""
import asyncio
import hashlib
import json
import logging
from uuid import uuid4

from fastapi import HTTPException

from . import db
from .models import WorkItem
from .work_context import work_item_id

logger = logging.getLogger(__name__)
TERMINAL = {'succeeded', 'failed', 'cancelled'}


class JobCancelled(Exception):
    pass


def cache_key(kind, payload):
    encoded = json.dumps({'kind': kind, 'version': 1, 'input': payload}, sort_keys=True, separators=(',', ':'))
    return hashlib.sha256(encoded.encode()).hexdigest()


def output(row):
    return WorkItem(**dict(row))


async def read(jid):
    row = await db.one('SELECT * FROM work_items WHERE id=$1', jid)
    if not row:
        raise HTTPException(404, 'Generation job not found')
    return output(row)


async def enqueue_lesson(sid):
    from . import learning, engine, rubrics
    from .generation import DEMO
    from app import config
    session, gap, _ = await learning.context(sid)
    definition = await engine.context(sid)
    payload = {'session_id': sid, 'claim_id': gap.id, 'scenario_id': session['scenario_id'],
               'rubric_version': rubrics.load(definition['rubric'], definition['engine_id']).version,
               'model': config.EVALUATOR_MODEL or config.GEMINI_MODEL,
               'recorded': DEMO}
    return await enqueue('lesson', session['user_id'], sid, payload)


async def enqueue(kind, user_id, subject_id, payload):
    if kind not in {'lesson', 'extract_source', 'plan', 'job_scan', 'ats_review'}:
        raise HTTPException(422, 'Unsupported generation workflow')
    from app import config
    if config.DATABASE_URL:
        from .providers import configuration_fingerprint
        connection=await configuration_fingerprint(user_id)
        if connection:payload={**payload,'connection':connection}
    row = await db.one('''INSERT INTO work_items(id,user_id,kind,subject_id,cache_key,payload)
        VALUES($1,$2,$3,$4,$5,$6)
        ON CONFLICT(user_id,kind,cache_key) DO UPDATE SET cache_key=excluded.cache_key RETURNING *''',
        str(uuid4()), user_id, kind, subject_id, cache_key(kind, payload), payload)
    return output(row)


async def latest_lesson(sid):
    from .service import require_session
    await require_session(sid)
    row = await db.one("SELECT * FROM work_items WHERE kind='lesson' AND subject_id=$1 ORDER BY created_at DESC LIMIT 1", sid)
    return output(row) if row else None


async def retry(jid):
    async with (await db.pool()).acquire() as conn, conn.transaction():
        row = await conn.fetchrow('SELECT * FROM work_items WHERE id=$1 FOR UPDATE', jid)
        if not row:
            raise HTTPException(404, 'Generation job not found')
        if row['status'] not in ('failed', 'cancelled'):
            raise HTTPException(409, 'Only a failed or cancelled job can retry.')
        if row['attempts'] >= 3:
            raise HTTPException(409, 'This job reached its three-attempt limit. Your evidence is saved.')
        row = await conn.fetchrow("UPDATE work_items SET status='queued',stage='Queued',error=NULL,finished_at=NULL,updated_at=now() WHERE id=$1 RETURNING *", jid)
    return output(row)


async def cancel(jid):
    async with (await db.pool()).acquire() as conn, conn.transaction():
        row = await conn.fetchrow('SELECT * FROM work_items WHERE id=$1 FOR UPDATE', jid)
        if not row:
            raise HTTPException(404, 'Generation job not found')
        if row['status'] == 'cancelled':
            return output(row)
        if row['status'] in TERMINAL or row['stage'] == 'Publishing':
            raise HTTPException(409, 'This job already finished or is publishing its checked result.')
        row = await conn.fetchrow("UPDATE work_items SET status='cancelled',stage='Cancelled',finished_at=now(),updated_at=now() WHERE id=$1 RETURNING *", jid)
    return output(row)


async def stage(label):
    jid = work_item_id.get()
    if jid:
        row = await db.one("UPDATE work_items SET stage=$2,updated_at=now() WHERE id=$1 AND status='running' RETURNING id", jid, label)
        if not row:
            raise JobCancelled()


async def publication_guard(conn):
    """Lock and check inside the SAME transaction that publishes the artifact.

Cancellation either wins before publication, or observes the completed result.
It can never be accepted and then followed by a newly published lesson.
"""
    jid = work_item_id.get()
    if jid:
        row = await conn.fetchrow('SELECT status FROM work_items WHERE id=$1 FOR UPDATE', jid)
        if not row or row['status'] != 'running':
            raise JobCancelled()
        await conn.execute("UPDATE work_items SET stage='Publishing',updated_at=now() WHERE id=$1", jid)


async def published(conn, result):
    jid = work_item_id.get()
    if jid:
        await conn.execute("UPDATE work_items SET status='succeeded',stage='Complete',result=$2,finished_at=now(),updated_at=now() WHERE id=$1 AND status='running'", jid, result)


async def handle(row):
    if row['kind'] == 'plan':
        from .planning import create
        return await create(row)
    if row['kind'] == 'extract_source':
        from .sources import extract
        return await extract(row)
    if row['kind'] == 'job_scan':
        from .resume import scan
        return await scan(row)
    if row['kind'] == 'ats_review':
        from .resume import review
        return await review(row)
    if row['kind'] == 'lesson':
        from . import learning, engine, rubrics
        sid = row['payload']['session_id']
        session, gap, _ = await learning.context(sid)
        definition = await engine.context(sid)
        if (gap.id != row['payload']['claim_id'] or session['scenario_id'] != row['payload']['scenario_id']
                or rubrics.load(definition['rubric'], definition['engine_id']).version != row['payload']['rubric_version']):
            raise HTTPException(409, 'The source review changed.')
        return (await learning.create(sid)).model_dump(mode='json')
    raise ValueError('Unsupported generation workflow')


async def execute(jid):
    async with (await db.pool()).acquire() as lock:
        if not await lock.fetchval("SELECT pg_try_advisory_lock(hashtextextended('work:' || $1,0))", jid):
            return
        task = None
        token = work_item_id.set(jid)
        try:
            async with lock.transaction():
                row = await lock.fetchrow('SELECT * FROM work_items WHERE id=$1 FOR UPDATE', jid)
                if not row or row['status'] not in ('queued', 'running'):
                    return
                if row['attempts'] >= 3:
                    await lock.execute("UPDATE work_items SET status='failed',stage='Stopped',error='Worker recovery limit reached. Your evidence is saved.',finished_at=now(),updated_at=now() WHERE id=$1", jid)
                    return
                # The advisory lock proves any prior owner has released the job.
                await lock.execute("UPDATE generation_jobs SET status='failed',stage='Recovered after interruption',error='Worker interrupted',finished_at=now() WHERE work_item_id=$1 AND status='running'", jid)
                row = await lock.fetchrow("UPDATE work_items SET status='running',stage='Preparing',attempts=attempts+1,error=NULL,updated_at=now() WHERE id=$1 RETURNING *", jid)
            task = asyncio.create_task(handle(row))
            while not task.done():
                await asyncio.wait({task}, timeout=.5)
                current = await db.one('SELECT status FROM work_items WHERE id=$1', jid)
                if not current or current['status'] == 'cancelled':
                    task.cancel()
                    break
            try:
                result = await task
            except asyncio.CancelledError:
                # Explicit cancellation is terminal; shutdown leaves running for recovery.
                current = await db.one('SELECT status FROM work_items WHERE id=$1', jid)
                if current and current['status'] == 'cancelled':
                    return
                raise
            await db.execute("UPDATE work_items SET status='succeeded',stage='Complete',result=$2,finished_at=now(),updated_at=now() WHERE id=$1 AND status='running'", jid, result)
        except asyncio.CancelledError:
            if task and not task.done():
                task.cancel()
                try:
                    await task
                except asyncio.CancelledError:
                    pass
            raise
        except JobCancelled:
            pass
        except Exception as exc:
            # Provider errors are already reduced to safe messages by generation.
            # Never store arbitrary exception text (DSNs, source material, keys).
            message = 'Generation could not finish. Your evidence is saved; retry when ready.'
            if isinstance(exc, HTTPException) and exc.status_code == 409:
                message = 'The source review changed or is incomplete. Reopen your evidence before retrying.'
            logger.warning('Work item failed: %s', type(exc).__name__)
            await db.execute("UPDATE work_items SET status='failed',stage='Needs another pass',error=$2,finished_at=now(),updated_at=now() WHERE id=$1 AND status='running'", jid, message)
        finally:
            if task and not task.done():
                task.cancel()
                await asyncio.gather(task, return_exceptions=True)
            work_item_id.reset(token)
            await asyncio.shield(lock.execute("SELECT pg_advisory_unlock(hashtextextended('work:' || $1,0))", jid))


async def worker():
    while True:
        try:
            for row in await db.fetch("SELECT id FROM work_items WHERE status IN ('queued','running') ORDER BY created_at LIMIT 10"):
                await execute(row['id'])
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            logger.warning('Generation queue unavailable: %s', type(exc).__name__)
        await asyncio.sleep(1)
