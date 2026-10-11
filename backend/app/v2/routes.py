import asyncio
import secrets
from fastapi import APIRouter, HTTPException, Query, WebSocket, WebSocketDisconnect, Request
from fastapi.responses import FileResponse
from pydantic import ValidationError
from app import config
from . import db, service as s
from .models import *
from .generation import DEMO

router = APIRouter(prefix='/api/v2', tags=['PrepCrew v2.3'])
ws_router = APIRouter()

@router.get('/health', response_model=Health)
async def health():
    version = await db.one('SELECT version_num FROM alembic_version')
    return Health(status='ok',schema_version=version['version_num'],demo=DEMO,
                  voice_ready=bool(config.ELEVENLABS_API_KEY and config.ELEVENLABS_VOICE_ID) and not DEMO,
                  test_environment=config.V2_DATABASE_SCHEMA.startswith('prepcrew_e2e_'))

@router.post('/plans', response_model=Plan)
async def plan(body: Intake): return await s.create_plan(body)

@router.post('/plans/jobs', response_model=WorkItem, status_code=202)
async def plan_job(body: Intake):
    from . import planning
    return await planning.enqueue(body)

@router.get('/plans/{pid}', response_model=Plan)
async def get_plan(pid: str): return await s.get_plan(pid)

@router.get('/users/{user_id}/sources', response_model=SourceList)
async def source_list(user_id: str):
    from . import sources
    return SourceList(sources=await sources.list_for(user_id))

@router.post('/sources', response_model=SourceDocument, status_code=201)
async def source_create(body: SourceInput):
    from . import sources
    return await sources.create(body)

@router.post('/sources/upload', response_model=SourceDocument, status_code=201)
async def source_upload(request: Request, user_id: str=Query(min_length=1,max_length=100),
                        kind: SourceKind='notes', title: str=Query(min_length=1,max_length=160)):
    from . import sources
    data=bytearray()
    async for chunk in request.stream():
        data.extend(chunk)
        if len(data)>sources.MAX_BYTES:raise HTTPException(413,'Keep source files under 3 MB.')
    return await sources.upload(user_id,kind,title,bytes(data),request.headers.get('content-type',''))

@router.post('/sources/github', response_model=SourceDocument, status_code=201)
async def source_github(body: SourceLinkInput):
    from . import sources
    return await sources.github(body.user_id,body.url)

@router.get('/sources/{source_id}', response_model=SourceDocument)
async def source_read(source_id: str):
    from . import sources
    return SourceDocument(**dict(await sources.read(source_id)))

@router.post('/sources/{source_id}/extract', response_model=WorkItem, status_code=202)
async def source_extract(source_id: str):
    from . import sources
    return await sources.enqueue(source_id)

@router.post('/sources/{source_id}/confirm', response_model=SourceDocument)
async def source_confirm(source_id: str, body: SourceConfirmation):
    from . import sources
    return await sources.confirm(source_id,body.fact_indices)

@router.post('/sessions', response_model=Session)
async def start(body: Start): return await s.start(body)

@router.get('/sessions/{sid}', response_model=Session)
async def session(sid: str): return await s.get_session(sid)

@router.post('/sessions/{sid}/lab', response_model=TurnResult)
async def lab_action(sid: str, body: LabAction):
    from . import labs
    return await labs.action(sid,body)

@router.post('/sessions/{sid}/pause', response_model=Session)
async def pause(sid: str, body: PauseInput):
    async with (await db.pool()).acquire() as conn,conn.transaction():
        row=await conn.fetchrow('SELECT * FROM sessions WHERE id=$1 FOR UPDATE',sid)
        if not row:raise HTTPException(404,'Session not found')
        if row['status']!='live':raise HTTPException(409,'Only a live interview can pause.')
        if row['engine_state'].get('paused',False)!=body.paused:
            await conn.execute('UPDATE sessions SET engine_state=engine_state || $2::jsonb WHERE id=$1',sid,{'paused':body.paused})
            await s.log(sid,'note','system',row['step'],{'paused':body.paused},conn)
    return await s.get_session(sid)

