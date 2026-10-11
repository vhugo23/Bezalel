import asyncio
from unittest.mock import AsyncMock
import pytest
from fastapi import HTTPException
from app.v2 import local_speech as local, realtime as rt, voice


@pytest.fixture
def mocked(monkeypatch):
    session=AsyncMock(return_value={'status':'live','step':1,'engine_state':{}})
    one=AsyncMock(return_value={'id':'local-job','payload':{'text':'Saved Dana words'}})
    execute=AsyncMock();job=AsyncMock(return_value='local-job')
    monkeypatch.setattr(local.s,'require_session',session);monkeypatch.setattr(local.db,'one',one)
    monkeypatch.setattr(local.db,'execute',execute);monkeypatch.setattr(local.voice,'job',job)
    return session,one,execute,job


def test_local_tts_uses_saved_interviewer_text_and_client_reported_audit(mocked):
    _,one,execute,job=mocked
    result=asyncio.run(local.start('s',local.LocalSpeechStart(kind='tts',seq=9)))
    assert result.text=='Saved Dana words'
    assert "actor='interviewer'" in one.call_args.args[0]
    assert job.call_args.args==('s','tts',local.MODELS['tts'])
    assert execute.call_args.args[2]=={'execution':'browser','client_reported':True,'seq':9,'step':1}


def test_local_tts_cannot_generate_arbitrary_unlogged_text(mocked):
    mocked[1].return_value=None
    with pytest.raises(HTTPException):asyncio.run(local.start('s',local.LocalSpeechStart(kind='tts',seq=9)))
    mocked[3].assert_not_awaited()


def test_saved_interviewer_speech_can_be_replayed_after_session_finishes(mocked):
    mocked[0].return_value={'status':'graded','step':3,'engine_state':{'paused':True}}
    result=asyncio.run(local.start('s',local.LocalSpeechStart(kind='tts',seq=9)))
    assert result.text=='Saved Dana words'


@pytest.mark.parametrize('status,paused',[('graded',False),('live',True)])
def test_local_inference_requires_live_unpaused_session(mocked,status,paused):
    mocked[0].return_value={'status':status,'step':1,'engine_state':{'paused':paused}}
    with pytest.raises(HTTPException):asyncio.run(local.start('s',local.LocalSpeechStart(kind='stt')))
    mocked[3].assert_not_awaited()


def test_finish_is_session_scoped_once_and_labels_results_untrusted(mocked):
    asyncio.run(local.finish('s','jid',local.LocalSpeechFinish(status='succeeded',text='Recognized words',latency_ms=12)))
    sql,*args=mocked[1].call_args.args
    assert "status='running'" in sql and 'subject_id=$2' in sql
    assert args==['jid','s','succeeded',{'text':'Recognized words','client_reported':True},12,None]
    mocked[1].return_value=None
    with pytest.raises(HTTPException):asyncio.run(local.finish('s','foreign',local.LocalSpeechFinish(status='failed')))


def test_transcript_must_match_finished_local_job_step_and_can_only_be_consumed_once(mocked):
    assert asyncio.run(local.consume_transcript('s','jid','Recognized words',True))=='jid'
    sql,*args=mocked[1].call_args.args
    assert 'response->>\'text\'=$3' in sql and "kind='stt'" in sql and "stage='Browser inference completed'" in sql
    assert args==['jid','s','Recognized words',1]
    mocked[1].return_value=None
    with pytest.raises(HTTPException):asyncio.run(local.consume_transcript('s','jid','Forged',True))


def test_local_control_is_rejected_while_cloud_stt_is_active(monkeypatch):
    class Socket:
        async def receive(self):return {'type':'websocket.receive','text':'{"type":"local_final","text":"Forged","inference_id":"id"}'}
    with pytest.raises(HTTPException) as error:asyncio.run(rt.receive_browser(Socket(),rt.Conversation('s',AsyncMock()),AsyncMock(),object()))
    assert error.value.status_code==409


def test_audited_local_transcript_uses_canonical_turn_and_same_interruption_protocol(mocked,monkeypatch):
    from datetime import datetime,timezone
    from app.v2.models import Event
    candidate=Event(session_id='s',seq=8,kind='turn',actor='candidate',step=1,ts=datetime.now(timezone.utc),payload={'text':'Can you clarify the requirements?','board':True})
    recorded=AsyncMock(return_value=candidate);monkeypatch.setattr(rt.s,'record_candidate',recorded)
    monkeypatch.setattr(rt.s.engine,'context',AsyncMock(return_value={'steps':[{},{}]}))
    monkeypatch.setattr(rt.s,'respond',AsyncMock());monkeypatch.setattr(rt.s,'log',AsyncMock())
    send=AsyncMock();conversation=rt.Conversation('s',send)
    class Socket:
        messages=iter([
            {'type':'websocket.receive','text':'{"type":"local_partial","text":"Can you clarify the requirements?","inference_id":"preview"}'},
            {'type':'websocket.receive','text':'{"type":"local_final","text":"Can you clarify the requirements?","inference_id":"final"}'},
            {'type':'websocket.disconnect'}])
        async def receive(self):return next(self.messages)
    async def check():
        conversation.playing=7
        await rt.receive_browser(Socket(),conversation,send)
        await conversation.close()
    asyncio.run(check())
    assert recorded.call_args.args[2]=='final'
    assert recorded.call_args.args[1].text==candidate.payload['text']
    assert any(c.args[0]['type']=='interrupt' for c in send.call_args_list)
    assert any(c.args[0]['type']=='committed' for c in send.call_args_list)


@pytest.mark.parametrize('status,code,eligible',[(402,'',True),(429,'quota_exceeded',True),(429,'rate_limit',False),(401,'',False),(403,'missing_permissions',False),(500,'',False)])
def test_only_quota_errors_authorize_fallback(status,code,eligible):
    error=voice.provider_error(status,code)
    assert bool((error.headers or {}).get('X-PrepCrew-Speech-Fallback'))==eligible
