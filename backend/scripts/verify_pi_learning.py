"""Pi learning acceptance: synthetic verified gap, authored coaching, real PostgreSQL.

Only called with the e2e harness's disposable schema. No live providers.
"""
from uuid import uuid4
from app import config
from app.v2 import db,service,learning,generation,jobs,pi_lab,rubrics,labs
from app.v2.integrity import verify as check_evidence
from app.v2.models import Intake,Start,LabAction,ClaimDraft


async def verify(source,schema):
    assert schema.startswith('prepcrew_e2e_') and schema.replace('_','').isalnum()
    assert db._pool is None
    prior=(config.DATABASE_URL,config.V2_DATABASE_SCHEMA,config.BACKBOARD_API_KEY,service.DEMO,generation.DEMO,learning.generate)
    config.DATABASE_URL,config.V2_DATABASE_SCHEMA=source,schema
    config.BACKBOARD_API_KEY='';service.DEMO=False;generation.DEMO=True
    async def no_model_calls(*args, **kwargs):
        raise AssertionError('Authored Pi coaching must not call a provider')
    learning.generate=no_model_calls
    try:
        owner=str(uuid4())
        plan=await service.create_plan(Intake(user_id=owner,name='Synthetic learning fixture',role='Infra',companies=[],struggles=['Permissions'],question='Investigate a Pi site.'))
        track=next(t for t in plan.tracks if t.title=='Fix the site on the Pi')
        parent=await service.start(Start(track_id=track.id,consent=True))
        row=await service.require_session(parent.id)
        await db.execute('UPDATE scenarios SET params=params || $2::jsonb WHERE id=$1',row['scenario_id'],{'private_answer':'PRIVATE_CANARY'})
        # Fixture starts at an explicit attempted permissions repair; no human work is graded.
        await db.execute('UPDATE sessions SET step=2 WHERE id=$1',parent.id)
        action=await labs.action(parent.id,LabAction(request_id=uuid4().hex,revision=0,step=2,kind='command',text='sudo chmod -R 777 /var/www/site'))
        event=action.events[0]
        claim=ClaimDraft(text='You granted write access to everyone in the simulated site tree.',polarity='gap',skill_id='infra.permissions',
                         evidence_seq=[event.seq],quotes=['sudo chmod -R 777 /var/www/site'],rule='tool_action')
        assert check_evidence(claim,[event.model_dump() ],parent.id)[0]=='verified'
        policy=rubrics.load(pi_lab.definition()['rubric'],'linux_fault');cid=str(uuid4())
        async with (await db.pool()).acquire() as conn,conn.transaction():
            for name in policy.evaluators:
                rid=str(uuid4())
                output={'claims':[claim.model_dump()] if name=='Linux and power' else [],'scores':[],'synthetic':True}
                await conn.execute("INSERT INTO evaluator_runs(id,session_id,evaluator,status,prompt_version,output) VALUES($1,$2,$3,'done',$4,$5)",rid,parent.id,name,policy.version,output)
                if name=='Linux and power':
                    await conn.execute("INSERT INTO claims(id,run_id,session_id,skill_id,text,polarity,evidence_seq,check_status,rubric_id,check_reason) VALUES($1,$2,$3,$4,$5,'gap',$6,'verified','permissions','Synthetic fixture with locally checked tool evidence')",cid,rid,parent.id,claim.skill_id,claim.text,claim.evidence_seq)
            await conn.execute("UPDATE sessions SET status='graded' WHERE id=$1",parent.id)
            await conn.execute('INSERT INTO session_reports(session_id,report,stats) VALUES($1,$2,$3)',parent.id,{'rubric_version':policy.version},{'partial':False,'demo':True,'synthetic':True})
            await conn.execute('INSERT INTO retest_queue(id,user_id,skill_id,session_id,claim_id,reason) VALUES($1,$2,$3,$4,$5,$6)',str(uuid4()),owner,claim.skill_id,parent.id,cid,claim.text)
        work=await jobs.enqueue_lesson(parent.id)
        await jobs.execute(work.id)
        result=await jobs.read(work.id)
        assert result.status=='succeeded' and 'reference-tested simulator' in result.result['validation_label'].lower()
        lesson=await learning.read(parent.id)
        assert lesson.retest_ready and lesson.evidence_seq==[event.seq]
        assert not (await db.one('SELECT ai_generated FROM lessons WHERE claim_id=$1',cid))['ai_generated']
        queue=await db.one('SELECT * FROM retest_queue WHERE claim_id=$1',cid)
        scenario=await db.one('SELECT * FROM scenarios WHERE track_id=$1',queue['track_id'])
        assert scenario['engine_id']=='linux_fault' and scenario['params']=={'variant':1}
        assert scenario['variant_of']==row['scenario_id'] and scenario['spec']['prompt']!=pi_lab.definition()['spec']['prompt']
        assert rubrics.load(scenario['rubric'],'linux_fault').version==policy.version
        assert 'five_reference_goals_pass' in scenario['validity_report']['checks']
        attempts=await db.fetch('SELECT * FROM generation_jobs WHERE work_item_id=$1 ORDER BY created_at',work.id)
        assert not attempts, 'Authored simulator coaching must not call a model.'
        child=await learning.retest(parent.id)
        again=await service.start(Start(track_id=queue['track_id'],consent=True))
        assert again.id==child.id and child.engine_id=='linux_fault' and len(child.steps)==5
        # The retest is the next run of the original track, not a separate plan card.
        listed=await service.get_plan(plan.id)
        assert queue['track_id'] not in {t.id for t in listed.tracks}
        origin=next(t for t in listed.tracks if t.id==parent.track_id)
        assert origin.next_focus and origin.next_focus.session_id==parent.id and origin.next_focus.evidence_seq==[event.seq]
        assert (await service.start(Start(track_id=origin.id,consent=True))).id==child.id
        assert 'current or historical' in child.steps[4].task
        assert child.events[0].payload['evidence_seq']==[event.seq]
        assert child.events[0].payload['source_session_id']==parent.id
        assert '_lab' not in child.engine_state
        output=await labs.action(child.id,LabAction(request_id=uuid4().hex,revision=0,step=0,kind='command',text='systemctl status site'))
        assert ':4000' in output.events[0].payload['output']
        parent_state=await service.require_session(parent.id)
        assert parent_state['engine_state']['_lab']['app_port']==3000
        print('Pi learning acceptance: authored coaching without provider calls, changed reference-tested engine, same rubric, source citations and idempotent retest passed (synthetic fixtures).')
    finally:
        if db._pool:await db._pool.close();db._pool=None
        config.DATABASE_URL,config.V2_DATABASE_SCHEMA,config.BACKBOARD_API_KEY,service.DEMO,generation.DEMO,learning.generate=prior
