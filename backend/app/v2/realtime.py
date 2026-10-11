"""Continuous STT relay and interruptible interviewer. No browser provider credentials."""
import asyncio
import base64
import json
import logging
import re
import time
from urllib.parse import urlencode
from contextlib import suppress
from pydantic import BaseModel, Field, ValidationError
from typing import Literal
from fastapi import WebSocket, WebSocketDisconnect, HTTPException
from websockets.asyncio.client import connect
from websockets.exceptions import InvalidStatus, ConnectionClosed
from app import config
from . import db, service as s, voice
from .models import TurnInput

PARAMS = {
    'model_id':'scribe_v2_realtime', 'audio_format':'pcm_16000',
    'commit_strategy':'vad', 'vad_silence_threshold_secs':'1.2',
    'min_speech_duration_ms':'250', 'min_silence_duration_ms':'200',
    'filter_background_audio':'true', 'keepalive_interval_ms':'1000',
}
ACTIVE = set()  # The local app runs one uvicorn worker.
logger=logging.getLogger(__name__)


class ProviderStreamError(HTTPException):
    def __init__(self,code,message):
        super().__init__(503,message)
        self.code=code


def check_provider_message(message):
    """Provider error bodies may contain sensitive data; return only authored text."""
    messages={
        'quota_exceeded':'ElevenLabs speech-to-text quota is exhausted. Add credits or use a key with available quota, then restart voice. You can keep working by typing.',
        'auth_error':'ElevenLabs rejected the speech-to-text credentials. Check the server API key and its speech-to-text permissions.',
        'rate_limited':'ElevenLabs speech-to-text rate limit reached. Wait a moment before restarting voice, or type your answer.',
        'throttled':'ElevenLabs has too many active voice sessions. Close another voice session before trying again.',
        'unaccepted_terms':'Accept the speech-to-text terms in your ElevenLabs account before starting voice.',
        'session_time_limit_exceeded':'This ElevenLabs voice session reached its time limit. Restart voice to continue; your transcript is saved.',
        'insufficient_audio_activity':'ElevenLabs ended the stream because it received too little audio. Restart voice, or continue by typing.',
        'input_error':'ElevenLabs could not process the microphone audio. Restart voice, or continue by typing.',
        'invalid_request':'ElevenLabs rejected the realtime voice settings. Your transcript is saved; continue by typing.',
        'chunk_size_exceeded':'ElevenLabs rejected an oversized audio frame. Restart voice, or continue by typing.',
    }
    kind=message.get('message_type','')
    if kind in messages:raise ProviderStreamError(kind,messages[kind])
    if kind in {'error','queue_overflow','resource_exhausted','transcriber_error'}:
        raise ProviderStreamError(kind,'ElevenLabs could not continue transcription. Try again shortly, or type your answer. Your transcript is saved.')


def failure_message(exc):
    if isinstance(exc,HTTPException):return str(exc.detail)
    if isinstance(exc,InvalidStatus):return str(voice.provider_error(exc.response.status_code).detail)
    if isinstance(exc,TimeoutError):return 'ElevenLabs voice connection timed out. Check your connection and restart voice, or type your answer.'
    if isinstance(exc,(ConnectionClosed,OSError)):
        return 'The ElevenLabs voice connection closed. Restart voice to reconnect; your saved turns are still here.'
    if isinstance(exc,ValidationError):return 'The voice client sent an invalid control message. Reload this page before restarting voice; your transcript is saved.'
    return 'Voice connection lost. Restart voice to reconnect; saved turns will stay in the conversation.'


class Command(BaseModel):
    type: Literal['interrupt','commit','mute','text','playback_started','playback_done','playback_failed','stop','replay','local_partial','local_final']
    text: str = Field(default='',max_length=5000)
    muted: bool = False
    seq: int = Field(default=0,ge=0)
    revision: int = Field(default=0,ge=0)
    inference_id: str = Field(default='',max_length=100)


def words(text):
    return re.findall(r"[\w']+",text.casefold())


def meaningful(text):
    text=re.sub(r'\[[^\]]*\]|\([^)]*\)','',text)
    tokens=words(text)
    return bool(tokens) and any(t not in {'um','uh','erm','hmm','ah','mm','mhm'} for t in tokens)


def playback_echo(text, spoken):
    # AEC + provider filtering do the audio work. This is a conservative last guard
    # against a verbatim leak of Dana's voice, never a speaker-identity guarantee.
    tokens=words(text)
    return len(tokens)>=3 and ' '.join(tokens) in ' '.join(words(spoken))


