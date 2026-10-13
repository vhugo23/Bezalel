"""Account-scoped model and speech configuration. Secrets never leave this module."""
import json
import os
import re
from pathlib import Path
from urllib.parse import urlsplit
from cryptography.fernet import Fernet, InvalidToken
from fastapi import APIRouter, HTTPException, Request, Response
from pydantic import BaseModel, Field, model_validator
from typing import Literal
from app import config
from . import db

router=APIRouter(prefix='/api/v2/providers',tags=['Connections'])
ROOT=Path(__file__).resolve().parents[3]
HOSTS={'api.openai.com','openrouter.ai','api.groq.com','api.mistral.ai','api.deepseek.com'}
_transport=None

class Settings(BaseModel):
    llm: Literal['none','gemini','openai','anthropic','compatible']='none'
    model: str=Field(default='',max_length=160)
    evaluator_model: str=Field(default='',max_length=160)
    base_url: str=Field(default='https://api.openai.com/v1',max_length=500)
    stt: Literal['local','elevenlabs','openai']='local'
    stt_model: str=Field(default='gpt-4o-mini-transcribe',max_length=160)
    tts: Literal['local','elevenlabs','openai','browser']='local'
    tts_model: str=Field(default='gpt-4o-mini-tts',max_length=160)
    voice: str=Field(default='coral',max_length=160)
    elevenlabs_voice: str=Field(default='',max_length=160)
    kokoro_voice: Literal['af_heart','af_bella','af_nicole','af_sarah']='af_heart'
    parakeet: Literal['balanced','quantized']='quantized'

    @model_validator(mode='after')
    def valid(self):
        self.model=self.model.strip()
        if self.llm!='none' and not self.model:raise ValueError('Choose a model ID for your interviewer.')
        if self.llm=='compatible':self.base_url=validate_url(self.base_url)
        if self.tts=='elevenlabs' and not re.fullmatch(r'[A-Za-z0-9_-]{1,160}',self.elevenlabs_voice):
            raise ValueError('Enter your ElevenLabs voice ID.')
        return self

class Update(Settings):
    llm_key: str=Field(default='',max_length=1000)
    openai_speech_key: str=Field(default='',max_length=1000)
    elevenlabs_key: str=Field(default='',max_length=1000)

def validate_url(value):
    parsed=urlsplit(value.strip().rstrip('/'))
    allowed=HOSTS|{s.strip() for s in os.getenv('PREPCREW_PROVIDER_HOSTS','').split(',') if s.strip()}
    local=os.getenv('PREPCREW_LOCAL_APP')=='true' and parsed.hostname in {'localhost','127.0.0.1','::1'}
    if parsed.username or parsed.password or parsed.query or parsed.fragment or not parsed.hostname:
        raise ValueError('Use a provider base URL without credentials, query or fragment.')
    if not local and (parsed.scheme!='https' or parsed.hostname not in allowed or parsed.port not in (None,443)):
        raise ValueError('Use a supported provider host. A self-hosted administrator can allow another host with PREPCREW_PROVIDER_HOSTS.')
    if local and parsed.scheme not in {'http','https'}:raise ValueError('Use HTTP or HTTPS for your local endpoint.')
    return value.strip().rstrip('/')

def cipher():
    key=os.getenv('PREPCREW_ENCRYPTION_KEY','')
    if not key:
        directory=Path(os.getenv('PREPCREW_DATA_DIR',str(ROOT/'.artifacts')))
        directory.mkdir(parents=True,exist_ok=True)
        path=directory/'provider.key'
        try:
            fd=os.open(path,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600)
            with os.fdopen(fd,'wb') as file:file.write(Fernet.generate_key())
        except FileExistsError:pass
        key=path.read_bytes()
    return Fernet(key)

def encrypt(value):return cipher().encrypt(json.dumps(value).encode()).decode()

def decrypt(value):
    try:return json.loads(cipher().decrypt(value.encode()))
    except (InvalidToken,ValueError,TypeError):
        raise HTTPException(503,'Saved connections could not be unlocked. Restore the app encryption key or reconnect your providers.')

