import asyncio
from datetime import datetime,timezone
from unittest.mock import AsyncMock
import pytest
from app.v2 import service,engine,db,pi_lab
from app.v2.models import Event,Reply
from app.v2.models import EventInput


class Context:
    def __init__(self,value=None):self.value=value
    async def __aenter__(self):return self.value
    async def __aexit__(self,*args):return False


class Conn:
    def transaction(self):return Context()
    async def fetchrow(self,*args):return {'status':'live','step':1,'engine_state':{}}
    async def fetchval(self,*args):return 1


@pytest.mark.parametrize('complete',[False,True])
def test_dana_progression_requires_simulator_goal_and_hides_private_state(monkeypatch,complete):
    state=pi_lab.initial()
    if complete:state.update(active_port=3000,verified={'proxy':True})
    data=pi_lab.definition()
    definition={'engine_id':'linux_fault','spec':data['spec'],'steps':engine.parse_steps(data['spec']),
        'engine_state':{'_lab':state,'_private':'PRIVATE_CANARY'},'params':{'answer':'PRIVATE_CANARY'},'step':1}
    first=Event(session_id='s',seq=1,kind='turn',actor='candidate',step=1,
        payload={'text':'I verified the response.','q':False},ts=datetime.now(timezone.utc))
    monkeypatch.setattr(service,'events',AsyncMock(return_value=[first]))
    monkeypatch.setattr(engine,'context',AsyncMock(return_value=definition))
    pool=type('Pool',(),{'acquire':lambda self:Context(Conn())})()
    monkeypatch.setattr(db,'pool',AsyncMock(return_value=pool))
    async def generate(*args,**kwargs):
        assert 'PRIVATE_CANARY' not in args[2]
        assert 'tool_goal_complete' in args[2]
        return Reply(text='Explain the next check.',action='advance'),'job','fake'
    monkeypatch.setattr(service,'generate',generate)
    captured=[]
    async def log(sid,kind,actor,step,payload,conn):
        captured.append(payload)
        return first.model_copy(update={'seq':2,'actor':'interviewer','payload':payload})
    monkeypatch.setattr(service,'log',log)
    asyncio.run(service.respond('s',first))
    assert captured[0]['action']==('advance' if complete else 'continue')


@pytest.mark.parametrize('text',['', '   ', None])
def test_client_cannot_satisfy_explanation_gate_with_an_empty_turn(monkeypatch,text):
    from fastapi import HTTPException
    from pydantic import ValidationError
    pool=type('Pool',(),{'acquire':lambda self:Context(Conn())})()
    monkeypatch.setattr(db,'pool',AsyncMock(return_value=pool))
    monkeypatch.setattr(engine,'context',AsyncMock(return_value={'steps':engine.parse_steps(pi_lab.definition()['spec'])}))
    with pytest.raises((HTTPException,ValidationError)):
        asyncio.run(service.append('s',EventInput(kind='turn',step=1,payload={'text':text})))


def test_appended_text_cannot_forge_board_question_or_provider_metadata(monkeypatch):
    pool=type('Pool',(),{'acquire':lambda self:Context(Conn())})()
    monkeypatch.setattr(db,'pool',AsyncMock(return_value=pool))
    monkeypatch.setattr(engine,'context',AsyncMock(return_value={'steps':engine.parse_steps(pi_lab.definition()['spec'])}))
    recorder=AsyncMock();monkeypatch.setattr(service,'log',recorder)
    asyncio.run(service.append('s',EventInput(kind='turn',step=1,payload={'text':' The proxy response is healthy. ','board':True,'q':True,'source_job_id':'invented'})))
    payload=recorder.call_args.args[4]
    assert payload=={'text':'The proxy response is healthy.','q':False,'board':False,'source':'client_text'}
