"""Explicit scripted walkthroughs. No model calls, scores, mastery or verified gaps."""
from fastapi import HTTPException
from . import db, engine, rubrics, service
from .models import TurnInput, TurnResult, BoardInput

DESIGN_REPLIES = (
    ('Use API keys and allow short bursts. Prioritize availability. What will hold the shared state?',
     'Good. Show me the gateway, limiter and shared store, and explain the request path.'),
    ('Keep explaining the drawing. How do two gateways update the same counter safely?',
     'Let me review the drawing, especially the shared counter and failure behavior.'),
    ('A cached count at each gateway cannot guarantee a strict global limit. What coordination would you need?',
     'That gives us a useful next practice goal: atomic updates and an explicit failure policy.'),
)
PI_REPLIES = (
    'The proxy and app observations point to different endpoints. Make a scoped repair and verify it.',
    'The public response now works. Next, check the stylesheet access.',
    'Mode 644 gives others read access, not write access. Remember that parent directories need search permission too.',
    'The contact form works after recovering space. Finish by distinguishing current power flags from history.',
    'Those high bits record history. The current low bits are clear; use that distinction in the next investigation.',
)

DEMO_OPENINGS={
    'conceptual':'Let us design a rate limiter for a public API. Start by asking about the requirements.',
    'linux_fault':'A simulated Raspberry Pi site returns a gateway error. Investigate the terminal and explain your decisions.',
}
CANDIDATE_UTTERANCES={
    'What traffic and per-key limit should we support?',
    'I will use token buckets. What burst allowance and availability target do we need?',
    'The gateway checks a Redis token bucket before calling the API. I think separate reads and writes cannot race because Redis is single threaded.',
    'Please review my board.',
    'If Redis fails, each gateway uses cached tokens. I think exact global limits still hold; no reconciliation or shared coordination is needed.',
    'A separate GET followed by SET should be safe. I would not need a transaction or an atomic Lua script.',
    'The app works on port 3000. Nginx points to 3001, causing the 502.',
    'I corrected the port, tested nginx, reloaded, and verified HTTP 200.',
    'The stylesheet now returns 200. I think 644 gives every user write permission.',
    'The access log filled the disk. I truncated it and verified the form. Next, add log rotation.',
    'I fitted the good supply. I interpret high bits as current under-voltage, so I think it is still throttling.',
}


async def start(sid):
    session,definition=await supported(sid)
    if session['status']!='live':raise HTTPException(409,'Start demo playback in a live session.')
    await mark(sid)
    existing=await db.one("SELECT * FROM session_events WHERE session_id=$1 AND kind='turn' AND actor='interviewer' AND payload->>'demo_opening'='true' ORDER BY seq LIMIT 1",sid)
    if existing:
        from .models import Event
        return Event(**dict(existing))
    return await service.log(sid,'turn','interviewer',session['step'],{'text':DEMO_OPENINGS[definition['engine_id']],
        'source':'scripted_demo','action':'continue','demo_opening':True,'synthetic':True})


async def supported(sid):
    session=await service.require_session(sid)
    track=await db.one('SELECT source,title FROM tracks WHERE id=$1',session['track_id'])
    definition=await engine.context(sid)
    if not track or track['source']=='retest' or session.get('kind')=='retest' or not definition:
        raise HTTPException(409,'Scripted playback supports the original practice tracks only.')
    expected=('Clarify requirements','Draw and explain','Defend the trade-offs') if definition['engine_id']=='conceptual' else ('Read the error','Fix the proxy','Fix the deploy','Free the disk','Check the hardware') if definition['engine_id']=='linux_fault' else ()
    if not expected or tuple(step.title for step in definition['steps'])!=expected:
        raise HTTPException(409,'This scenario is not supported by scripted playback.')
    if definition['engine_id']=='linux_fault' and definition.get('params',{}).get('variant',0)!=0:
        raise HTTPException(409,'Changed Pi retests require your own investigation.')
    return session,definition


async def mark(sid):
    await db.execute('UPDATE sessions SET engine_state=engine_state || $2::jsonb WHERE id=$1',sid,{'scripted_demo':True})