@router.post('/sessions/{sid}/hint', response_model=Event)
async def hint(sid: str):
    from . import engine
    async with (await db.pool()).acquire() as conn,conn.transaction():
        row=await conn.fetchrow('SELECT * FROM sessions WHERE id=$1 FOR UPDATE',sid)
        if not row:raise HTTPException(404,'Session not found')
        definition=await engine.context(sid,conn)
        if row['status']!='live' or row['engine_state'].get('paused') or row['step']>=len(definition['steps']):
            raise HTTPException(409,'Hints require an active step.')
        current=definition['steps'][row['step']]
        used=await conn.fetchval("SELECT count(*) FROM session_events WHERE session_id=$1 AND step=$2 AND kind='hint'",sid,row['step'])
        if used>=len(current.hints):raise HTTPException(409,'No more hints for this step.')
        return await s.log(sid,'hint','interviewer',row['step'],{'text':current.hints[used],'hint_index':used,'source':'authored_step'},conn)

@router.get('/sessions/{sid}/events', response_model=list[Event])
async def events(sid: str, after: int = Query(0,ge=0)): return await s.events(sid,after)

@router.post('/sessions/{sid}/events', response_model=Event)
async def append(sid: str, body: EventInput):
    try: return await s.append(sid,body)
    except ValidationError: raise HTTPException(422,'Invalid event payload')

@router.post('/sessions/{sid}/turns', response_model=TurnResult)
async def turn(sid: str, body: TurnInput):
    try: return await s.turn(sid,body)
    except ValueError as exc: raise HTTPException(503,str(exc))

@router.post('/sessions/{sid}/reply-complete')
async def reply_complete(sid: str, body: ReplyAck):
    return {'action':await s.acknowledge_reply(sid,body.seq)}

@ws_router.websocket('/ws/v2/voice/{sid}')
async def duplex(ws: WebSocket, sid: str):
    from .realtime import serve
    await serve(ws,sid)

@router.post('/sessions/{sid}/board', response_model=BoardResult)
async def board(sid: str, body: BoardInput):
    try: return await s.board(sid,body)
    except ValueError as exc: raise HTTPException(422,str(exc))

@router.post('/sessions/{sid}/end', response_model=Report)
async def end(sid: str):
    from . import rubrics,engine
    async with (await db.pool()).acquire() as conn,conn.transaction():
        session=await conn.fetchrow('SELECT * FROM sessions WHERE id=$1 FOR UPDATE',sid)
        if not session:raise HTTPException(404,'Session not found')
        definition=await engine.context(sid,conn)
        VERSION=rubrics.load(definition['rubric'],definition['engine_id']).version
        saved=await conn.fetchrow('SELECT * FROM session_reports WHERE session_id=$1',sid)
        complete=saved and saved['report'].get('rubric_version')==VERSION and not saved['stats'].get('partial',False)
        if session['status']!='grading' and not (session['status']=='graded' and complete):
            await conn.execute("UPDATE sessions SET status='grading',ended_at=coalesce(ended_at,now()) WHERE id=$1",sid)
    return await s.report(sid)

@router.get('/sessions/{sid}/report', response_model=Report)
async def report(sid: str): return await s.report(sid)

@router.get('/sessions/{sid}/metrics', response_model=Metrics)
async def metrics(sid: str):
    session=await s.require_session(sid)
    return Metrics(rows=[dict(r) for r in await db.fetch('SELECT name,n,p50,p95,max FROM v_session_latency WHERE session_id=$1',sid)],
                   hypertables=[r['hypertable_name'] for r in await db.fetch('SELECT hypertable_name FROM timescaledb_information.hypertables WHERE hypertable_schema=$1',config.V2_DATABASE_SCHEMA)],
                   aggregates=[r['view_name'] for r in await db.fetch('SELECT view_name FROM timescaledb_information.continuous_aggregates WHERE view_schema=$1',config.V2_DATABASE_SCHEMA)],
                   mastery=[{**dict(r),'bucket':r['bucket'].isoformat()} for r in await db.fetch('SELECT skill_id,bucket,score,samples FROM mastery_hourly WHERE user_id=$1 ORDER BY bucket DESC LIMIT 48',session['user_id'])])

@router.get('/sessions/{sid}/lesson', response_model=Lesson)
async def lesson(sid: str):
    from .learning import read
    return await read(sid)

@router.post('/sessions/{sid}/lesson', response_model=Lesson, deprecated=True)
async def generate_lesson(sid: str):
    from . import jobs,learning
    job=await jobs.enqueue_lesson(sid)
    for _ in range(120):
        job=await jobs.read(job.id)
        if job.status=='succeeded':return await learning.read(sid)
        if job.status in ('failed','cancelled'):raise HTTPException(503,job.error or 'Generation cancelled. Your evidence is saved.')
        await asyncio.sleep(.5)
    raise HTTPException(409,'Your lesson is still being prepared. Reopen the lesson to see its saved progress.')

