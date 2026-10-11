"""One opt-in real Gemini plan/review check in a disposable Tiger schema.

Not part of the automated suite: --live explicitly allows paid provider calls.
No user records are used. A failed check is reported without automatic reruns.
"""
import argparse
import asyncio
import json
import os
from pathlib import Path
import subprocess
import sys
from uuid import uuid4

import asyncpg

from app import config
from app.v2 import db, generation, jobs, planning, sources
from app.v2.models import Intake, SourceInput

ROOT = Path(__file__).resolve().parents[2]


async def main():
    if generation.DEMO or not config.GEMINI_API_KEY:
        raise RuntimeError('Live Gemini settings are required; this check will not silently use fixtures.')
    schema = 'prepcrew_e2e_live_' + uuid4().hex
    admin = await asyncpg.connect(config.DATABASE_URL)
    created = False
    prior_schema = config.V2_DATABASE_SCHEMA
    assert db._pool is None
    try:
        await admin.execute(f'CREATE SCHEMA "{schema}"')
        created = True
        env = {**os.environ, 'PYTHONPATH': str(ROOT/'backend'), 'V2_DATABASE_SCHEMA': schema}
        out = ROOT / '.artifacts'
        out.mkdir(exist_ok=True)
        with (out/'live-plan-migration.log').open('w',encoding='utf-8') as log:
            migration = await asyncio.to_thread(subprocess.run,
                [sys.executable,'-m','alembic','-c','backend/alembic.ini','upgrade','head'],
                cwd=ROOT,env=env,stdout=log,stderr=subprocess.STDOUT,
                creationflags=subprocess.CREATE_NO_WINDOW if os.name=='nt' else 0)
        if migration.returncode:
            raise RuntimeError('Disposable migration failed; inspect ignored migration log.')
        config.V2_DATABASE_SCHEMA = schema
        owner = 'synthetic-live-plan-' + uuid4().hex
        doc = await sources.create(SourceInput(user_id=owner,kind='job_posting',title='Synthetic job description',
            body='Synthetic practice role: embedded firmware engineer. Practice sensor interfaces, power debugging, C drivers and explaining engineering trade-offs.'))
        body = Intake(user_id=owner,name='Synthetic live acceptance',role='Embedded firmware engineer',
            companies=[],struggles=['Circuits & power','Embedded C'],question='How would you debug a sensor board that fails under load?',source_ids=[doc.id])
        job = await planning.enqueue(body)
        await jobs.execute(job.id)
        result = await jobs.read(job.id)
        audits = [dict(r) for r in await db.fetch('SELECT kind,model,status,tokens_in,tokens_out,latency_ms,error FROM generation_jobs WHERE work_item_id=$1 ORDER BY created_at',job.id)]
        print(json.dumps({'status':result.status,'model_attempts':audits,'cost_usd':None,
            'cost_note':'Provider token usage recorded; billed dollars not available from this response.'},indent=2))
        if result.status != 'succeeded':
            raise RuntimeError('Live plan/review did not publish; no rerun performed.')
        plan_id = result.result['plan_id']
        plan = await db.one('SELECT primary_domain,job_id,inference FROM plans WHERE id=$1',plan_id)
        assert plan['job_id'] and plan['inference']['check_job_id']
        assert await db.one("SELECT id FROM scenarios WHERE job_id=$1 AND validity='passed'",plan['job_id'])
        assert not await db.fetch('SELECT * FROM skill_assessments WHERE user_id=$1',owner)
        print('Live plan and independent review published a checked conceptual scenario without ability scores.')
    finally:
        if db._pool:
            await db._pool.close()
            db._pool = None
        config.V2_DATABASE_SCHEMA = prior_schema
        if created:
            await admin.execute(f'DROP SCHEMA "{schema}" CASCADE')
        await admin.close()
        print('Disposable live acceptance schema removed.')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--live',action='store_true',required=True)
    parser.parse_args()
    if hasattr(sys.stdout,'reconfigure'):sys.stdout.reconfigure(encoding='utf-8')
    asyncio.run(main())