async def turn(sid,body:TurnInput):
    _,definition=await supported(sid)
    first=await service.record_candidate(sid,body)
    await mark(sid)
    count=await db.one("SELECT count(*) n FROM session_events WHERE session_id=$1 AND kind='turn' AND actor='candidate' AND step=$2",sid,body.step)
    if definition['engine_id']=='conceptual':
        text=DESIGN_REPLIES[body.step][min(count['n']-1,1)]
    else:text=PI_REPLIES[body.step]
    second=await service.log(sid,'turn','interviewer',body.step,
        {'text':text,'source':'scripted_demo','action':'continue','reply_to':first.seq,'synthetic':True})
    return TurnResult(events=[first,second],source='scripted_demo')


async def board(sid,body:BoardInput):
    _,definition=await supported(sid)
    if definition['engine_id']!='conceptual':raise HTTPException(409,'This demo has no whiteboard.')
    await mark(sid)
    return await service.board(sid,body,scripted_demo=True)


def recap(engine_id):
    if engine_id=='linux_fault':
        return {'scripted':True,'label':'Scripted demonstration — these are authored examples, not an assessment.',
            'weakpoints':['Read octal permissions by owner, group and others.','Distinguish current throttle flags from historical warnings.'],
            'lesson':{'title':'Permissions and power: interpret the evidence',
                'body':'Mode 644 gives the owner read/write access and group/others read-only access. Serving a file also requires search permission through parent directories. Current throttle flags are in the low bits; historical high bits can remain after a fault is fixed.',
                'practice':'Explain the permissions of a readable file inside a non-searchable directory. Compare current and historical throttle flags before deciding to replace a supply.'},
            'retest_prompt':'Investigate a newly redeployed simulated Pi site. The next practice changes the application endpoint, directory access, log lifecycle and power conditions. Discover the symptoms and justify each repair.'}
    return {'scripted':True,'label':'Scripted demonstration — these are authored examples, not an assessment.',
        'weakpoints':['Coordinate token updates atomically across gateways.','Explain the availability versus strict-limit trade-off during a shared-store outage.'],
        'lesson':{'title':'Shared counters need atomic decisions',
            'body':'Separate GET and SET commands can interleave between gateways, even when each Redis command is single threaded. Combine the decision and update atomically. Independent cached counts cannot guarantee a strict global limit during an outage; choose and explain a bounded approximation or an availability trade-off.',
            'practice':'Walk through two gateways reading the same remaining token, then describe an atomic operation that admits only one request.'},
        'retest_prompt':'Design a rate limiter for an API spread across two regions. Explain how the limit behaves during a shared-state outage when strict global enforcement matters more than availability.'}


async def end(sid):
    session,definition=await supported(sid)
    if not session['engine_state'].get('scripted_demo'):
        raise HTTPException(409,'Start the scripted walkthrough before finishing it.')
    if session['step']<len(definition['steps']):
        raise HTTPException(409,'Complete the walkthrough before opening its recap.')
    result=recap(definition['engine_id'])
    version=rubrics.load(definition['rubric'],definition['engine_id']).version
    async with (await db.pool()).acquire() as conn,conn.transaction():
        current=await conn.fetchrow('SELECT * FROM sessions WHERE id=$1 FOR UPDATE',sid)
        if current['status'] not in ('live','graded'):
            raise HTTPException(409,'This session is already being assessed.')
        if current['status']=='graded':
            saved=await conn.fetchrow('SELECT report,stats FROM session_reports WHERE session_id=$1',sid)
            if saved and saved['stats'].get('scripted_demo') and saved['report'].get('scripted_walkthrough'):
                return saved['report']['scripted_walkthrough']
            raise HTTPException(409,'This session already has an assessment.')
        await conn.execute('INSERT INTO session_reports(session_id,overall,report,stats) VALUES($1,NULL,$2,$3) ON CONFLICT(session_id) DO UPDATE SET overall=NULL,report=excluded.report,stats=excluded.stats',
            sid,{'scores':[],'rubric_version':version,'scripted_walkthrough':result},{'demo':True,'scripted_demo':True,'partial':False,'supported':0})
        await conn.execute("UPDATE sessions SET status='graded',ended_at=coalesce(ended_at,now()),graded_at=now() WHERE id=$1",sid)
        await service.log(sid,'note','system',current['step'],{'scripted_demo_complete':True,'synthetic':True,'label':'Authored walkthrough; no ability assessment'},conn)
    return result
