"""Single-use pairing with a private, bounded reconnect capability."""
import asyncio
import hashlib
import re
import secrets
from datetime import datetime,timezone

from fastapi import HTTPException, WebSocketDisconnect
from pydantic import ValidationError
from . import db, engine, service
from .models import BoardElementsInput


def batch(raw):
    # Echo the device's batch id so it can settle exactly the edits a reply refers to.
    value=raw.get('batch') if isinstance(raw,dict) else None
    return {'batch':value} if isinstance(value,str) and re.fullmatch(r'[A-Za-z0-9_-]{1,100}',value) else {}


def token_hash(value):
    if not isinstance(value,str) or not re.fullmatch(r'[a-f0-9]{64}',value):
        raise ValueError('Invalid device capability')
    return hashlib.sha256(value.encode()).hexdigest()


async def paired(ws,code):
    await ws.accept()
    if not re.fullmatch(r'[A-Za-z0-9-]{1,64}',code):
        await ws.close(code=4404);return
    try:
        hello=await asyncio.wait_for(ws.receive_json(),10)
        if not isinstance(hello,dict) or hello.get('type')!='hello':raise ValueError('Missing handshake')
        digest=token_hash(hello.get('token'))
    except (ValueError,TypeError,WebSocketDisconnect,asyncio.TimeoutError):
        await ws.close(code=4400);return
    connection_id=secrets.token_hex(16)
    row=await db.one("""UPDATE session_devices d SET status='connected',
        paired_at=coalesce(paired_at,now()),resume_hash=coalesce(resume_hash,$2),
        resume_expires_at=coalesce(resume_expires_at,now()+interval '24 hours'),last_seen_at=now(),connection_id=$3
        FROM sessions s WHERE d.pair_code=$1 AND s.id=d.session_id AND s.status='live'
        AND ((d.status='pending' AND d.expires_at>now()) OR
            (d.resume_hash=$2 AND d.resume_expires_at>now() AND (d.status<>'connected' OR d.last_seen_at<now()-interval '5 seconds'))) RETURNING d.*""",code,digest,connection_id)
    if not row:
        active=await db.one("SELECT d.id FROM session_devices d JOIN sessions s ON s.id=d.session_id WHERE d.pair_code=$1 AND d.resume_hash=$2 AND d.resume_expires_at>now() AND d.status='connected' AND s.status='live'",code,digest)
        if active:await ws.close(code=4409);return
        await ws.send_json({'type':'error','message':'Pairing code expired, already used, or session ended.'})
        await ws.close(code=4404);return
    after=0;history=[];review_id=None
    try:
        session=await service.require_session(row['session_id'])
        await ws.send_json({'type':'paired','session_id':row['session_id'],'device_id':row['id'],'step':session['step']})
        # No transcript/provider material is included in device status.
        while True:
            lease=await db.one("UPDATE session_devices SET last_seen_at=now() WHERE id=$1 AND connection_id=$2 AND resume_expires_at>now() RETURNING id",row['id'],connection_id)
            if not lease:await ws.close(code=4404);return
            session=await service.require_session(row['session_id'])
            if session['status']!='live' or row['resume_expires_at']<=datetime.now(timezone.utc):
                await ws.send_json({'type':'error','message':'This session has ended.'});await ws.close(code=4404);return
            definition=await engine.context(session['id'])
            drawable=not session['engine_state'].get('paused') and session['step']<len(definition['steps']) and definition['steps'][session['step']].surface=='whiteboard'
            await ws.send_json({'type':'state','step':session['step'],'drawable':drawable})
            incoming=await service.events(session['id'],after)
            history.extend(incoming)
            for event in incoming:
                after=max(after,event.seq)
                if event.kind=='stroke' or (event.kind=='note' and 'remove_strokes' in event.payload):
                    await ws.send_json({'type':'event','event':event.model_dump(mode='json')})
            review=await service.current_board_review(session['id'],session['step'],history)
            if (review.artifact_id if review else None)!=review_id:
                review_id=review.artifact_id if review else None
                await ws.send_json({'type':'review','review':review.model_dump(mode='json') if review else None})
            try:raw=await asyncio.wait_for(ws.receive_json(),1)
            except asyncio.TimeoutError:continue
            except ValueError:
                await ws.close(code=4400);return
            try:
                if not drawable:raise HTTPException(409,'Drawing is paused or this step has no whiteboard.')
                if not isinstance(raw,dict):raise ValueError('Unknown device action')
                if raw.get('type')=='elements':
                    body=BoardElementsInput.model_validate({'step':raw.get('step'),'elements':raw.get('elements')})
                    saved=await service.append_elements(session['id'],body)
                    await ws.send_json({'type':'ack','ids':[f"{e.payload['id']}:{e.payload['version']}" for e in saved],'seq':max(e.seq for e in saved),**batch(raw)})
                else:raise ValueError('Unknown device action')
            except (ValidationError,ValueError,HTTPException) as exc:
                await ws.send_json({'type':'error','message':str(exc.detail) if isinstance(exc,HTTPException) else 'Invalid drawing message.',**batch(raw)})
    except (WebSocketDisconnect,RuntimeError,HTTPException):pass
    finally:
        await asyncio.shield(db.execute("UPDATE session_devices SET status='disconnected' WHERE id=$1 AND connection_id=$2",row['id'],connection_id))
