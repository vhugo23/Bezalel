import asyncio
import json
from types import SimpleNamespace
from unittest.mock import AsyncMock
import httpx
import pytest
from fastapi import HTTPException
from app import config
from app.v2 import providers, model_transport, generation, observation, speech_connections, voice


def test_credentials_are_encrypted_and_invalid_keys_fail_closed(monkeypatch,tmp_path):
    monkeypatch.setenv('PREPCREW_DATA_DIR',str(tmp_path))
    monkeypatch.delenv('PREPCREW_ENCRYPTION_KEY',raising=False)
    encrypted=providers.encrypt({'llm_key':'synthetic-secret'})
    assert 'synthetic-secret' not in encrypted
    assert providers.decrypt(encrypted)=={'llm_key':'synthetic-secret'}
    monkeypatch.setenv('PREPCREW_ENCRYPTION_KEY',providers.Fernet.generate_key().decode())
    with pytest.raises(HTTPException) as exc:providers.decrypt(encrypted)
    assert exc.value.status_code==503 and 'synthetic-secret' not in str(exc.value)


@pytest.mark.parametrize('url',['http://api.openai.com/v1','https://169.254.169.254/latest','https://api.openai.com.evil.test/v1','https://key@api.openai.com/v1','https://api.openai.com:123/v1','https://api.openai.com/v1?api_key=secret'])
def test_custom_endpoints_cannot_target_unapproved_or_credentialed_hosts(monkeypatch,url):
    monkeypatch.delenv('PREPCREW_PROVIDER_HOSTS',raising=False)
    monkeypatch.setenv('PREPCREW_LOCAL_APP','false')
    with pytest.raises(ValueError):providers.validate_url(url)


def test_local_models_are_allowed_only_in_local_app_mode(monkeypatch):
    monkeypatch.setenv('PREPCREW_LOCAL_APP','true')
    assert providers.validate_url('http://127.0.0.1:11434/v1')=='http://127.0.0.1:11434/v1'
    monkeypatch.setenv('PREPCREW_LOCAL_APP','false')
    with pytest.raises(ValueError):providers.validate_url('http://127.0.0.1:11434/v1')


def request(owner):return SimpleNamespace(state=SimpleNamespace(account={'id':owner}))


def test_save_keeps_blank_existing_key_and_never_returns_secrets(monkeypatch,tmp_path):
    monkeypatch.setenv('PREPCREW_DATA_DIR',str(tmp_path))
    monkeypatch.delenv('PREPCREW_ENCRYPTION_KEY',raising=False)
    settings=providers.Settings(llm='openai',model='model-for-test')
    monkeypatch.setattr(providers,'profile',AsyncMock(return_value=(settings,{'llm_key':'synthetic-secret'})))
    execute=AsyncMock();monkeypatch.setattr(providers.db,'execute',execute)
    result=asyncio.run(providers.save(providers.Update(llm='openai',model='new-model'),request('owner-a')))
    assert result['ready'] and result['has_llm_key']
    assert 'synthetic-secret' not in json.dumps(result)
    assert execute.call_args.args[1]=='owner-a'
    assert providers.decrypt(execute.call_args.args[3])['llm_key']=='synthetic-secret'


def test_changing_model_provider_does_not_reuse_another_vendors_key(monkeypatch):
    monkeypatch.setattr(providers,'profile',AsyncMock(return_value=(providers.Settings(llm='openai',model='test'),{'llm_key':'synthetic-secret'})))
    with pytest.raises(HTTPException) as exc:
        asyncio.run(providers.save(providers.Update(llm='anthropic',model='test'),request('owner')))
    assert exc.value.status_code==422


@pytest.mark.parametrize('provider',['openai','anthropic','compatible'])
def test_native_model_transports_send_correct_auth_schema_and_images(monkeypatch,provider):
    seen=[]
    def reply(req):
        body=json.loads(req.content);seen.append((req,body))
        if provider=='openai':
            assert body['store'] is False and body['text']['format']['schema']['type']=='object'
            assert body['input'][0]['content'][1]['type']=='input_image'
            return httpx.Response(200,json={'output':[{'type':'message','content':[{'type':'output_text','text':'{"reply":"hello"}'}]}],'usage':{'input_tokens':2,'output_tokens':3}})
        if provider=='anthropic':
            assert body['output_config']['format']['type']=='json_schema'
            assert body['messages'][0]['content'][1]['source']['media_type']=='image/png'
            return httpx.Response(200,json={'content':[{'type':'text','text':'{"reply":"hello"}'}]})
        assert body['response_format']['type']=='json_object'
        return httpx.Response(200,json={'choices':[{'message':{'content':'{"reply":"hello"}'}}]})
    monkeypatch.setattr(providers,'_transport',httpx.MockTransport(reply))
    settings=providers.Settings(llm=provider,model='test-model')
    result=asyncio.run(model_transport.generate(settings,{'llm_key':'synthetic-secret'},'test-model','prompt',{'type':'object'},b'png'))
    assert json.loads(result[0])=={'reply':'hello'}
    assert seen[0][0].headers.get('x-api-key' if provider=='anthropic' else 'authorization')==('synthetic-secret' if provider=='anthropic' else 'Bearer synthetic-secret')


def test_provider_error_excludes_response_bodies_and_keys(monkeypatch):
    monkeypatch.setattr(providers,'_transport',httpx.MockTransport(lambda req:httpx.Response(401,json={'detail':'sensitive-provider-body'})))
    with pytest.raises(model_transport.ProviderFailure) as exc:
        asyncio.run(model_transport.generate(providers.Settings(llm='openai',model='test'),{'llm_key':'secret'},'test','prompt',{'type':'object'}))
    assert exc.value.code==401 and 'sensitive' not in str(exc.value) and 'secret' not in str(exc.value)


