"""One opt-in real Gemini job scan and ATS review in a disposable Tiger schema.

Not part of the automated suite: --live explicitly allows paid provider calls.
Without --live it only prints what it would do. No user records are used: the
resume and the job posting below are SYNTHETIC. A failed check is reported
without automatic reruns. Keys and connection strings are never printed.

Run from the repository root:
  PYTHONPATH=backend python backend/scripts/verify_live_ats.py          (dry run)
  PYTHONPATH=backend python backend/scripts/verify_live_ats.py --live   (paid)
"""
import argparse
import asyncio
import json
import os
from pathlib import Path
import re
import subprocess
import sys
from uuid import uuid4

import asyncpg

from app import config
from app.v2 import db, generation, jobs, resume, sources
from app.v2.models import AtsApply, AtsCategoryDraft, SourceInput

ROOT = Path(__file__).resolve().parents[2]

# SYNTHETIC resume. Not a real person, employer or school.
RESUME = '''Sam Placeholder
sam.placeholder@example.com | (555) 010-0142 | Example City

Summary
Software engineer with 3 years of experience working on backend services and internal tools.

Experience
Example Logistics Co, Software Engineer, 2022 - 2025
- Responsible for the Python services that route orders between 14 regional warehouses.
- Worked on moving the nightly reporting jobs from cron to a PostgreSQL-backed queue.
- Helped with code reviews and was involved in onboarding of new engineers.
- Wrote unit and integration tests in pytest for the order routing service.

Example Campus Lab, Student Developer, 2020 - 2022
- Made a Flask dashboard that shows lab equipment bookings.

Skills
Python, Flask, PostgreSQL, pytest, Git, Linux

Education
B.S. Computer Science, Example State University, 2022'''

# SYNTHETIC job posting. Kubernetes and Go are deliberately absent from the resume.
POSTING = '''Backend Engineer (synthetic practice posting)

We are hiring a backend engineer for our order platform team.

Requirements
- 2+ years of professional experience with Python.
- Strong experience with PostgreSQL and schema design.
- Experience running services on Kubernetes.
- Automated testing with pytest or a similar framework.

Nice to have
- Experience with Go.
- Familiarity with message queues.'''


def plan():
    print('Dry run. Nothing was called. With --live this script would:')
    print('  1. create a disposable schema in the configured database and migrate it (dropped at the end);')
    print('  2. save one SYNTHETIC resume and one SYNTHETIC job posting, embedded in this file;')
    print('  3. run job_scan then a tailored ats_review through the real queue: two paid Gemini calls,')
    print('     or up to four if a call needs its one validation retry;')
    print('  4. print whether each schema was accepted, the score computed in code, suggestions accepted')
    print('     and rejected by the local guards, and token counts and latency per model attempt.')
    print('It needs DATABASE_URL (with CREATE SCHEMA rights), GEMINI_API_KEY and DEMO_MODE not true.')
    print(json.dumps({'database_configured': bool(config.DATABASE_URL), 'gemini_key_configured': bool(config.GEMINI_API_KEY),
                      'recorded_mode': generation.DEMO}))


async def run(job):
    await jobs.execute(job.id)
    return await jobs.read(job.id)


def check(review, requirements, body, posting):
    """Recompute the product rules on what was actually saved."""
    assert review.score == resume.score([AtsCategoryDraft(id=item.id, rating=item.rating, findings=[]) for item in review.categories], True)[0]
    assert all(finding.quote is None or finding.quote in body for item in review.categories for finding in item.findings)
    assert all(item['quote'] in posting and item['term'].lower() in item['quote'].lower() for item in requirements)
    assert all(row.quote in posting and (row.resume_quote is None or row.resume_quote in body) for row in review.coverage)
    absent = resume.missing_terms(review.coverage)
    for item in review.suggestions:
        assert body[item.start:item.end] == item.original and body.count(item.original) == 1
        # No accepted change adds a number, a name or a requirement the resume does not have.
        assert resume._added_claim(body, body[:item.start] + item.replacement + body[item.end:], absent) is None
    chosen = [item.id for item in review.suggestions]
    assert resume._added_claim(body, resume.apply_suggestions(body, review.suggestions, chosen), absent) is None


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
        with (out/'live-ats-migration.log').open('w',encoding='utf-8') as log:
            migration = await asyncio.to_thread(subprocess.run,
                [sys.executable,'-m','alembic','-c','backend/alembic.ini','upgrade','head'],
                cwd=ROOT,env=env,stdout=log,stderr=subprocess.STDOUT,
                creationflags=subprocess.CREATE_NO_WINDOW if os.name=='nt' else 0)
        if migration.returncode:
            raise RuntimeError('Disposable migration failed; inspect ignored migration log.')
        config.V2_DATABASE_SCHEMA = schema
        owner = 'synthetic-live-ats-' + uuid4().hex
        posting = await sources.create(SourceInput(user_id=owner,kind='job_posting',title='Synthetic job posting',body=POSTING))
        document = await sources.create(SourceInput(user_id=owner,kind='resume',title='Synthetic resume',body=RESUME))
        scan = await run(await resume.enqueue_scan(posting.id))
        review = await run(await resume.enqueue_review(document.id,posting.id)) if scan.status == 'succeeded' else None
        items = [scan.id] + ([review.id] if review else [])
        audits = [dict(r) for r in await db.fetch('SELECT kind,attempt,model,status,schema_ok,tokens_in,tokens_out,latency_ms,error FROM generation_jobs WHERE work_item_id=ANY($1::text[]) ORDER BY created_at',items)]
        accepted = lambda kind: any(a['kind'] == kind and a['schema_ok'] for a in audits)
        report = {'job_scan': {'status':scan.status,'schema_accepted':accepted('job_scan')},
            'ats_review': {'status':review.status if review else 'not run','schema_accepted':accepted('ats_review')},
            'model_attempts':audits,'cost_usd':None,
            'cost_note':'Provider token usage recorded; billed dollars not available from this response.'}
        if not review or review.status != 'succeeded':
            print(json.dumps(report,indent=2))
            raise RuntimeError('Live scan/review did not publish; no rerun performed.')
        requirements = (await sources.read(posting.id))['extracted']['requirements']
        saved = await resume.read_review(document.id,posting.id)
        report.update({'requirements_kept':len(requirements),'score_computed_in_code':saved.score,
            'ratings':{item.id:item.rating for item in saved.categories},
            'suggestions_accepted':len(saved.suggestions),'suggestions_rejected_by_guards':saved.rejected,
            'coverage':{row.term:row.status for row in saved.coverage},'facts':saved.facts.model_dump()})
        print(json.dumps(report,indent=2))
        assert saved.provider == 'gemini' and saved.score is not None
        check(saved,requirements,document.body,posting.body)
        if saved.suggestions:
            revised = await resume.apply(document.id,AtsApply(job_id=posting.id,suggestion_ids=[item.id for item in saved.suggestions]))
            original = await sources.read(document.id)
            assert revised.id != document.id and original['body'] == document.body
            assert revised.extracted['origin']['parent_id'] == document.id
        print('Live scan and tailored review published; every saved quote, number and suggestion passed the local checks.')
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
    parser = argparse.ArgumentParser(description=__doc__,formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--live',action='store_true',help='allow paid Gemini calls and a disposable database schema')
    args = parser.parse_args()
    if hasattr(sys.stdout,'reconfigure'):sys.stdout.reconfigure(encoding='utf-8')
    if args.live:
        asyncio.run(main())
    else:
        plan()
