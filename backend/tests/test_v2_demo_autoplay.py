import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock
from contextlib import asynccontextmanager
import pytest
from fastapi import HTTPException
from app.v2 import demo_autoplay as demo, service, engine, db, routes, pi_lab, rubrics
from app.v2.models import TurnInput


def test_scripted_turn_uses_saved_candidate_and_authored_dana_without_model(monkeypatch):
    definition={'engine_id':'conceptual'}
    monkeypatch.setattr(demo,'supported',AsyncMock(return_value=({},definition)))
    first=SimpleNamespace(seq=7)
    monkeypatch.setattr(service,'record_candidate',AsyncMock(return_value=first))
    monkeypatch.setattr(demo,'mark',AsyncMock())
    monkeypatch.setattr(db,'one',AsyncMock(return_value={'n':1}))
    saved=AsyncMock(return_value=SimpleNamespace(seq=8))
    monkeypatch.setattr(service,'log',saved)
    monkeypatch.setattr(service,'generate',AsyncMock(side_effect=AssertionError('No model calls in demo')))
    # Result event validation is covered by the real endpoint/browser test; inspect saved payload here.
    monkeypatch.setattr(demo,'TurnResult',lambda **kwargs:kwargs)
    result=asyncio.run(demo.turn('session',TurnInput(step=0,text='Synthetic candidate')))
    assert result['source']=='scripted_demo'
    assert saved.call_args.args[-1]['source']=='scripted_demo'
    assert saved.call_args.args[-1]['action']=='continue'
    service.generate.assert_not_called()


@pytest.mark.parametrize('source,kind,variant',[('retest','retest',0),('onboarding','session',1)])
def test_demo_rejects_retests_and_changed_pi_variants(monkeypatch,source,kind,variant):
    monkeypatch.setattr(service,'require_session',AsyncMock(return_value={'track_id':'t','kind':kind}))
    monkeypatch.setattr(db,'one',AsyncMock(return_value={'source':source,'title':'Pi'}))
    monkeypatch.setattr(engine,'context',AsyncMock(return_value={'engine_id':'linux_fault','params':{'variant':variant},'steps':[SimpleNamespace(title=t) for t in pi_lab.TITLES]}))
    with pytest.raises(HTTPException):asyncio.run(demo.supported('session'))


def test_demo_recap_is_explicitly_authored_and_contains_no_scores_or_claims():
    for engine_id in ('conceptual','linux_fault'):
        recap=demo.recap(engine_id)
        assert recap['scripted'] is True and 'not an assessment' in recap['label']
        assert len(recap['weakpoints'])>=2
        assert recap['lesson']['body'] and recap['retest_prompt']
        assert 'scores' not in recap and 'claims' not in recap


def test_normal_end_of_scripted_run_never_enqueues_real_grading(monkeypatch):
    monkeypatch.setattr(service,'require_session',AsyncMock(return_value={'engine_state':{'scripted_demo':True}}))
    finish=AsyncMock();monkeypatch.setattr(demo,'end',finish)
    monkeypatch.setattr(service,'report',AsyncMock(return_value='scripted report'))
    assert asyncio.run(routes.end('session'))=='scripted report'
    finish.assert_awaited_once_with('session')


def test_saved_scripted_board_review_is_readable_without_a_generation_job(monkeypatch):
    item={'id':'limiter','version':1,'element':{'id':'limiter','version':1,'isDeleted':False,'type':'rectangle','x':0,'y':0,'width':100,'height':80,'angle':0}}
    events=[SimpleNamespace(kind='stroke',actor='candidate',step=1,seq=1,payload=item),
        SimpleNamespace(kind='note',actor='system',step=1,seq=2,payload={'board_snapshot':True,'artifact_id':'artifact'})]
    monkeypatch.setattr(db,'one',AsyncMock(return_value={'id':'artifact','job_status':None,'payload':{'items':[item],'scripted_demo':True}}))
    monkeypatch.setattr(db,'fetch',AsyncMock(return_value=[]))
    result=asyncio.run(service.current_board_review('session',1,events))
    assert result and result.source=='scripted_demo' and result.stroke_ids==['limiter']
    steps=engine.LEGACY_STEPS
    assert engine.action_allowed('advance',1,1,bool(result),'Continue',steps)=='advance'
