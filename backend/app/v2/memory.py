"""Implicit memory: Backboard ranks, verified Postgres evidence authorizes.

No generated/remote text is promoted into a candidate fact. Deletion outbox
rows contain references only, and survive local cascades until remote erasure.
"""
import asyncio
import hashlib
import logging
import re
import time

import httpx

from app import config
from . import db
from .generation import DEMO

logger = logging.getLogger(__name__)
_transport = None  # deterministic tests inject MockTransport, never real keys.

ACTIVE = """m.kind='gap' AND m.salience>0 AND NOT (m.data @> '{"resolved":true}'::jsonb)
    AND c.check_status='verified' AND c.polarity='gap' AND c.text=m.text
    AND s.user_id=m.owner_id AND s.status='graded' AND cardinality(c.evidence_seq)>0
    AND NOT coalesce((r.stats->>'partial')::boolean,true)
    AND r.report->>'rubric_version'=e.prompt_version
    AND e.attempt=(SELECT max(latest.attempt) FROM evaluator_runs latest
        WHERE latest.session_id=s.id AND latest.evaluator=e.evaluator)
    AND NOT EXISTS(SELECT 1 FROM unnest(c.evidence_seq) ref(seq) WHERE NOT EXISTS(
        SELECT 1 FROM session_events event WHERE event.session_id=s.id AND event.seq=ref.seq AND event.actor='candidate'))"""
JOINS = '''FROM memories m JOIN claims c ON c.id=m.source_claim_id
    JOIN sessions s ON s.id=m.source_session_id AND s.id=c.session_id
    JOIN evaluator_runs e ON e.id=c.run_id JOIN session_reports r ON r.session_id=s.id'''


def enabled():
    return bool(config.BACKBOARD_API_KEY) and not DEMO and config.MEMORY_BACKEND not in ('postgres','memory')


class ProviderError(Exception):
    def __init__(self, status):
        self.status = status
        super().__init__(f'Backboard HTTP {status}')


def safe_id(value):
    if not isinstance(value, str) or not re.fullmatch(r'[A-Za-z0-9_-]{1,120}', value):
        raise ValueError('Invalid external memory identifier')
    return value


async def request(method, path, **kwargs):
    if not config.BACKBOARD_API_KEY:
        raise ProviderError(401)
    async with httpx.AsyncClient(base_url=config.BACKBOARD_BASE_URL.rstrip('/')+'/',
            headers={'X-API-Key':config.BACKBOARD_API_KEY},timeout=5,
            follow_redirects=False,trust_env=False,transport=_transport) as client:
        response = await client.request(method,path.lstrip('/'),**kwargs)
    if response.status_code >= 300:
        raise ProviderError(response.status_code)  # never include provider bodies.
    return response.json() if response.content else {}


async def assistant(owner, conn, mid):
    # Held across lookup/create/persist, and shared by all worker processes.
    await conn.execute("SELECT pg_advisory_lock(hashtextextended('bb-owner:' || $1,0))",owner)
    try:
        row = await conn.fetchrow('SELECT assistant_id FROM memory_accounts WHERE user_id=$1',owner)
        if row:
            return safe_id(row['assistant_id'])
        name='prepcrew-v2-'+hashlib.sha256((config.V2_DATABASE_SCHEMA+':'+owner).encode()).hexdigest()[:32]
        found = await request('GET','assistants',params={'name':name,'limit':2})
        # Current REST list response is an array; accepting the documented SDK
        # envelope as well does not grant access to a different assistant name.
        items=found if isinstance(found,list) else found.get('assistants',[])
        matches=[a for a in items if a.get('name')==name]
        if matches:
            aid=safe_id(matches[0].get('assistant_id'))
        else:
            out=await request('POST','assistants',json={'name':name,
                'system_prompt':'Store only explicitly supplied, evidence-verified PrepCrew practice gaps. Never infer new candidate facts.'})
            aid=safe_id(out.get('assistant_id'))
        # Keep the erasure reference even if the user is deleted before the
        # account mapping can be inserted.
        await conn.execute('UPDATE memory_sync SET assistant_id=$2 WHERE memory_id=$1',mid,aid)
        await conn.execute('INSERT INTO memory_accounts(user_id,assistant_id) SELECT id,$2 FROM users WHERE id=$1 AND deleted_at IS NULL ON CONFLICT(user_id) DO NOTHING',owner,aid)
        return aid
    finally:
        await asyncio.shield(conn.execute("SELECT pg_advisory_unlock(hashtextextended('bb-owner:' || $1,0))",owner))


