"""Atomic, idempotent actions for hand-built session engines."""
from fastapi import HTTPException
from . import db, engine, pi_lab
from .models import LabAction, Event, TurnResult


def state(definition):
    saved=definition['engine_state'].get('_lab')
    if saved:
        if saved.get('version')!=pi_lab.VERSION:raise HTTPException(409,'This simulator version is unavailable.')
        return saved
    return pi_lab.initial(definition.get('params',{}).get('variant',0))


def public_state(definition):
    # Internal simulator state is never exposed through Session or Dana context.
    result={k:v for k,v in definition['engine_state'].items() if not k.startswith('_')}
    if definition['engine_id']=='linux_fault':result['lab']=pi_lab.public(state(definition),definition['step'])
    return result


def complete(definition):
    return definition['engine_id']!='linux_fault' or pi_lab.goal(state(definition),definition['step'])


async def action(sid, body: LabAction):
    from .service import log
    async with (await db.pool()).acquire() as conn,conn.transaction():
        session=await conn.fetchrow('SELECT * FROM sessions WHERE id=$1 FOR UPDATE',sid)
        if not session:raise HTTPException(404,'Session not found')
        # Retry of a committed request remains idempotent even after progression.
        previous=await conn.fetchrow("SELECT * FROM session_events WHERE session_id=$1 AND kind IN ('command','edit','part_drop','probe') AND payload->>'request_id'=$2",sid,body.request_id)
        if previous:
            if previous['payload'].get('request')!=body.model_dump():raise HTTPException(409,'Action id was already used for a different request.')
            return TurnResult(events=[Event(**dict(previous))],source='simulator')
        definition=await engine.context(sid,conn)
        if definition['engine_id']!='linux_fault':raise HTTPException(409,'This session has no supported simulator.')
        if session['status']!='live' or session['engine_state'].get('paused') or session['step']>=len(definition['steps']):
            raise HTTPException(409,'Resume an active simulator step before adding work.')
        if session['step']!=body.step:raise HTTPException(409,'The step changed. Refresh before retrying.')
        current=state(definition)
        if current['revision']!=body.revision:raise HTTPException(409,'The lab changed in another tab. Refresh before retrying.')
        try:updated,output=pi_lab.apply(current,body.kind,body.text)
        except ValueError as exc:raise HTTPException(422,str(exc))
        private={**session['engine_state'],'_lab':updated}
        await conn.execute('UPDATE sessions SET engine_state=$2 WHERE id=$1',sid,private)
        event=await log(sid,{'command':'command','edit':'edit','part':'part_drop','browser':'probe'}[body.kind],
            'candidate',body.step,{'request_id':body.request_id,'request':body.model_dump(),'input':body.text,
                'output':output,'text':f'{body.kind}: {body.text}\n{output}',
                'source':'validated_simulator','engine_version':pi_lab.VERSION,'revision':updated['revision']},conn)
    return TurnResult(events=[event],source='simulator')
