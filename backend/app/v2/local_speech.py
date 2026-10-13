"""Audit browser inference without representing client reports as provider proof."""
from typing import Literal
from pydantic import BaseModel, Field
from fastapi import HTTPException
from . import db, voice, service as s

MODELS={'stt':'parakeet.js/1.4.4/tdt-0.6b-v3/f88260fa/webgpu-encoder-wasm-decoder',
        'tts':'kokoro-js/1.2.1/Kokoro-82M-v1.0/fp32/webgpu/af_heart'}


class LocalSpeechStart(BaseModel):
    kind: Literal['stt','tts']
    seq: int | None = Field(default=None,ge=1)


class LocalSpeechFinish(BaseModel):
    status: Literal['succeeded','failed']
    text: str = Field(default='',max_length=5000)
    latency_ms: int = Field(default=0,ge=0,le=600_000)


class LocalSpeechJob(BaseModel):
    id: str
    text: str = ''


async def start(sid,body):
    session=await s.require_session(sid)
    if body.kind=='stt' and (session['status']!='live' or session['engine_state'].get('paused')):
        raise HTTPException(409,'Resume a live interview before using local speech.')
    text=''
    if body.kind=='tts':
        event=await db.one("SELECT payload FROM session_events WHERE session_id=$1 AND seq=$2 AND kind IN ('turn','hint') AND actor='interviewer'",sid,body.seq)
        if not event:raise HTTPException(404,'Interviewer turn not found.')
        text=event['payload']['text']
    model=MODELS[body.kind]
    if body.kind=='tts':
        from app import config
        from . import providers
        selected=await providers.session_profile(sid) if config.DATABASE_URL else None
        if selected:model=model.rsplit('/',1)[0]+'/'+selected[0].kokoro_voice
    jid=await voice.job(sid,body.kind,model)
    await db.execute("UPDATE generation_jobs SET request=$2,stage='Browser inference' WHERE id=$1",jid,
        {'execution':'browser','client_reported':True,'seq':body.seq,'step':session['step']})
    return LocalSpeechJob(id=jid,text=text)


async def finish(sid,jid,body):
    # A conditional UPDATE prevents retries or forged cross-session IDs changing results.
    row=await db.one("""UPDATE generation_jobs SET status=$3,response=$4,latency_ms=$5,
        error=$6,stage='Browser inference completed',finished_at=now()
        WHERE id=$1 AND subject_id=$2 AND subject_type='session' AND status='running'
        AND request->>'execution'='browser' RETURNING id""",jid,sid,body.status,
        {'text':body.text,'client_reported':True},body.latency_ms,
        'Browser inference failed or cancelled' if body.status=='failed' else None)
    if not row:raise HTTPException(409,'Local inference is already finished or does not belong to this session.')
    return LocalSpeechJob(id=jid)


async def consume_transcript(sid,jid,text,final):
    session=await s.require_session(sid)
    row=await db.one("""UPDATE generation_jobs SET stage='Browser transcript consumed'
        WHERE id=$1 AND subject_id=$2 AND subject_type='session' AND kind='stt'
        AND status='succeeded' AND request->>'execution' IN ('browser','cloud_segment')
        AND (request->>'step')::int=$4 AND response->>'text'=$3
        AND stage='Browser inference completed' RETURNING id""",jid,sid,text,session['step'])
    if not row:raise HTTPException(409,'Local transcript is stale, already used or unaudited.')
    return jid