async def remote_matches(aid, mid):
    # Recover a successful POST whose response/persistence was lost. Metadata is
    # available on list/get, but NOT on semantic-search results (API contract).
    matches=[]
    for page in range(1,6):
        out=await request('GET',f'assistants/{safe_id(aid)}/memories',params={'page':page,'page_size':100})
        items=out.get('memories',[])
        found=[safe_id(m.get('memory_id') or m.get('id')) for m in items
               if (m.get('metadata') or {}).get('prepcrew_memory_id')==mid]
        matches.extend(found)
        if len(items)<100 or page>=out.get('total_pages',page+1):return list(dict.fromkeys(matches))
    raise ValueError('Memory recovery page limit reached')


async def active(mid):
    return await db.one('SELECT m.*,c.evidence_seq,c.rubric_id '+JOINS+' WHERE m.id=$1 AND '+ACTIVE,mid)


async def sync(mid):
    if not enabled():return
    async with (await db.pool()).acquire() as conn:
        if not await conn.fetchval("SELECT pg_try_advisory_lock(hashtextextended('bb-memory:' || $1,0))",mid):return
        rev=None;start=time.perf_counter()
        try:
            exhausted=await conn.fetchrow("SELECT memory_id FROM memory_sync WHERE memory_id=$1 AND status IN ('queued','running') AND attempts>=3",mid)
            if exhausted:
                await conn.execute("UPDATE memory_sync SET status='failed',error='Memory recovery limit reached; local evidence is retained.' WHERE memory_id=$1",mid)
                return
            row=await conn.fetchrow("UPDATE memory_sync SET status='running',attempts=attempts+1,error=NULL,updated_at=now() WHERE memory_id=$1 AND status IN ('queued','running') AND attempts<3 RETURNING *",mid)
            if not row:return
            rev=row['revision'];aid=row['assistant_id'];external=row['external_id']
            local=await active(mid) if row['operation']=='upsert' else None
            if local:
                owner=await conn.fetchrow('SELECT id FROM users WHERE id=$1 AND deleted_at IS NULL',row['owner_id'])
                if owner:
                    aid=aid or await assistant(row['owner_id'],conn,mid)
                    ids=[external] if external else await remote_matches(aid,mid)
                    if ids:
                        external=ids[0]
                    else:
                        out=await request('POST',f'assistants/{safe_id(aid)}/memories',json={
                            'content':local['text'],'metadata':{'prepcrew_memory_id':mid,
                                'source_session_id':local['source_session_id'],
                                'source_claim_id':local['source_claim_id'],'evidence_seq':local['evidence_seq']}})
                        external=safe_id(out.get('memory_id') or out.get('id'))
                    await conn.execute("UPDATE memories SET backend='backboard',external_id=$2 WHERE id=$1",mid,external)
                else:
                    local=None
            if not local:
                if not aid:
                    account=await conn.fetchrow('SELECT assistant_id FROM memory_accounts WHERE user_id=$1',row['owner_id'])
                    aid=account['assistant_id'] if account else None
                ids=list(dict.fromkeys(([external] if external else [])+await remote_matches(aid,mid))) if aid else []
                for remote in ids:
                    try:await request('DELETE',f'assistants/{safe_id(aid)}/memories/{safe_id(remote)}')
                    except ProviderError as exc:
                        if exc.status!=404:raise
            # Save references even if deletion/resolution arrived during the
            # remote call. Its newer revision remains queued for cleanup.
            await conn.execute('UPDATE memory_sync SET assistant_id=coalesce($2,assistant_id),external_id=coalesce($3,external_id) WHERE memory_id=$1',mid,aid,external)
            await conn.execute("UPDATE memory_sync SET status='succeeded',latency_ms=$3,updated_at=now() WHERE memory_id=$1 AND revision=$2",mid,rev,round((time.perf_counter()-start)*1000))
        except asyncio.CancelledError:
            # Running is recoverable; the advisory lock releases on shutdown.
            raise
        except Exception as exc:
            logger.warning('Memory synchronization failed: %s',type(exc).__name__)
            if rev is not None:
                terminal=isinstance(exc,ProviderError) and exc.status in (400,401,403,422)
                await conn.execute("UPDATE memory_sync SET status=CASE WHEN attempts>=3 OR $3 THEN 'failed' ELSE 'queued' END,error=$4,next_at=now()+attempts*interval '10 seconds',updated_at=now() WHERE memory_id=$1 AND revision=$2",mid,rev,terminal,'Backboard unavailable; verified local memory remains available.')
        finally:
            await asyncio.shield(conn.execute("SELECT pg_advisory_unlock(hashtextextended('bb-memory:' || $1,0))",mid))


