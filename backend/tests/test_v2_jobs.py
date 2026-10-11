import asyncio
from unittest.mock import AsyncMock

import pytest

from app.v2 import jobs, generation
from app.v2.models import Critique
from app.v2.work_context import work_item_id


def test_cache_is_canonical_and_versioned_by_input():
    assert jobs.cache_key('lesson', {'a': 1, 'b': 2}) == jobs.cache_key('lesson', {'b': 2, 'a': 1})
    assert jobs.cache_key('lesson', {'claim': 'a'}) != jobs.cache_key('lesson', {'claim': 'b'})


def test_model_audit_inherits_only_its_async_task_context(monkeypatch):
    audit = AsyncMock()
    monkeypatch.setattr(generation.db, 'execute', audit)
    async def call(jid):
        token = work_item_id.set(jid)
        try:
            await asyncio.sleep(0)
            await generation.generate('lesson', 'subject', 'Synthetic test', Critique,
                                      cached={'marks': []}, prefer_cache=True, subject_type='lesson')
        finally:
            work_item_id.reset(token)
    async def run():
        await asyncio.gather(call('job-a'), call('job-b'))
        assert work_item_id.get() is None
    asyncio.run(run())
    inserts = [c for c in audit.call_args_list if 'INSERT INTO generation_jobs' in c.args[0]]
    assert {c.args[11] for c in inserts} == {'job-a', 'job-b'}


def test_publication_gate_rejects_cancelled_job():
    conn = type('Connection', (), {'fetchrow': AsyncMock(return_value={'status': 'cancelled'}),
                                  'execute': AsyncMock()})()
    async def run():
        token = work_item_id.set('cancelled-job')
        try:
            with pytest.raises(jobs.JobCancelled):
                await jobs.publication_guard(conn)
        finally:
            work_item_id.reset(token)
    asyncio.run(run())
    conn.execute.assert_not_called()
