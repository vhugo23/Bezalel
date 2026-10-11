import asyncio
from unittest.mock import AsyncMock
import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient
from starlette.websockets import WebSocketDisconnect
from pydantic import ValidationError
from app import config
from app.main import app
from app.v2 import auth,db,service,devices

REAL_ENABLED=auth.enabled
ACCOUNT={'id':'account-a','name':'Synthetic candidate','email':'a@example.test'}
HEADER={'X-PrepCrew-Request':'1'}


@pytest.fixture
def secured(monkeypatch):
    monkeypatch.setattr(auth,'enabled',lambda:True)
    monkeypatch.setattr(config,'LEGACY_API_ENABLED',False)
    monkeypatch.setattr(auth,'current',AsyncMock(return_value=ACCOUNT))
    monkeypatch.setattr(db,'one',AsyncMock(return_value={'user_id':'account-b'}))
    return TestClient(app)


def test_auth_bypass_is_impossible_in_normal_or_provider_enabled_schema(monkeypatch):
    monkeypatch.setattr(config,'V2_AUTH_TEST_BYPASS',True)
    monkeypatch.setenv('DEMO_MODE','true')
    for key in ('GEMINI_API_KEY','ELEVENLABS_API_KEY','BACKBOARD_API_KEY'):monkeypatch.setattr(config,key,'')
    monkeypatch.setattr(config,'V2_DATABASE_SCHEMA','prepcrew')
    assert REAL_ENABLED()
    monkeypatch.setattr(config,'V2_DATABASE_SCHEMA','prepcrew_e2e_synthetic')
    assert not REAL_ENABLED()
    monkeypatch.setattr(config,'GEMINI_API_KEY','synthetic-test-key')
    assert REAL_ENABLED()
    monkeypatch.setattr(config,'GEMINI_API_KEY','')
    monkeypatch.setenv('DEMO_MODE','false')
    assert REAL_ENABLED()


@pytest.mark.parametrize('path',[
    '/sessions/foreign','/sessions/foreign/events','/sessions/foreign/report',
    '/sessions/foreign/metrics','/sessions/foreign/lesson','/sessions/foreign/lesson/jobs',
    '/sessions/foreign/speech/1','/artifacts/foreign/png','/sources/foreign','/plans/foreign','/jobs/foreign',
    '/users/account-b/sources',
    '/sources/github','/sources/upload','/plans/jobs',
])
def test_cross_account_reads_return_404_before_handler(secured,path):
    response=secured.get('/api/v2'+path)
    assert response.status_code==404
    assert response.headers['cache-control']=='no-store'


@pytest.mark.parametrize('path',[
    '/sessions/foreign/events','/sessions/foreign/lab','/sessions/foreign/turns',
    '/sessions/foreign/board','/sessions/foreign/pair','/sessions/foreign/audio',
    '/sessions/foreign/end','/sessions/foreign/pause','/sessions/foreign/hint',
    '/sessions/foreign/reply-complete','/sessions/foreign/lesson/jobs',
    '/jobs/foreign/retry','/jobs/foreign/cancel','/sources/foreign/extract','/sources/foreign/confirm',
    '/sources/github/extract','/sources/upload/confirm',
])
def test_cross_account_writes_cannot_reach_generation_or_tools(secured,path):
    assert secured.post('/api/v2'+path,headers=HEADER,json={}).status_code==404


def test_owned_event_read_is_not_blocked_and_is_private(secured,monkeypatch):
    monkeypatch.setattr(db,'one',AsyncMock(return_value={'user_id':ACCOUNT['id']}))
    monkeypatch.setattr(service,'events',AsyncMock(return_value=[]))
    response=secured.get('/api/v2/sessions/own/events')
    assert response.status_code==200 and response.json()==[]
    assert response.headers['cache-control']=='no-store'


def test_no_cookie_and_missing_protection_and_foreign_origin(secured,monkeypatch):
    monkeypatch.setattr(auth,'current',AsyncMock(return_value=None))
    assert secured.get('/api/v2/history').status_code==401
    assert secured.post('/api/v2/auth/login',json={}).status_code==403
    assert secured.post('/api/v2/auth/login',headers={**HEADER,'Origin':'https://attacker.example'},json={}).status_code==403
    assert secured.post('/api/v2/sources/upload?user_id=a',content=b'notes').status_code==403
    # Trusted cross-origin errors remain readable; untrusted origins get no CORS.
    allowed=secured.get('/api/v2/history',headers={'Origin':'http://127.0.0.1:5173'})
    assert allowed.headers['access-control-allow-origin']=='http://127.0.0.1:5173'
    assert allowed.headers['access-control-allow-credentials']=='true'
    assert secured.get('/api/v2/sessions/own/report',headers={'Sec-Fetch-Site':'same-site'}).status_code==403
    assert secured.get('/api/v2/sessions/own/speech/1',headers={'Sec-Fetch-Site':'cross-site'}).status_code==403


