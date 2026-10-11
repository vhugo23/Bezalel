"""Single-use pairing with a private, bounded reconnect capability."""
import asyncio
import hashlib
import re
import secrets
from datetime import datetime,timezone

from fastapi import HTTPException, WebSocketDisconnect
from pydantic import ValidationError
from . import db, engine, service
from .models import EventInput, Stroke


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
                if raw.get('type')=='stroke':
                    stroke=Stroke.model_validate(raw.get('stroke'))
                    event=await service.append(session['id'],EventInput(kind='stroke',step=raw.get('step'),payload=stroke.model_dump()))
                    await ws.send_json({'type':'ack','id':stroke.id,'seq':event.seq})
                elif raw.get('type')=='remove':
                    ids=raw.get('ids')
                    active=service.active_strokes(history,session['step'])
                    if not isinstance(ids,list) or not 1<=len(ids)<=1000 or any(not isinstance(i,str) or i not in active for i in ids):raise ValueError('Unknown stroke to remove')
                    event=await service.append(session['id'],EventInput(kind='note',step=raw.get('step'),payload={'remove_strokes':ids}))
                    await ws.send_json({'type':'event','event':event.model_dump(mode='json')})
                else:raise ValueError('Unknown device action')
            except (ValidationError,ValueError,HTTPException) as exc:
                bad_stroke=raw.get('stroke') if isinstance(raw,dict) else None
                await ws.send_json({'type':'error','id':str(bad_stroke.get('id',''))[:100] if isinstance(bad_stroke,dict) else '',
                    'message':str(exc.detail) if isinstance(exc,HTTPException) else 'Invalid drawing message.'})
    except (WebSocketDisconnect,RuntimeError,HTTPException):pass
    finally:
        await asyncio.shield(db.execute("UPDATE session_devices SET status='disconnected' WHERE id=$1 AND connection_id=$2",row['id'],connection_id))
