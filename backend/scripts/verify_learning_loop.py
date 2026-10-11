"""Read-only acceptance checks for an already completed live learning loop.

PYTHONPATH=backend python backend/scripts/verify_learning_loop.py PARENT_ID RETEST_ID
This does not generate content, finish sessions or modify candidate data.
"""
import argparse
import asyncio
import json
from app.v2 import db, rubrics
from app.v2.integrity import verify
from app.v2.models import ClaimDraft


async def check(parent_id, child_id):
    try:
        parent=await db.one('SELECT * FROM sessions WHERE id=$1',parent_id)
        child=await db.one('SELECT * FROM sessions WHERE id=$1',child_id)
        assert parent and child, 'Both sessions must exist'
        assert parent['status']==child['status']=='graded'
        assert parent['user_id']==child['user_id'] and child['parent_session_id']==parent_id
        assert child['kind']=='retest' and child['track_id']!=parent['track_id']
        scenario=await db.one('SELECT * FROM scenarios WHERE id=$1',child['scenario_id'])
        original=await db.one('SELECT * FROM scenarios WHERE id=$1',parent['scenario_id'])
        assert scenario['variant_of']==original['id']
        assert scenario['spec']['prompt']!=original['spec']['prompt']
        assert scenario['validity']=='passed' and scenario['validity_report']['kind']=='second_model_review'
        queue=await db.one('SELECT * FROM retest_queue WHERE track_id=$1',child['track_id'])
        assert queue['status']=='taken' and queue['session_id']==parent_id
        lesson=await db.one('SELECT * FROM lessons WHERE claim_id=$1',queue['claim_id'])
        gap=await db.one('SELECT * FROM claims WHERE id=$1',queue['claim_id'])
        assert lesson and gap['check_status']=='verified' and gap['polarity']=='gap'
        assert lesson['skill_id']==gap['skill_id']
        check_job=await db.one('SELECT * FROM generation_jobs WHERE id=$1',lesson['check_job_id'])
        assert check_job['parent_job_id']==lesson['job_id'] and check_job['status']=='succeeded'
        assert check_job['response']['supported'] is True
        checked=0
        for sid in (parent_id,child_id):
            report=await db.one('SELECT * FROM session_reports WHERE session_id=$1',sid)
            assert not report['stats']['partial'] and report['report']['rubric_version']==rubrics.VERSION
            events=[dict(e) for e in await db.fetch('SELECT * FROM session_events WHERE session_id=$1 ORDER BY seq',sid)]
            runs=await db.fetch('SELECT DISTINCT ON(evaluator) * FROM evaluator_runs WHERE session_id=$1 ORDER BY evaluator,attempt DESC',sid)
            assert len(runs)==4 and all(r['status']=='done' for r in runs)
            for run in runs:
                for claim in await db.fetch("SELECT * FROM claims WHERE run_id=$1 AND check_status='verified'",run['id']):
                    draft=next(c for c in run['output']['claims'] if c['text']==claim['text'])
                    assert verify(ClaimDraft(**draft),events,sid)[0]=='verified'
                    checked+=1
            rows=await db.fetch('SELECT skill_id,count(*) AS n FROM skill_assessments WHERE session_id=$1 GROUP BY skill_id',sid)
            assert rows and all(r['n']==1 for r in rows), 'Exactly one assessment per observed skill'
            for score in report['report']['scores']:
                assert score['claim_ids']
                supported=await db.fetch("SELECT id FROM claims WHERE id=ANY($1::text[]) AND session_id=$2 AND skill_id=$3 AND check_status='verified'",score['claim_ids'],sid,score['skill_id'])
                assert len(supported)==len(set(score['claim_ids']))
            assert not await db.one("SELECT id FROM generation_jobs WHERE subject_id=$1 AND status='running'",sid)
            assert not await db.one("SELECT id FROM evaluator_runs WHERE session_id=$1 AND status='running'",sid)
        latest=await db.one('SELECT report FROM session_reports WHERE session_id=$1',child_id)
        focus=next(s for s in latest['report']['scores'] if s['skill_id']==gap['skill_id'])
        assert focus['previous_session_id']==parent_id and focus['previous_evidence_seq']
        print(json.dumps({'same_skill_retest':'passed','changed_scenario':'passed','reviewed_lesson':'passed',
            'candidate_claim_references_checked':checked,'one_assessment_per_skill':'passed','comparison_evidence':'passed','stranded_jobs':0},indent=2))
    finally:
        if db._pool:await db._pool.close()


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('parent_id');parser.add_argument('retest_id')
    args=parser.parse_args()
    asyncio.run(check(args.parent_id,args.retest_id))