@pytest.mark.parametrize('path,body',[
    ('/plans',{'user_id':'account-b','role':'Engineer','companies':[],'struggles':[],'question':''}),
    ('/plans/jobs',{'user_id':'account-b','role':'Engineer','companies':[],'struggles':[],'question':''}),
    ('/sources',{'user_id':'account-b','kind':'notes','title':'Synthetic notes','body':'Test source'}),
    ('/sources/github',{'user_id':'account-b','url':'https://github.com/example/repo'}),
])
def test_client_identity_never_grants_write_access(secured,path,body):
    assert secured.post('/api/v2'+path,headers=HEADER,json=body).status_code==403


def test_binary_upload_and_track_and_retest_body_ownership(secured):
    assert secured.post('/api/v2/sources/upload?user_id=account-b&title=Synthetic',headers=HEADER,content=b'test').status_code==403
    assert secured.post('/api/v2/sessions',headers=HEADER,json={'track_id':'foreign','consent':True}).status_code==404
    assert secured.post('/api/v2/retests',headers=HEADER,json={'session_id':'foreign'}).status_code==404


@pytest.mark.parametrize('path',['/api/users','/api/sessions/foreign','/api/prepcrew/hardware/start'])
def test_legacy_api_disabled_by_default(secured,path):
    assert secured.get(path).status_code==404
    assert secured.post(path,json={}).status_code==404


@pytest.mark.parametrize('path',['/ws/v2/voice/foreign','/ws/v2/sessions/foreign','/ws/foreign'])
def test_foreign_owner_and_legacy_websockets_denied_before_accept(secured,path):
    with pytest.raises(WebSocketDisconnect) as error:
        with secured.websocket_connect(path):pass
    assert error.value.code==4404


def test_expired_cookie_denies_voice_before_provider_call(secured,monkeypatch):
    monkeypatch.setattr(auth,'current',AsyncMock(return_value=None))
    with pytest.raises(WebSocketDisconnect) as error:
        with secured.websocket_connect('/ws/v2/voice/own'):pass
    assert error.value.code==4401


def test_idle_event_socket_closes_on_logout_and_cancels_application(secured,monkeypatch):
    monkeypatch.setattr(db,'one',AsyncMock(return_value={'user_id':ACCOUNT['id']}))
    lookup=AsyncMock(return_value=ACCOUNT);monkeypatch.setattr(auth,'current',lookup)
    monkeypatch.setattr(auth,'SOCKET_CHECK_SECONDS',.02)
    monkeypatch.setattr(service,'require_session',AsyncMock(return_value={}))
    monkeypatch.setattr(service,'events',AsyncMock(return_value=[]))
    with secured.websocket_connect('/ws/v2/sessions/own') as socket:
        lookup.return_value=None
        assert socket.receive()['code']==4401


def test_paired_device_uses_its_existing_limited_capability_not_owner_cookie(secured,monkeypatch):
    monkeypatch.setattr(auth,'current',AsyncMock(return_value=None))
    async def paired(socket,code):
        await socket.accept();await socket.send_json({'synthetic_capability':code});await socket.close()
    monkeypatch.setattr(devices,'paired',paired)
    with secured.websocket_connect('/ws/v2/pair/one-use-code') as socket:
        assert socket.receive_json()=={'synthetic_capability':'one-use-code'}


def test_cookie_lookup_uses_only_hash_and_checks_expiry_and_soft_deletion(monkeypatch):
    from starlette.requests import HTTPConnection
    token='a'*43
    lookup=AsyncMock(return_value=ACCOUNT);monkeypatch.setattr(db,'one',lookup)
    conn=HTTPConnection({'type':'http','headers':[(b'cookie',f'{auth.COOKIE}={token}'.encode())]})
    assert asyncio.run(auth.current(conn))==ACCOUNT
    sql,value=lookup.call_args.args
    assert token not in value and value==auth.digest(token)
    assert 'expires_at>now()' in sql and 'deleted_at IS NULL' in sql


@pytest.mark.parametrize('email,password',[
    ('missing-at.example','twelve-character-password'),('a@b.test','short'),('a@b.test','a'*257),
])
def test_invalid_credentials_are_bounded(email,password):
    with pytest.raises(ValidationError):auth.Credentials(email=email,password=password)


def test_passwords_are_argon2id_not_plaintext_and_email_is_normalized():
    credentials=auth.Credentials(email='  Candidate@Example.test  ',password='synthetic-password-123')
    assert credentials.email=='candidate@example.test'
    hashed=auth.hasher.hash(credentials.password)
    assert hashed.startswith('$argon2id$') and credentials.password not in hashed
    assert auth.hasher.verify(hashed,credentials.password)


def test_unknown_ownership_tables_are_never_interpolated():
    with pytest.raises(RuntimeError):asyncio.run(auth.require_owner('a','untrusted;DROP TABLE users','x'))