def test_parallel_generations_use_their_owners_provider_keys(monkeypatch):
    monkeypatch.setattr(config,'DATABASE_URL','synthetic-database')
    monkeypatch.setattr(generation,'DEMO',False)
    monkeypatch.setattr(generation.db,'execute',AsyncMock())
    async def select(subject,kind,owner):
        return providers.Settings(llm='openai',model='model-'+owner),{'llm_key':'key-'+owner}
    monkeypatch.setattr(providers,'for_subject',select)
    calls=[]
    async def generate(settings,keys,model,prompt,*args,**kwargs):
        calls.append((model,keys['llm_key']))
        await asyncio.sleep(0)
        return '{"reply":"hello"}',1,1
    monkeypatch.setattr(model_transport,'generate',generate)
    async def run():
        return await asyncio.gather(*(generation.generate('connection_probe',owner,'prompt',providers.ConnectionProbe,subject_type='connection',user_id=owner) for owner in ('a','b')))
    assert all(result[0].reply=='hello' for result in asyncio.run(run()))
    assert set(calls)=={('model-a','key-a'),('model-b','key-b')}
    assert 'key-a' not in str(generation.db.execute.call_args_list)


def test_observation_only_uses_relevant_candidate_tool_evidence():
    def event(kind,actor='candidate',output=''):return SimpleNamespace(kind=kind,actor=actor,payload={'output':output})
    assert observation.relevant(event('command',output='HTTP/1.1 502 Bad Gateway'))
    assert observation.relevant(event('edit'))
    assert not observation.relevant(event('stroke'))
    assert not observation.relevant(event('command',actor='interviewer',output='502'))
    assert not observation.relevant(event('command',output='help text'))


def test_claude_transport_relaxes_wire_constraints_without_changing_the_original():
    schema=providers.ConnectionProbe.model_json_schema()
    converted=model_transport.claude_schema(schema)
    assert converted['additionalProperties'] is False
    assert 'maxLength' not in converted['properties']['reply']
    assert 'maxLength' in converted['properties']['reply']['description']
    assert schema['properties']['reply']['maxLength']==200


def test_openai_speech_uses_the_accounts_key_and_selected_voice(monkeypatch):
    selected=providers.Settings(llm='openai',model='test',tts='openai',voice='coral')
    monkeypatch.setattr(voice,'job',AsyncMock(return_value='job'))
    audit=AsyncMock();monkeypatch.setattr(speech_connections.db,'execute',audit)
    def respond(req):
        assert req.headers['authorization']=='Bearer synthetic-speech-key'
        assert json.loads(req.content)['voice']=='coral'
        return httpx.Response(200,content=b'synthetic-audio')
    monkeypatch.setattr(providers,'_transport',httpx.MockTransport(respond))
    result=asyncio.run(speech_connections.speak('session','Saved interviewer reply',selected,{'openai_speech_key':'synthetic-speech-key'}))
    assert result.media_type=='audio/mpeg' and result.body==b'synthetic-audio'
    assert 'synthetic-speech-key' not in str(audit.call_args_list)


def test_cloud_transcription_is_audited_for_the_current_step_and_consumed_as_evidence(monkeypatch):
    from starlette.requests import Request
    settings=providers.Settings(llm='openai',model='test',stt='openai')
    monkeypatch.setattr(providers,'session_profile',AsyncMock(return_value=(settings,{'openai_speech_key':'synthetic-key'})))
    monkeypatch.setattr(speech_connections.service,'require_session',AsyncMock(return_value={'status':'live','step':2,'engine_state':{}}))
    monkeypatch.setattr(voice,'job',AsyncMock(return_value='transcription-job'))
    audit=AsyncMock();monkeypatch.setattr(speech_connections.db,'execute',audit)
    monkeypatch.setattr(providers,'_transport',httpx.MockTransport(lambda req:httpx.Response(200,json={'text':'I checked the service before changing the proxy.'})))
    async def receive():return {'type':'http.request','body':b'RIFF'+bytes(4)+b'WAVE'+bytes(32),'more_body':False}
    request=Request({'type':'http','method':'POST','path':'/','headers':[]},receive)
    result=asyncio.run(speech_connections.transcribe('session',request))
    assert result['inference_id']=='transcription-job' and result['text'].startswith('I checked')
    assert any(call.args[2]=={'execution':'cloud_segment','step':2} for call in audit.call_args_list if len(call.args)>2)
    assert 'synthetic-key' not in str(audit.call_args_list)

def test_connection_validation_does_not_echo_credential_input():
    from fastapi.exceptions import RequestValidationError
    from app.main import validation_error
    error=RequestValidationError([{'type':'value_error','loc':('body',),'msg':'Choose a model',
        'input':{'llm_key':'synthetic-private-key'},'ctx':{'error':ValueError('bad')}}])
    response=asyncio.run(validation_error(SimpleNamespace(url=SimpleNamespace(path='/api/v2/providers')),error))
    assert response.status_code==422
    assert b'synthetic-private-key' not in response.body
    assert json.loads(response.body)['detail'][0]['msg']=='Choose a model'


def test_whiteboard_storage_uses_persistent_app_directory(monkeypatch,tmp_path):
    from app.v2 import service
    monkeypatch.setenv('PREPCREW_DATA_DIR',str(tmp_path))
    assert service.artifact_directory()==tmp_path/'artifacts'
    monkeypatch.delenv('PREPCREW_DATA_DIR')
    assert service.artifact_directory()==service.ROOT/'.artifacts'
