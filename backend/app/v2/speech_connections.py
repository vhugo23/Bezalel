"""Saved speech choices, native OpenAI audio, and bounded utterance transcription."""
import time
from fastapi import APIRouter, Request, Response, HTTPException
import httpx
from . import db, providers, service, voice

router=APIRouter(prefix='/api/v2',tags=['Speech connections'])

@router.get('/sessions/{sid}/voice-options')
async def options(sid:str):
    await service.require_session(sid)
    saved=await providers.session_profile(sid)
    if not saved:
        from app import config
        return {'stt':'elevenlabs' if config.ELEVENLABS_API_KEY else 'local',
            'tts':'elevenlabs' if config.ELEVENLABS_API_KEY and config.ELEVENLABS_VOICE_ID else 'browser',
            'kokoro_voice':'af_heart','parakeet':'quantized','ready':bool(config.GEMINI_API_KEY)}
    return providers.public(*saved)

async def speak(sid,text,settings,keys):
    jid=await voice.job(sid,'tts',settings.tts_model);began=time.perf_counter()
    try:
        async with httpx.AsyncClient(timeout=35,trust_env=False,follow_redirects=False,transport=providers._transport) as client:
            result=await client.post('https://api.openai.com/v1/audio/speech',
                headers={'Authorization':'Bearer '+keys['openai_speech_key']},
                json={'model':settings.tts_model,'input':text,'voice':settings.voice,'response_format':'mp3'})
        if not result.is_success:raise HTTPException(503,'Your speech provider could not synthesize this reply. Check Connections and your quota.')
        await db.execute("UPDATE generation_jobs SET status='succeeded',latency_ms=$2,finished_at=now() WHERE id=$1",jid,round((time.perf_counter()-began)*1000))
        return Response(result.content,media_type='audio/mpeg',headers={'Cache-Control':'no-store'})
    except BaseException:
        await voice.failed(jid,'Speech synthesis failed or was interrupted')
        raise

@router.post('/sessions/{sid}/transcriptions')
async def transcribe(sid:str,request:Request):
    session=await service.require_session(sid)
    if session['status']!='live' or session['engine_state'].get('paused'):raise HTTPException(409,'Resume a live session first.')
    saved=await providers.session_profile(sid)
    if not saved or saved[0].stt!='openai':raise HTTPException(409,'Choose OpenAI speech recognition in Connections first.')
    settings,keys=saved
    data=bytearray()
    async for chunk in request.stream():
        data.extend(chunk)
        if len(data)>1_000_000:raise HTTPException(413,'Keep speech segments under 30 seconds.')
    if len(data)<44 or not data.startswith(b'RIFF') or data[8:12]!=b'WAVE':raise HTTPException(422,'Send a WAV speech segment.')
    jid=await voice.job(sid,'stt',settings.stt_model);began=time.perf_counter()
    await db.execute("UPDATE generation_jobs SET request=$2 WHERE id=$1",jid,
        {'execution':'cloud_segment','step':session['step']})
    try:
        async with httpx.AsyncClient(timeout=20,trust_env=False,follow_redirects=False,transport=providers._transport) as client:
            result=await client.post('https://api.openai.com/v1/audio/transcriptions',
                headers={'Authorization':'Bearer '+keys['openai_speech_key']},
                data={'model':settings.stt_model},files={'file':('speech.wav',bytes(data),'audio/wav')})
        if not result.is_success:raise HTTPException(503,'Your speech provider could not transcribe this segment. Check Connections and your quota.')
        text=result.json().get('text','')
        if not isinstance(text,str) or len(text)>5000:raise HTTPException(503,'Your speech provider returned an invalid transcript.')
        await db.execute("UPDATE generation_jobs SET status='succeeded',response=$2,latency_ms=$3,stage='Browser inference completed',finished_at=now() WHERE id=$1",jid,
            {'text':text,'provider':'openai'},round((time.perf_counter()-began)*1000))
        return {'text':text,'inference_id':jid}
    except BaseException:
        await voice.failed(jid,'Transcription failed or was interrupted')
        raise