@router.post('/sessions/{sid}/lesson/jobs', response_model=WorkItem, status_code=202)
async def enqueue_lesson(sid: str):
    from . import jobs
    return await jobs.enqueue_lesson(sid)

@router.get('/sessions/{sid}/lesson/jobs', response_model=WorkItem | None)
async def lesson_job(sid: str):
    from . import jobs
    return await jobs.latest_lesson(sid)

@router.get('/jobs/{jid}', response_model=WorkItem)
async def get_job(jid: str):
    from . import jobs
    return await jobs.read(jid)

@router.post('/jobs/{jid}/retry', response_model=WorkItem, status_code=202)
async def retry_job(jid: str):
    from . import jobs
    return await jobs.retry(jid)

@router.post('/jobs/{jid}/cancel', response_model=WorkItem)
async def cancel_job(jid: str):
    from . import jobs
    return await jobs.cancel(jid)

@router.post('/retests', response_model=Session)
async def retest(body: RetestInput):
    from .learning import retest
    return await retest(body.session_id)

@router.post('/sessions/{sid}/pair', response_model=PairResult)
async def pair(sid: str):
    session=await s.require_session(sid)
    if session['status']!='live':raise HTTPException(409,'Pairing is available only during a live session.')
    code=secrets.token_hex(4).upper()
    r=await db.one("INSERT INTO session_devices(id,session_id,kind,pair_code,expires_at) VALUES($1,$2,'ipad_whiteboard',$3,now()+interval '10 minutes') RETURNING expires_at",s.uid(),sid,code)
    return PairResult(code=code,session_id=sid,expires_at=r['expires_at'])

@router.get('/artifacts/{aid}/png')
async def artifact(aid: str):
    r=await db.one('SELECT blob_key FROM artifacts WHERE id=$1',aid)
    if not r: raise HTTPException(404,'Artifact not found')
    return FileResponse(s.ROOT / '.artifacts' / r['blob_key'],media_type='image/png')

@router.post('/sessions/{sid}/audio', response_model=TurnResult)
async def audio(sid: str, request: Request, step: int = Query(0,ge=0,le=9), board: bool = False):
    from .voice import transcribe
    session = await s.require_session(sid)
    if session['status'] != 'live' or session['step'] != step:
        raise HTTPException(409,'The session moved on. Refresh before recording again.')
    if DEMO: raise HTTPException(409,'Enable live mode for ElevenLabs voice input.')
    data=bytearray()
    async for chunk in request.stream():
        data.extend(chunk)
        if len(data)>12_000_000: raise HTTPException(413,'Keep audio turns under 12 MB')
    text = await transcribe(sid,bytes(data),request.headers.get('content-type','audio/webm'))
    # A model failure must not mark a successful transcription as failed.
    # The candidate turn is saved before generation starts, and replays over the event socket.
    try:
        return await s.turn(sid,TurnInput(text=text,step=step,board=board))
    except ValueError as exc:
        raise HTTPException(503,str(exc))

@router.get('/sessions/{sid}/speech/{seq}')
async def speech(sid: str, seq: int):
    from .voice import speak
    await s.require_session(sid)
    r=await db.one("SELECT payload FROM session_events WHERE session_id=$1 AND seq=$2 AND kind IN ('turn','hint') AND actor='interviewer'",sid,seq)
    if not r: raise HTTPException(404,'Interviewer turn not found')
    if DEMO: raise HTTPException(409,'Recorded mode has no live voice.')
    return await speak(sid,r['payload']['text'])

@ws_router.websocket('/ws/v2/sessions/{sid}')
async def live(ws: WebSocket, sid: str, after: int = 0):
    await ws.accept()
    try:
        await s.require_session(sid)
        # Polling the shared database also works across workers; replay always uses seq.
        while True:
            for e in await s.events(sid,after):
                await ws.send_json({'type':'event','event':e.model_dump(mode='json')})
                after=max(after,e.seq)
            await asyncio.sleep(.4)
    except (WebSocketDisconnect,RuntimeError,HTTPException): pass

@ws_router.websocket('/ws/v2/pair/{code}')
async def paired(ws: WebSocket, code: str):
    from .devices import paired as connect
    await connect(ws,code)