class Conversation:
    def __init__(self, sid, send):
        self.sid,self.send=sid,send
        self.revision=0
        self.task=None
        self.playing=None
        self.last_dana=''
        self.echo_until=0.
        self.partial=''
        self.muted=False
        self.discard_segment=False
        self.source_job=None
        self.closed=False
        self.candidate_lock=asyncio.Lock()

    async def interrupt(self, reason='speech'):
        active=self.playing is not None or (self.task and not self.task.done())
        self.revision+=1
        if self.task and not self.task.done():
            self.task.cancel()
            with suppress(asyncio.CancelledError): await self.task
        self.task=None
        seq=self.playing
        self.playing=None
        # Keep the echo guard for the tail of interrupted speaker audio.
        if active:
            self.echo_until=time.monotonic()+1.0
        await self.send({'type':'interrupt','revision':self.revision})
        if active:
            session=await s.require_session(self.sid)
            await s.log(self.sid,'interrupted','candidate',session['step'],{'reason':reason,'interrupted_seq':seq})

    async def transcript(self,text,final=False):
        text=text.strip()
        if self.discard_segment:
            if final:self.discard_segment=False
            return
        if self.muted or not meaningful(text):
            if final:
                had_partial=bool(self.partial)
                self.partial=''
                if had_partial:await self.send({'type':'partial','text':''})
            return
        if (self.playing is not None or time.monotonic()<self.echo_until) and playback_echo(text,self.last_dana):
            if final:
                self.partial=''
                await self.send({'type':'partial','text':''})
            return
        if not final:
            if text==self.partial:return
            self.partial=text
            # Recognized speech, rather than an RMS spike, triggers barge-in.
            if self.playing is not None or (self.task and not self.task.done()):
                await self.interrupt()
            await self.send({'type':'partial','text':text})
            return
        self.partial=''
        await self.submit(text)

    async def submit(self,text):
        async with self.candidate_lock:
            await self.interrupt('new_utterance')
            session=await s.require_session(self.sid)
            if session['status']!='live' or session.get('engine_state',{}).get('paused'):return
            if session.get('scenario_id'):
                definition=await s.engine.context(self.sid)
                if session['step']>=len(definition['steps']):return
            event=await s.record_candidate(self.sid,TurnInput(text=text,step=session['step']),self.source_job)
            await self.send({'type':'committed','event':event.model_dump(mode='json')})
            revision=self.revision
            self.task=asyncio.create_task(self.respond(event,revision))

    async def respond(self,event,revision):
        try:
            # Small continuation window: the next partial cancels this before Dana jumps in.
            await asyncio.sleep(.35)
            await self.send({'type':'state','state':'thinking','revision':revision})
            result=await s.respond(self.sid,event)
            if revision!=self.revision or self.closed:return
            reply=next((e for e in result.events if e.actor=='interviewer'),None)
            if reply: await self.deliver(reply,revision)
            else: await self.send({'type':'state','state':'listening','revision':revision})
        except asyncio.CancelledError:
            raise
        except Exception:
            if revision==self.revision and not self.closed:
                await self.send({'type':'error','message':'Dana could not finish that response. Your words are saved; keep talking or try again.','fatal':False})

    async def deliver(self,event,revision):
        self.playing=event.seq
        self.last_dana=str(event.payload.get('text',''))
        await self.send({'type':'reply','event':event.model_dump(mode='json'),'revision':revision})

    async def playback_done(self,seq,revision):
        if revision!=self.revision or seq!=self.playing:return
        self.playing=None;self.echo_until=time.monotonic()+.7
        action=await s.acknowledge_reply(self.sid,seq)
        if action=='look': await self.send({'type':'look','revision':revision})
        await self.send({'type':'state','state':'listening','revision':revision})

    async def close(self):
        self.closed=True
        if self.task and not self.task.done():
            self.task.cancel()
            with suppress(asyncio.CancelledError):await self.task


async def receive_browser(ws,conversation,send,upstream=None):
    sid=conversation.sid
    while True:
        message=await ws.receive()
        if message['type']=='websocket.disconnect':return
        if message.get('bytes') is not None:
            if upstream is None:continue
            data=message['bytes']
            if len(data)>64000 or len(data)%2:raise HTTPException(422,'Invalid audio frame.')
            if conversation.muted:data=bytes(len(data))
            await upstream.send(json.dumps({'message_type':'input_audio_chunk','audio_base_64':base64.b64encode(data).decode(),'sample_rate':16000}))
        else:
            command=Command.model_validate_json(message.get('text',''))
            if command.type=='stop':return
            if command.type=='interrupt':await conversation.interrupt('button')
            elif command.type=='mute':
                if upstream is not None and command.muted and conversation.partial:conversation.discard_segment=True
                conversation.muted=command.muted
                conversation.partial=''
                await send({'type':'partial','text':''})
            elif command.type=='commit' and upstream is not None:
                await upstream.send(json.dumps({'message_type':'input_audio_chunk','audio_base_64':base64.b64encode(bytes(3200)).decode(),'commit':True,'sample_rate':16000}))
            elif command.type=='text' and command.text.strip():
                conversation.source_job=None
                await conversation.submit(command.text.strip())
            elif command.type in ('local_partial','local_final'):
                if upstream is not None:raise HTTPException(409,'Local transcription is not active.')
                from .local_speech import consume_transcript
                conversation.source_job=await consume_transcript(sid,command.inference_id,command.text,command.type=='local_final')
                await conversation.transcript(command.text,command.type=='local_final')
            elif command.type=='playback_done':await conversation.playback_done(command.seq,command.revision)
            elif command.type=='playback_failed':await conversation.interrupt('playback_failed')
            elif command.type=='replay':
                event=next((e for e in await s.events(sid) if e.seq==command.seq and e.kind=='turn' and e.actor=='interviewer'),None)
                if event:
                    await conversation.interrupt('replay')
                    await conversation.deliver(event,conversation.revision)


