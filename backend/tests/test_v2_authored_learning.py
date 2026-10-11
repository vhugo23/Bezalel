import asyncio
from contextlib import asynccontextmanager
from unittest.mock import AsyncMock
from types import SimpleNamespace
import pytest
from fastapi import HTTPException
from app.v2 import learning, learning_variants, pi_lab, jobs, service
from app.v2.models import GapSummary


def test_pi_publication_uses_no_model_and_keeps_job_guard_and_authored_label(monkeypatch):
    original={'id':'scenario','engine_id':'linux_fault',**pi_lab.definition()}
    session={'scenario_id':'scenario','user_id':'synthetic','track_id':'parent'}
    gap=GapSummary(id='gap',skill_id='infra.permissions',text='Synthetic verified gap',evidence_seq=[1])
    @asynccontextmanager
    async def scope(*args):yield conn
    conn=SimpleNamespace(transaction=scope,execute=AsyncMock(),fetch=AsyncMock(return_value=[]),
        fetchrow=AsyncMock(return_value={'id':'parent','plan_id':'plan','template_id':'infra.pi_site','domain_id':'infra'}))
    pool=SimpleNamespace(acquire=scope)
    monkeypatch.setattr(learning,'learning_lock',scope)
    monkeypatch.setattr(learning,'context',AsyncMock(return_value=(session,gap,None)))
    monkeypatch.setattr(learning.db,'one',AsyncMock(return_value=original))
    monkeypatch.setattr(learning.db,'pool',AsyncMock(return_value=pool))
    monkeypatch.setattr(learning,'read',AsyncMock(return_value='authored lesson'))
    model=AsyncMock(side_effect=AssertionError('Authored Pi coaching must not call a model'))
    monkeypatch.setattr(learning,'generate',model)
    guard,publish=AsyncMock(),AsyncMock()
    monkeypatch.setattr(jobs,'stage',AsyncMock())
    monkeypatch.setattr(jobs,'publication_guard',guard)
    monkeypatch.setattr(jobs,'published',publish)
    monkeypatch.setattr(learning.engine,'persist_steps',AsyncMock())
    assert asyncio.run(learning.create('session'))=='authored lesson'
    model.assert_not_called();guard.assert_awaited_once_with(conn)
    inserts=[call.args for call in conn.execute.call_args_list if 'INSERT INTO lessons' in call.args[0]]
    assert len(inserts)==1 and inserts[0][-1] is False
    assert inserts[0][-3:-1]==(None,None)
    published=publish.call_args.args[1]
    assert published['ai_generated'] is False and published['retest_ready'] is True
    assert 'Authored coaching' in published['validation_label']


@pytest.mark.parametrize('status,partial,gap',[('graded',True,True),('grading',False,True),('graded',False,False)])
def test_authored_coaching_does_not_bypass_complete_verified_gap_gate(monkeypatch,status,partial,gap):
    monkeypatch.setattr(learning,'require_session',AsyncMock(return_value={'user_id':'synthetic'}))
    monkeypatch.setattr(service,'report',AsyncMock(return_value=SimpleNamespace(status=status,partial=partial,next_gap=gap)))
    with pytest.raises(HTTPException) as error:asyncio.run(learning.context('session'))
    assert error.value.status_code==409
