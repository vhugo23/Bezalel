"""Implicit-memory acceptance on a disposable Tiger schema and mock Backboard.

Fixtures are synthetic, including the deliberately fabricated remote content.
No paid provider calls or real candidate records are used.
"""
import asyncio
import json
from uuid import uuid4

import httpx

from app import config
from app.v2 import db, memory, rubrics


async def verify(source,schema):
    assert schema.startswith('prepcrew_e2e_') and schema.replace('_','').isalnum()
    prior=(config.DATABASE_URL,config.V2_DATABASE_SCHEMA,config.BACKBOARD_API_KEY,config.MEMORY_BACKEND,memory.DEMO,memory._transport)
    assert db._pool is None
    config.DATABASE_URL,config.V2_DATABASE_SCHEMA=source,schema
    config.BACKBOARD_API_KEY,config.MEMORY_BACKEND,memory.DEMO='synthetic-key','backboard',False
    remote={};assistants=[];adds=0;entered=asyncio.Event();release=asyncio.Event();race=False
    async def transport(request):
        nonlocal adds
        path=request.url.path.removeprefix('/api/');method=request.method
        body=json.loads(request.content) if request.content else {}
        if path=='assistants':
            if method=='GET':return httpx.Response(200,json=[a for a in assistants if a['name']==request.url.params.get('name')])
            a={'assistant_id':'synthetic-assistant','name':body['name']};assistants.append(a)
            return httpx.Response(200,json=a)
        if path.endswith('/memories/search'):
            return httpx.Response(200,json={'memories':[{'id':mid,'content':'Fabricated remote text: this must never become an opener.'} for mid in remote]})
        if path.endswith('/memories'):
            if method=='GET':return httpx.Response(200,json={'memories':list(remote.values()),'total_pages':1})
            adds+=1;mid='synthetic-external-'+str(adds)
            remote[mid]={'id':mid,**body}
            if race:entered.set();await release.wait()
            return httpx.Response(201,json={'memory_id':mid})
        if method=='DELETE':
            mid=path.rsplit('/',1)[1]
            if mid not in remote:return httpx.Response(404)
            del remote[mid];return httpx.Response(204)
        raise AssertionError('Unexpected mocked Backboard route')
    memory._transport=httpx.MockTransport(transport)
    owner,track,scenario,session,run,claim,mid=[str(uuid4()) for _ in range(7)]
    text='Synthetic candidate incorrectly equated failing closed with availability.'
    task=None
    try:
        async with (await db.pool()).acquire() as conn,conn.transaction():
            await conn.execute('INSERT INTO users(id) VALUES($1)',owner)
            await conn.execute("INSERT INTO tracks(id,user_id,domain_id,engine_id,layer,title,source,status) VALUES($1,$2,'sw','conceptual',3,'Synthetic memory fixture','catalog','ready')",track,owner)
            await conn.execute("INSERT INTO scenarios(id,track_id,engine_id,engine_version,spec,validity) VALUES($1,$2,'conceptual','1',$3,'passed')",scenario,track,{'prompt':'Synthetic memory fixture','steps':['Clarify','Draw','Explain']})
            await conn.execute("INSERT INTO sessions(id,user_id,track_id,scenario_id,status) VALUES($1,$2,$3,$4,'graded')",session,owner,track,scenario)
            seq=await conn.fetchval("INSERT INTO session_events(session_id,kind,actor,step,payload) VALUES($1,'turn','candidate',2,$2) RETURNING seq",session,{'text':'Failing closed guarantees availability.'})
            await conn.execute("INSERT INTO evaluator_runs(id,session_id,evaluator,status,prompt_version) VALUES($1,$2,'Trade-offs','done',$3)",run,session,rubrics.VERSION)
            await conn.execute("INSERT INTO claims(id,run_id,session_id,skill_id,text,polarity,evidence_seq,check_status) VALUES($1,$2,$3,'sw.system_design',$4,'gap',$5,'verified')",claim,run,session,text,[seq])
            await conn.execute('INSERT INTO session_reports(session_id,report,stats) VALUES($1,$2,$3)',session,{'rubric_version':rubrics.VERSION},{'partial':False,'synthetic':True})
            await conn.execute("INSERT INTO skill_assessments(user_id,skill_id,score,source,session_id,claim_ids) VALUES($1,'sw.system_design',25,'session',$2,$3)",owner,session,[claim])
            await conn.execute("INSERT INTO memories(id,owner_id,text,kind,skill_id,source_session_id,source_claim_id) VALUES($1,$2,$3,'gap','sw.system_design',$4,$5)",mid,owner,text,session,claim)
        await memory.sync(mid);await memory.sync(mid)
        assert adds==1 and len(remote)==1
        result=await memory.recall(owner,['sw.system_design'],'failure policy')
        assert result['text']==text and result['retrieval']=='backboard' and result['evidence_seq']==[seq]
        assert await memory.recall('wrong-owner',['sw.system_design'],'failure policy') is None
        assert await memory.recall(owner,['hw.circuit_probing'],'circuit') is None
        calibrated=await memory.calibration(owner,['sw.system_design'],rubrics.VERSION)
        assert calibrated['level']==1 and calibrated['source_session_id']==session and calibrated['evidence_seq']==[seq]
        assert (await memory.calibration(owner,['sw.system_design'],'another-rubric'))['source']=='default_practice_setting'
        await db.execute("UPDATE memories SET data=jsonb_build_object('resolved',true),salience=0 WHERE id=$1",mid)
        assert await memory.recall(owner,['sw.system_design'],'failure') is None
        await memory.sync(mid);assert not remote

        # Resolution/deletion during a provider POST must leave a newer queued
        # tombstone with the newly returned external reference, then erase it.
        race=True
        await db.execute("UPDATE memories SET data='{}',salience=.5,external_id=NULL WHERE id=$1",mid)
        await db.execute('UPDATE memory_sync SET external_id=NULL WHERE memory_id=$1',mid)
        task=asyncio.create_task(memory.sync(mid))
        await asyncio.wait_for(entered.wait(),5)
        await db.execute('DELETE FROM memories WHERE id=$1',mid)
        release.set();await asyncio.wait_for(task,5)
        tombstone=await db.one('SELECT * FROM memory_sync WHERE memory_id=$1',mid)
        assert tombstone['operation']=='delete' and tombstone['status']=='queued' and tombstone['external_id']
        await memory.sync(mid)
        assert not remote and (await db.one('SELECT status FROM memory_sync WHERE memory_id=$1',mid))['status']=='succeeded'
        assert 'text' not in tombstone and 'payload' not in tombstone
        print('Implicit-memory acceptance: canonical citations, owner/skill isolation, calibration, resolution and in-flight deletion recovery passed (synthetic/mock fixtures).')
    finally:
        if task and not task.done():
            task.cancel();await asyncio.gather(task,return_exceptions=True)
        if db._pool:
            await db._pool.close();db._pool=None
        config.DATABASE_URL,config.V2_DATABASE_SCHEMA,config.BACKBOARD_API_KEY,config.MEMORY_BACKEND,memory.DEMO,memory._transport=prior