async def profile(owner):
    row=await db.one('SELECT settings,credentials FROM provider_settings WHERE user_id=$1',owner)
    if not row or not isinstance(row.get('settings'),dict):return None
    return Settings.model_validate(row['settings']),decrypt(row['credentials'])

def owner(request):
    account=getattr(request.state,'account',None)
    if not account:raise HTTPException(401,'Sign in to manage your connections.')
    return account['id']

def public(settings,keys):
    return {**settings.model_dump(),'has_llm_key':bool(keys.get('llm_key')),
        'has_openai_speech_key':bool(keys.get('openai_speech_key')),
        'has_elevenlabs_key':bool(keys.get('elevenlabs_key')),
        'ready':settings.llm!='none' and bool(keys.get('llm_key') or
            settings.llm=='compatible' and urlsplit(settings.base_url).hostname in {'localhost','127.0.0.1','::1'})}

@router.get('')
async def read(request:Request,response:Response):
    response.headers['Cache-Control']='no-store'
    saved=await profile(owner(request))
    return public(*(saved or (Settings(),{})))

@router.put('')
async def save(body:Update,request:Request):
    uid=owner(request);old=await profile(uid)
    keys=old[1] if old else {}
    if old and old[0].llm!=body.llm:keys.pop('llm_key',None)
    for key in ('llm_key','openai_speech_key','elevenlabs_key'):
        if getattr(body,key).strip():keys[key]=getattr(body,key).strip()
    settings=Settings.model_validate(body.model_dump())
    if settings.llm!='none' and not public(settings,keys)['ready']:raise HTTPException(422,'Add an API key for the selected model provider.')
    if (settings.stt=='elevenlabs' or settings.tts=='elevenlabs') and not keys.get('elevenlabs_key'):
        raise HTTPException(422,'Add an ElevenLabs key or choose local speech.')
    if (settings.stt=='openai' or settings.tts=='openai') and not keys.get('openai_speech_key'):
        if settings.llm=='openai' and keys.get('llm_key'):keys['openai_speech_key']=keys['llm_key']
        else:raise HTTPException(422,'Add an OpenAI speech key or choose local speech.')
    await db.execute('''INSERT INTO provider_settings(user_id,settings,credentials) VALUES($1,$2,$3)
        ON CONFLICT(user_id) DO UPDATE SET settings=excluded.settings,credentials=excluded.credentials,updated_at=now()''',
        uid,settings.model_dump(),encrypt(keys))
    return public(settings,keys)

@router.delete('')
async def disconnect(request:Request):
    await db.execute('DELETE FROM provider_settings WHERE user_id=$1',owner(request))
    return {'disconnected':True}

class ConnectionProbe(BaseModel):
    reply: str=Field(min_length=1,max_length=200)

@router.post('/test')
async def test_connection(request:Request):
    from .generation import generate, DEMO
    if DEMO:raise HTTPException(409,'Connection testing requires live mode. Start the app without --demo.')
    uid=owner(request)
    result,_,source=await generate('connection_probe',uid,
        'Return a brief greeting from Dana, an engineering practice interviewer. No questions or claims about a candidate.',
        ConnectionProbe,subject_type='connection',user_id=uid)
    return {'connected':True,'provider':source,'reply':result.reply}

async def session_profile(sid):
    session=await db.one('SELECT user_id FROM sessions WHERE id=$1',sid)
    return await profile(session['user_id']) if session and session.get('user_id') else None

async def for_subject(subject,subject_type,user_id=None):
    if not user_id:
        table={'session':'sessions','plan':'plans','source':'source_documents'}.get(subject_type)
        if table:
            row=await db.one(f'SELECT user_id FROM {table} WHERE id=$1',subject)
            user_id=row.get('user_id') if row else None
    return await profile(user_id) if user_id else None

async def configuration_fingerprint(owner):
    import hashlib
    row=await db.one('SELECT settings FROM provider_settings WHERE user_id=$1',owner)
    if not row or not isinstance(row.get('settings'),dict):return None
    fields={k:v for k,v in row['settings'].items() if k in ('llm','model','evaluator_model','base_url')}
    return hashlib.sha256(json.dumps(fields,sort_keys=True).encode()).hexdigest()
