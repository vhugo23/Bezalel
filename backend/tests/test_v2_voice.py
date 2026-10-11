import asyncio
from unittest.mock import AsyncMock
import httpx
import pytest
from fastapi import HTTPException
from starlette.requests import Request
from app.v2 import voice, routes


@pytest.fixture
def provider(monkeypatch):
    monkeypatch.setattr(voice.config,'ELEVENLABS_API_KEY','test-key')
    monkeypatch.setattr(voice.config,'ELEVENLABS_VOICE_ID','test-voice')
    audit=AsyncMock()
    monkeypatch.setattr(voice.db,'execute',audit)
    original=httpx.AsyncClient
    def mock(handler):
        monkeypatch.setattr(voice.httpx,'AsyncClient',lambda **kw:original(transport=httpx.MockTransport(handler),**kw))
    return mock,audit


def test_stt_uploads_actual_mime_and_audits_transcript(provider):
    mock,audit=provider
    def respond(request):
        assert b'turn.mp4' in request.content
        assert b'audio/mp4' in request.content
        return httpx.Response(200,json={'text':'Use a token bucket.'})
    mock(respond)
    assert asyncio.run(voice.transcribe('s',b'recorded-audio','audio/mp4'))=='Use a token bucket.'
    assert any("status='succeeded'" in c.args[0] for c in audit.call_args_list)


@pytest.mark.parametrize('status',[401,403,429,500])
def test_stt_provider_failure_never_creates_a_transcript(provider,status):
    mock,audit=provider
    mock(lambda _:httpx.Response(status,json={'secret':'must never reach client'}))
    with pytest.raises(HTTPException) as exc:asyncio.run(voice.transcribe('s',b'audio','audio/webm'))
    assert exc.value.status_code==503
    assert 'secret' not in exc.value.detail
    assert any("status='failed'" in c.args[0] for c in audit.call_args_list)
    assert not any("status='succeeded'" in c.args[0] for c in audit.call_args_list)


def test_empty_transcription_does_not_become_candidate_evidence(provider):
    mock,_=provider
    mock(lambda _:httpx.Response(200,json={'text':'  '}))
    with pytest.raises(HTTPException) as exc:asyncio.run(voice.transcribe('s',b'audio','audio/webm'))
    assert exc.value.status_code==422


def test_tts_auth_error_precedes_successful_stream_headers(provider):
    mock,_=provider
    mock(lambda _:httpx.Response(401))
    with pytest.raises(HTTPException) as exc:asyncio.run(voice.speak('s','Hello.'))
    assert exc.value.status_code==503
    assert 'API key' in exc.value.detail


def test_permission_error_does_not_claim_the_key_is_invalid(provider):
    mock,_=provider
    mock(lambda _:httpx.Response(401,json={'detail':{'status':'missing_permissions'}}))
    with pytest.raises(HTTPException) as exc:asyncio.run(voice.speak('s','Hello.'))
    assert 'lacks permission' in exc.value.detail
    assert 'rejected' not in exc.value.detail


def test_model_failure_preserves_successful_stt_audit(provider,monkeypatch):
    mock,audit=provider
    mock(lambda _:httpx.Response(200,json={'text':'What scale?'}))
    monkeypatch.setattr(routes,'DEMO',False)
    monkeypatch.setattr(routes.s,'require_session',AsyncMock(return_value={'status':'live','step':0}))
    monkeypatch.setattr(routes.s,'turn',AsyncMock(side_effect=ValueError('Model unavailable')))
    async def receive():return {'type':'http.request','body':b'audio','more_body':False}
    request=Request({'type':'http','headers':[(b'content-type',b'audio/webm')]},receive)
    with pytest.raises(HTTPException):asyncio.run(routes.audio('s',request,step=0,board=False))
    assert any("status='succeeded'" in c.args[0] for c in audit.call_args_list)
    assert not any("status='failed'" in c.args[0] for c in audit.call_args_list)
