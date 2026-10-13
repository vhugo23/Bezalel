"""Cached ElevenLabs clips for the fixed authored demo, never arbitrary account text."""
import asyncio
import hashlib
import json
import os
from pathlib import Path
from fastapi import HTTPException
from fastapi.responses import Response
from app import config
from . import db, demo_autoplay, service, voice

# Adam is an ElevenLabs documented pre-made voice. Override for an account-specific voice.
DEFAULT_CANDIDATE='pNInz6obpgDQGcFmaJgB'
CACHE_DIRECTORY=service.ROOT/'.artifacts'/'demo-speech'
_lock=asyncio.Lock()
MAX_CLIP_BYTES=8_000_000


def voice_for(role):
    dana=config.ELEVENLABS_VOICE_ID
    candidate=os.getenv('ELEVENLABS_DEMO_CANDIDATE_VOICE_ID',DEFAULT_CANDIDATE).strip() or DEFAULT_CANDIDATE
    if not dana:raise HTTPException(503,'Configure ELEVENLABS_VOICE_ID for Dana.')
    if candidate==dana:raise HTTPException(503,'Set ELEVENLABS_DEMO_CANDIDATE_VOICE_ID to a different voice from Dana.')
    return candidate if role=='candidate' else dana


def allowed(role,text):
    if role=='candidate':return text in demo_autoplay.CANDIDATE_UTTERANCES
    if role!='interviewer':return False
    return text in {*demo_autoplay.DEMO_OPENINGS.values(),*demo_autoplay.PI_REPLIES,
        *(text for replies in demo_autoplay.DESIGN_REPLIES for text in replies),
        *(mark['speech'] for mark in service.DEMO_CRITIQUE['marks'])}


async def speech(sid,seq):
    session,_=await demo_autoplay.supported(sid)
    if not session['engine_state'].get('scripted_demo'):
        raise HTTPException(409,'Start scripted playback before requesting demo audio.')
    event=await db.one("SELECT actor,payload FROM session_events WHERE session_id=$1 AND seq=$2 AND kind='turn'",sid,seq)
    if not event:raise HTTPException(404,'Saved demo utterance not found.')
    role,text=event['actor'],event['payload'].get('text','')
    if not allowed(role,text) or len(text)>900:
        raise HTTPException(422,'This saved utterance is not part of the authored demo audio.')
    voice_id=voice_for(role)
    model=config.ELEVENLABS_MODEL or 'eleven_flash_v2_5'
    key=hashlib.sha256(json.dumps([voice_id,model,'mp3_44100_128',text]).encode()).hexdigest()
    path=CACHE_DIRECTORY/(key+'.mp3')
    hit=False
    async with _lock:
        if path.is_file() and 0<path.stat().st_size<=MAX_CLIP_BYTES:
            audio=path.read_bytes();hit=True
        else:
            response=await voice.speak(sid,text,voice_id=voice_id)
            data=bytearray()
            async for chunk in response.body_iterator:
                data.extend(chunk)
                if len(data)>MAX_CLIP_BYTES:
                    await response.body_iterator.aclose()
                    raise HTTPException(503,'Demo voice clip exceeded the supported size.')
            if not data:raise HTTPException(503,'ElevenLabs returned no demo audio. The transcript is saved.')
            audio=bytes(data)
            CACHE_DIRECTORY.mkdir(parents=True,exist_ok=True)
            pending=path.with_suffix('.tmp');pending.write_bytes(audio);pending.replace(path)
    return Response(audio,media_type='audio/mpeg',headers={'Cache-Control':'private, max-age=86400',
        'X-PrepCrew-Speech-Provider':'elevenlabs','X-PrepCrew-Speech-Role':role,
        'X-PrepCrew-Speech-Cache':'hit' if hit else 'miss'})
