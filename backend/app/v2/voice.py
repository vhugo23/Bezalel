"""ElevenLabs transport with audited calls and errors before audio response headers."""
import asyncio
import time
from uuid import uuid4
import httpx
from fastapi import HTTPException
from fastapi.responses import StreamingResponse
from app import config
from . import db


def provider_error(status: int, code: str = '') -> HTTPException:
    if code == 'missing_permissions':
        return HTTPException(503, 'The ElevenLabs key lacks permission for this operation. Enable speech-to-text and text-to-speech access on the key.')
    if status == 401:
        return HTTPException(503, 'ElevenLabs rejected the API key. Update ELEVENLABS_API_KEY in the root .env and restart the server.')
    if status == 403:
        return HTTPException(503, 'ElevenLabs denied this request. Check the API key permissions and voice access.')
    if status in (402, 429):
        return HTTPException(503, 'ElevenLabs quota or rate limit reached. Try again shortly or check your account.')
    return HTTPException(503, 'ElevenLabs is unavailable. Your saved transcript is still available.')


def error_code(response: httpx.Response) -> str:
    try:
        return response.json().get('detail',{}).get('status','')
    except (ValueError,AttributeError):
        return ''


async def job(sid: str, kind: str, model: str) -> str:
    jid = str(uuid4())
    await db.execute("INSERT INTO generation_jobs(id,kind,subject_type,subject_id,status,model) VALUES($1,$2,'session',$3,'running',$4)",jid,kind,sid,model)
    return jid


async def failed(jid: str, message: str):
    await db.execute("UPDATE generation_jobs SET status='failed',error=$2,finished_at=now() WHERE id=$1",jid,message)


async def transcribe(sid: str, data: bytes, mime: str) -> str:
    if not config.ELEVENLABS_API_KEY: raise HTTPException(503,'ELEVENLABS_API_KEY is missing from the server .env.')
    if not data: raise HTTPException(422,'No audio was recorded. Please try again.')
    if mime.split(';')[0] not in ('audio/webm','audio/mp4','audio/ogg','audio/wav','audio/mpeg'):
        raise HTTPException(415,'Unsupported audio recording format.')
    model=config.ELEVENLABS_STT_MODEL
    jid=await job(sid,'stt',model); started=time.perf_counter()
    extension={'audio/mp4':'mp4','audio/wav':'wav','audio/ogg':'ogg','audio/mpeg':'mp3'}.get(mime.split(';')[0],'webm')
    try:
        async with httpx.AsyncClient(timeout=httpx.Timeout(30,connect=10)) as client:
            response=await client.post('https://api.elevenlabs.io/v1/speech-to-text',
                headers={'xi-api-key':config.ELEVENLABS_API_KEY},
                data={'model_id':model,'tag_audio_events':'false'},
                files={'file':(f'turn.{extension}',data,mime)})
        if not response.is_success: raise provider_error(response.status_code,error_code(response))
        text=str(response.json().get('text','')).strip()
        if not text: raise HTTPException(422,'No speech was detected. Please try again.')
        elapsed=(time.perf_counter()-started)*1000
        await db.execute("UPDATE generation_jobs SET status='succeeded',response=$2,latency_ms=$3,finished_at=now() WHERE id=$1",jid,{'text':text},round(elapsed))
        await db.execute("INSERT INTO metrics(session_id,name,value) VALUES($1,'stt_ms',$2)",sid,elapsed)
        return text
    except HTTPException as exc:
        await failed(jid,str(exc.detail));raise
    except Exception:
        await failed(jid,'Transcription transport failed')
        raise HTTPException(503,'Transcription failed. Please try again or type your answer.')


async def speak(sid: str, text: str):
    if not config.ELEVENLABS_API_KEY or not config.ELEVENLABS_VOICE_ID:
        raise HTTPException(503,'Configure ELEVENLABS_API_KEY and ELEVENLABS_VOICE_ID in the root .env.')
    model=config.ELEVENLABS_MODEL or 'eleven_flash_v2_5'
    jid=await job(sid,'tts',model);started=time.perf_counter()
    client=httpx.AsyncClient(timeout=httpx.Timeout(35,connect=10))
    response=None
    try:
        request=client.build_request('POST',f'https://api.elevenlabs.io/v1/text-to-speech/{config.ELEVENLABS_VOICE_ID}/stream',
            params={'output_format':'mp3_44100_128'},headers={'xi-api-key':config.ELEVENLABS_API_KEY},
            json={'text':text,'model_id':model})
        response=await client.send(request,stream=True)
        if not response.is_success:
            await response.aread()
            raise provider_error(response.status_code,error_code(response))
    except Exception as exc:
        if response: await response.aclose()
        await client.aclose();await failed(jid,'Voice provider request failed')
        if isinstance(exc,HTTPException): raise
        raise HTTPException(503,'Dana’s voice could not connect. Her transcript is saved.')

    async def chunks():
        first=True
        try:
            async for chunk in response.aiter_bytes():
                if not chunk: continue
                if first:
                    await db.execute("INSERT INTO metrics(session_id,name,value) VALUES($1,'tts_first_byte_ms',$2)",sid,(time.perf_counter()-started)*1000)
                    first=False
                yield chunk
            await db.execute("UPDATE generation_jobs SET status='succeeded',latency_ms=$2,finished_at=now() WHERE id=$1",jid,round((time.perf_counter()-started)*1000))
        except (Exception,asyncio.CancelledError):
            await asyncio.shield(failed(jid,'Voice stream stopped before completion'))
            raise
        finally:
            await response.aclose();await client.aclose()
    return StreamingResponse(chunks(),media_type='audio/mpeg',headers={'Cache-Control':'no-store'})