def ranked_local(rows, remote_ids):
    # Use remote IDs for ordering only; never remote content or inferred facts.
    by_external={r['external_id']:r for r in rows if r.get('external_id')}
    result=[]
    for rid in remote_ids:
        if rid in by_external and by_external[rid] not in result:result.append(by_external[rid])
    result.extend(r for r in rows if r not in result)
    return result


async def recall(owner, skill_ids, query):
    rows=[dict(r) for r in await db.fetch('SELECT m.*,c.evidence_seq '+JOINS+
        ' WHERE m.owner_id=$1 AND c.skill_id=ANY($2::text[]) AND '+ACTIVE+' ORDER BY m.created_at DESC LIMIT 20',owner,skill_ids)]
    if not rows:return None
    if enabled():
        account=await db.one('SELECT assistant_id FROM memory_accounts WHERE user_id=$1',owner)
        if account:
            try:
                out=await asyncio.wait_for(request('POST',f"assistants/{safe_id(account['assistant_id'])}/memories/search",
                    json={'query':query[:2000],'limit':10}),timeout=1)
                remote_ids=[str(m.get('id') or m.get('memory_id')) for m in out.get('memories',[])]
                ranked=ranked_local(rows,remote_ids)
                return {**ranked[0],'retrieval':'backboard' if ranked[0].get('external_id') in remote_ids else 'postgres'}
            except Exception:pass  # Retrieval is optional; local evidence is canonical.
    return {**rows[0],'retrieval':'postgres'}


def follow_up_depth(score, baseline=2):
    # Authored practice settings, not validated measurements of human ability.
    return max(1,min(5,baseline+(1 if score>=75 else -1 if score<50 else 0)))


async def calibration(owner, skill_ids, version, baseline=2):
    row=await db.one('''SELECT a.score,a.session_id,a.claim_ids FROM skill_assessments a
        JOIN sessions s ON s.id=a.session_id JOIN session_reports r ON r.session_id=s.id
        WHERE a.user_id=$1 AND s.user_id=$1 AND a.skill_id=ANY($2::text[]) AND a.source IN ('session','retest')
          AND NOT a.is_estimate AND s.status='graded' AND NOT coalesce((r.stats->>'partial')::boolean,true)
          AND r.report->>'rubric_version'=$3 AND cardinality(a.claim_ids)>0
          AND NOT EXISTS(SELECT 1 FROM unnest(a.claim_ids) ref(id) LEFT JOIN claims c ON c.id=ref.id
            LEFT JOIN evaluator_runs e ON e.id=c.run_id WHERE c.check_status IS DISTINCT FROM 'verified'
              OR c.session_id IS DISTINCT FROM a.session_id OR e.prompt_version IS DISTINCT FROM $3
              OR e.attempt<>(SELECT max(latest.attempt) FROM evaluator_runs latest WHERE latest.session_id=s.id AND latest.evaluator=e.evaluator)
              OR cardinality(c.evidence_seq)=0 OR EXISTS(SELECT 1 FROM unnest(c.evidence_seq) evidence(seq)
                WHERE NOT EXISTS(SELECT 1 FROM session_events event WHERE event.session_id=a.session_id
                    AND event.seq=evidence.seq AND event.actor='candidate')))
        ORDER BY a.ts DESC LIMIT 1''',owner,skill_ids,version)
    if not row:return {'level':baseline,'source':'default_practice_setting'}
    claims=await db.fetch('SELECT evidence_seq FROM claims WHERE id=ANY($1::text[])',row['claim_ids'])
    return {'level':follow_up_depth(row['score'],baseline),'source':'verified_practice_assessment',
            'source_session_id':row['session_id'],'evidence_seq':sorted({seq for c in claims for seq in c['evidence_seq']}),
            'claim_ids':row['claim_ids']}


async def worker():
    while True:
        if enabled():
            try:
                # A worker lost on its third execution is terminal, not stranded.
                for row in await db.fetch("SELECT memory_id FROM memory_sync WHERE status IN ('queued','running') AND next_at<=now() ORDER BY next_at LIMIT 20"):
                    await sync(row['memory_id'])
            except asyncio.CancelledError:raise
            except Exception as exc:logger.warning('Memory queue unavailable: %s',type(exc).__name__)
        await asyncio.sleep(5)
