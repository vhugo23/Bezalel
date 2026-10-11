"""Shared persisted session contract. Surface adapters do not own progression."""
from fastapi import HTTPException
from . import db
from .models import SessionStep


LEGACY_STEPS = [
    SessionStep(idx=0,title='Clarify requirements',surface='voice',task='Ask Dana about the workload, constraints and success conditions.',success={'min_turns':2}),
    SessionStep(idx=1,title='Draw and explain',surface='whiteboard',task='Talk through your design as you draw. Ask Dana questions, then request a review.',config={'look':'on_done'},success={'min_turns':1,'board_review':True}),
    SessionStep(idx=2,title='Defend the trade-offs',surface='voice',task='Explain a decision, its consequences and a failure case.',success={'min_turns':2}),
]


def parse_steps(spec, rows=None):
    raw = rows or spec.get('steps') or []
    if raw and all(isinstance(item,str) for item in raw):
        # Compatibility only for the previously shipped authored three-step flow.
        if len(raw)!=3:raise ValueError('Legacy steps require migration')
        result=[step.model_copy(update={'title':title}) for step,title in zip(LEGACY_STEPS,raw)]
    else:
        result=[SessionStep.model_validate(dict(item)) for item in raw]
    if not result or len(result)>10 or [s.idx for s in result]!=list(range(len(result))):
        raise ValueError('Scenario steps must be nonempty, ordered and contiguous')
    for step in result:
        minimum=step.success.get('min_turns',1)
        if not isinstance(minimum,int) or isinstance(minimum,bool) or not 0<=minimum<=20:
            raise ValueError('Invalid minimum utterances')
        if step.config.get('look','on_done') not in ('on_done','on_pause'):
            raise ValueError('Invalid board look mode')
    return result


async def context(sid, conn=None):
    one=conn.fetchrow if conn else db.one
    fetch=conn.fetch if conn else db.fetch
    row=await one('SELECT sc.*,t.domain_id,s.engine_state,s.step,s.status FROM sessions s JOIN scenarios sc ON sc.id=s.scenario_id JOIN tracks t ON t.id=s.track_id WHERE s.id=$1',sid)
    if not row:return None
    steps=await fetch('SELECT idx,title,surface,task,config,hints,success,rubric_ids FROM scenario_steps WHERE scenario_id=$1 ORDER BY idx',row['id'])
    return {**dict(row),'steps':parse_steps(row['spec'],steps)}


async def persist_steps(conn, scenario_id, steps):
    for step in steps:
        await conn.execute('INSERT INTO scenario_steps(scenario_id,idx,title,surface,task,config,hints,success,rubric_ids) VALUES($1,$2,$3,$4,$5,$6,$7,$8,$9)',scenario_id,step.idx,step.title,step.surface,step.task,step.config,step.hints,step.success,step.rubric_ids)


def action_allowed(action, step, count, reviewed, text, steps):
    if not 0<=step<len(steps):return 'continue'
    current=steps[step]
    if action=='look':
        from .service import board_look_requested
        return 'look' if current.surface=='whiteboard' and board_look_requested(text) else 'continue'
    enough=count>=current.success.get('min_turns',1)
    complete=enough and (not current.success.get('board_review') or reviewed)
    if action=='advance' and step<len(steps)-1 and complete:return action
    if action=='finish' and step==len(steps)-1 and complete:return action
    return 'continue'


async def ensure_accepting(session, sid):
    if session.get('engine_state',{}).get('paused'):
        raise HTTPException(409,'Resume the interview before adding work.')
    definition=await context(sid) if session.get('scenario_id') else None
    if definition and session['step']>=len(definition['steps']):
        raise HTTPException(409,'The interview is complete.')
    return definition
