"""Real account/ownership acceptance in the harness's disposable Tiger schema.

Synthetic identities only. No providers or real workspace records are used.
"""
import asyncio
from uuid import uuid4
import httpx
from starlette.responses import Response
from app import config
from app.main import app
from app.v2 import auth,db


async def verify(source,schema):
    assert schema.startswith('prepcrew_e2e_') and schema.replace('_','').isalnum()
    keys=('DATABASE_URL','V2_DATABASE_SCHEMA','V2_AUTH_TEST_BYPASS','LEGACY_API_ENABLED','AUTH_COOKIE_SECURE')
    prior={key:getattr(config,key) for key in keys}
    assert db._pool is None
    config.DATABASE_URL,config.V2_DATABASE_SCHEMA=source,schema
    config.V2_AUTH_TEST_BYPASS=False;config.LEGACY_API_ENABLED=False;config.AUTH_COOKIE_SECURE=False
    headers={'X-PrepCrew-Request':'1'}
    password='synthetic-password-acceptance-123'
    tag=uuid4().hex
    transport=httpx.ASGITransport(app=app)
    try:
        async with httpx.AsyncClient(transport=transport,base_url='http://testserver',headers=headers) as a, \
                   httpx.AsyncClient(transport=transport,base_url='http://testserver',headers=headers) as b:
            users=[]
            for client,label in ((a,'a'),(b,'b')):
                response=await client.post('/api/v2/auth/register',json={'name':'Synthetic auth fixture','email':f'{label}-{tag}@example.test','password':password})
                assert response.status_code==201
                users.append(response.json()['user'])
                cookie=response.headers['set-cookie']
                assert 'HttpOnly' in cookie and 'SameSite=lax' in cookie
            owner,other=[u['id'] for u in users]
            stored=await db.one('SELECT password_hash FROM accounts WHERE user_id=$1',owner)
            assert stored['password_hash'].startswith('$argon2id$') and password not in stored['password_hash']
            token=a.cookies.get(auth.COOKIE)
            assert await db.one('SELECT token_hash FROM auth_sessions WHERE token_hash=$1',auth.digest(token))
            assert not await db.one('SELECT token_hash FROM auth_sessions WHERE token_hash=$1',token)
            # Minimal authored/synthetic resources isolate authorization from model output.
            tid,sid,pid,aid,source_id,jid=[tag+'-'+name for name in ('track','session','plan','artifact','source','job')]
            await db.execute("INSERT INTO plans(id,user_id,status) VALUES($1,$2,'ready')",pid,owner)
            await db.execute("INSERT INTO tracks(id,user_id,plan_id,domain_id,engine_id,layer,title,source,status) VALUES($1,$2,$3,'sw','conceptual',3,'Synthetic account fixture','catalog','ready')",tid,owner,pid)
            await db.execute("INSERT INTO scenarios(id,track_id,engine_id,engine_version,spec,validity) VALUES($1,$2,'conceptual','1',$3,'passed')",tag+'-scenario',tid,{'prompt':'Synthetic fixture, not a generated exercise.'})
            async with (await db.pool()).acquire() as conn:
                await conn.executemany("INSERT INTO sessions(id,user_id,track_id,scenario_id,status) VALUES($1,$2,$3,$4,'live')",[(sid+str(i),owner,tid,tag+'-scenario') for i in range(23)])
            await db.execute("INSERT INTO artifacts(id,session_id,kind,blob_key) VALUES($1,$2,'whiteboard_png',$3)",aid,sid+'0','synthetic-auth-canary.png')
            await db.execute("INSERT INTO source_documents(id,user_id,kind,title,body) VALUES($1,$2,'notes','Synthetic private note','Synthetic private content')",source_id,owner)
            await db.execute("INSERT INTO work_items(id,user_id,kind,subject_id,cache_key,payload,status) VALUES($1,$2,'lesson',$3,$1,$4,'cancelled')",jid,owner,sid+'0',{'synthetic':True})
            for path in (f'/plans/{pid}',f'/sessions/{sid}0/events',f'/artifacts/{aid}/png',f'/sources/{source_id}',f'/jobs/{jid}',f'/users/{owner}/sources'):
                response=await b.get('/api/v2'+path)
                assert response.status_code==404,path
                assert 'Synthetic private' not in response.text
            assert (await b.post('/api/v2/retests',json={'session_id':sid+'0'})).status_code==404
            assert (await b.post('/api/v2/sessions',json={'track_id':tid,'consent':True})).status_code==404
            assert (await a.get('/api/v2/sessions/'+sid+'0/events')).status_code==200
            first=(await a.get('/api/v2/history')).json()
            assert first['latest_plan_id']==pid and len(first['sessions'])==20 and first['next_cursor']
            last=(await a.get('/api/v2/history',params={'before':first['next_cursor']})).json()
            assert len(last['sessions'])==3 and not last['next_cursor']
            assert len({s['id'] for s in first['sessions']+last['sessions']})==23
            assert (await b.get('/api/v2/history')).json()['sessions']==[]
            assert (await b.get('/api/v2/history',params={'before':first['next_cursor']})).status_code==404
            # Duplicate registration cannot attach an old user or replace its password.
            duplicate=await b.post('/api/v2/auth/register',json={'name':'Synthetic duplicate','email':users[0]['email'],'password':password})
            assert duplicate.status_code==409
            await db.execute("UPDATE auth_sessions SET expires_at=now()-interval '1 second' WHERE token_hash=$1",auth.digest(token))
            assert (await a.get('/api/v2/history')).status_code==401
            bad=await a.post('/api/v2/auth/login',json={'email':users[0]['email'],'password':'synthetic-wrong-password'})
            assert bad.status_code==401
            login=await a.post('/api/v2/auth/login',json={'email':users[0]['email'],'password':password})
            assert login.status_code==200 and a.cookies.get(auth.COOKIE)!=token
            revoked=a.cookies.get(auth.COOKIE)
            assert (await a.post('/api/v2/auth/logout',json={})).status_code==200
            a.cookies.set(auth.COOKIE,revoked)
            assert (await a.get('/api/v2/history')).status_code==401
            assert not await db.one('SELECT token_hash FROM auth_sessions WHERE token_hash=$1',auth.digest(revoked))
            await asyncio.gather(*(auth.issue(Response(),owner) for _ in range(12)))
            count=await db.one('SELECT count(*) AS n FROM auth_sessions WHERE user_id=$1',owner)
            assert count['n']==10
            # Trusted local binding can preserve an old workspace ID; registration cannot.
            from bind_account import bind
            legacy=tag+'-pre-account'
            await db.execute("INSERT INTO users(id,display_name) VALUES($1,'Synthetic pre-account workspace')",legacy)
            await bind(legacy,f'legacy-{tag}@example.test',password)
            bound=await a.post('/api/v2/auth/login',json={'email':f'legacy-{tag}@example.test','password':password})
            assert bound.status_code==200 and bound.json()['user']['id']==legacy
            # Soft deletion also invalidates an otherwise unexpired cookie.
            await db.execute('UPDATE users SET deleted_at=now() WHERE id=$1',other)
            assert (await b.get('/api/v2/history')).status_code==401
            missing={'email':f'missing-{tag}@example.test','password':password}
            results=[(await a.post('/api/v2/auth/login',json=missing)).status_code for _ in range(13)]
            assert results[:12]==[401]*12 and results[12]==429
            attempts=await db.fetch('SELECT key FROM auth_attempts')
            assert all(len(row['key'])==64 and '@' not in row['key'] for row in attempts)
        print('Synthetic Tiger account acceptance passed: hashed sessions/passwords, ownership, pagination, expiry/revocation and shared rate limits; no paid providers.')
    finally:
        if db._pool:await db._pool.close();db._pool=None
        for key,value in prior.items():setattr(config,key,value)