async def serve(ws: WebSocket,sid: str):
    await ws.accept()
    lock=asyncio.Lock()
    async def send(value):
        async with lock:await ws.send_json(value)
    conversation=Conversation(sid,send)
    reader=None;jid=None;outcome='succeeded';registered=False;failure=None
    try:
        if sid in ACTIVE:raise HTTPException(409,'Voice is already open for this session. End it in the other tab first.')
        ACTIVE.add(sid);registered=True
        session=await s.require_session(sid)
        definition=await s.engine.context(sid)
        if session['status']!='live' or session['step']>=len(definition['steps']):raise HTTPException(409,'This interview is complete.')
        if session['engine_state'].get('paused'):raise HTTPException(409,'Resume this interview before starting voice.')
        if not config.ELEVENLABS_API_KEY:raise HTTPException(503,'ElevenLabs is not configured.')
        jid=await voice.job(sid,'stt','scribe_v2_realtime')
        conversation.source_job=jid
        async with connect('wss://api.elevenlabs.io/v1/speech-to-text/realtime?'+urlencode(PARAMS),
                           additional_headers={'xi-api-key':config.ELEVENLABS_API_KEY},open_timeout=10,max_size=1_000_000) as upstream:
            initial=json.loads(await asyncio.wait_for(upstream.recv(),10))
            check_provider_message(initial)
            if initial.get('message_type')!='session_started':
                raise HTTPException(503,'ElevenLabs realtime transcription could not start. Check speech-to-text permissions and quota.')
            await send({'type':'ready','revision':0})

            async def receive_transcripts():
                async for raw in upstream:
                    message=json.loads(raw);kind=message.get('message_type')
                    check_provider_message(message)
                    if kind=='partial_transcript':await conversation.transcript(message.get('text',''))
                    elif kind=='committed_transcript':await conversation.transcript(message.get('text',''),True)
                    elif kind not in ('session_started','warning','committed_transcript_with_timestamps'):
                        raise RuntimeError('Realtime transcription interrupted')


            reader=asyncio.create_task(receive_transcripts())
            browser=asyncio.create_task(receive_browser(ws,conversation,send,upstream))
            try:
                done,_=await asyncio.wait([reader,browser],return_when=asyncio.FIRST_COMPLETED)
                for task in done:task.result()
                if reader in done and browser not in done:raise RuntimeError('Provider closed the transcription stream')
            finally:
                for task in (reader,browser):
                    task.cancel()
                await asyncio.gather(reader,browser,return_exceptions=True)
    except (WebSocketDisconnect,):pass
    except Exception as exc:
        outcome='failed'
        failure=failure_message(exc)
        logger.warning('Voice relay failed: %s (%s)',type(exc).__name__,exc.code if isinstance(exc,ProviderStreamError) else 'see audited error')
        if isinstance(exc,ProviderStreamError) and exc.code=='quota_exceeded':
            if jid:
                await db.execute("UPDATE generation_jobs SET status='failed',error=$2,stage='Realtime stream failed',finished_at=now() WHERE id=$1",jid,failure)
                jid=None
            try:
                conversation.discard_segment=False
                conversation.partial=''
                conversation.source_job=None
                await send({'type':'fallback','provider':'parakeet','reason':'quota'})
                await receive_browser(ws,conversation,send)
            except (WebSocketDisconnect,):pass
            except Exception as local_exc:
                with suppress(Exception):await send({'type':'error','message':failure_message(local_exc),'fatal':True})
        else:
            with suppress(Exception):await send({'type':'error','message':failure,'fatal':True})
    finally:
        if registered:ACTIVE.discard(sid)
        await conversation.close()
        if jid:
            await db.execute("UPDATE generation_jobs SET status=$2,error=$3,stage=$4,finished_at=now() WHERE id=$1",jid,outcome,failure,'Realtime stream failed' if failure else 'Realtime stream closed')
        with suppress(Exception):await ws.close()
