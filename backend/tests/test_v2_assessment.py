import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock
import pytest
from fastapi import HTTPException
from app.v2 import assessment, rubrics, learning
from app.v2.models import RubricEvaluation, EvidenceReview, LessonDraft


def evaluation(skill='sw.system_design',seq=1,polarity='gap',score=1):
    return RubricEvaluation(criteria=[{'id':'failure_policy','score':score,'claims':[{
        'text':'Equated failing closed with availability.','polarity':polarity,'evidence_seq':[seq],
        'quotes':['Failing closed guarantees availability.'],'skill_id':skill}]}])


EVENTS=[{'session_id':'s','seq':1,'actor':'candidate','kind':'turn','step':2,
         'payload':{'text':'Failing closed guarantees availability.'}}]


def test_unknown_skill_is_rejected_not_remapped():
    output=evaluation('invented.skill')
    checked=assessment.checked_claims('Trade-offs',output,EVENTS,'s')
    assert checked[0]['status']=='rejected'
    assert output.criteria[0].claims[0].skill_id=='invented.skill'
    assert assessment.eligible_scores(output,checked)==[]


@pytest.mark.parametrize('criteria',[[],[{'id':'not-a-criterion'}],[{'id':'failure_policy'},{'id':'failure_policy'}]])
def test_missing_unknown_or_duplicate_criteria_fail_closed(criteria):
    with pytest.raises(ValueError):rubrics.validate_evaluation('Trade-offs',RubricEvaluation(criteria=criteria))


def test_absence_and_dana_work_cannot_support_gap():
    for events in ([],[{**EVENTS[0],'actor':'interviewer'}]):
        checked=assessment.checked_claims('Trade-offs',evaluation(),events,'s')
        assert checked[0]['status']=='rejected'
        assert assessment.eligible_scores(evaluation(),checked)==[]


def test_second_review_must_resolve_every_candidate_claim_once():
    for decisions in ([],[{'index':5,'supported':True,'reason':'unsupported index'}],
                      [{'index':0,'supported':True,'reason':'first'},{'index':0,'supported':True,'reason':'duplicate'}]):
        checked=assessment.checked_claims('Trade-offs',evaluation(),EVENTS,'s')
        with pytest.raises(ValueError):assessment.apply_semantic_review(checked,EvidenceReview(decisions=decisions))


def test_semantic_rejection_blocks_score_even_when_quote_exists():
    checked=assessment.checked_claims('Trade-offs',evaluation(),EVENTS,'s')
    assert checked[0]['status']=='verified'
    assessment.apply_semantic_review(checked,EvidenceReview(decisions=[{'index':0,'supported':False,'reason':'The interpretation overstates the evidence.'}]))
    assert assessment.eligible_scores(evaluation(),checked)==[]


def test_criterion_scores_keep_their_skill_and_citations():
    output=evaluation();checked=assessment.checked_claims('Trade-offs',output,EVENTS,'s');checked[0]['id']='claim'
    assert assessment.eligible_scores(output,checked)==[{'criterion_id':'failure_policy','skill_id':'sw.system_design','score':25,'claim_ids':['claim']}]
    communication=RubricEvaluation(criteria=[{'id':'narration','score':None,'claims':[]},{'id':'followup','score':3,'claims':[{'text':'Answered directly.','polarity':'strength','skill_id':'comm.followups','evidence_seq':[1],'quotes':['Failing closed guarantees availability.']}]}])
    dialogue=[{'session_id':'s','seq':-1,'kind':'turn','actor':'interviewer','step':0,'payload':{'text':'Design an API.'}},
              {'session_id':'s','seq':0,'kind':'turn','actor':'interviewer','step':2,'payload':{'text':'What happens under failure?'}},*EVENTS]
    checked=assessment.checked_claims('Communication',communication,dialogue,'s');checked[0]['id']='communication'
    assert assessment.eligible_scores(communication,checked)[0]['skill_id']=='comm.followups'


def test_technical_error_cannot_contaminate_requirements_or_unobserved_followup():
    scope=evaluation();scope.criteria[0].id='scope'
    assert assessment.checked_claims('Requirements',scope,EVENTS,'s')[0]['status']=='rejected'
    followup=RubricEvaluation(criteria=[{'id':'narration'},{'id':'followup','score':1,'claims':[{
        'text':'Availability misconception.','polarity':'gap','skill_id':'comm.followups','evidence_seq':[1],'quotes':['Failing closed guarantees availability.']}]}])
    checked=assessment.checked_claims('Communication',followup,EVENTS,'s')
    assert checked[0]['status']=='rejected'
    assert assessment.eligible_scores(followup,checked)==[]


def test_observable_activity_cannot_create_an_ability_score():
    output=RubricEvaluation(criteria=[{'id':'drawing','score':4,'claims':[]},{'id':'design_reasoning'}])
    with pytest.raises(ValueError,match='activity'):rubrics.validate_evaluation('Whiteboard',output)
    checked=assessment.checked_claims('Trade-offs',evaluation(polarity='neutral'),EVENTS,'s')
    assert checked[0]['status']=='rejected'


def test_lesson_requires_complete_verified_gap(monkeypatch):
    from app.v2 import service
    monkeypatch.setattr(learning,'require_session',AsyncMock(return_value={'id':'s'}))
    monkeypatch.setattr(service,'report',AsyncMock(return_value=SimpleNamespace(status='graded',partial=False,next_gap=None)))
    with pytest.raises(HTTPException) as error:asyncio.run(learning.read('s'))
    assert error.value.status_code==409


def test_unchanged_retest_is_not_publishable():
    draft=LessonDraft(title='Failure policies',explanation='Explain an availability trade-off. '*4,
        practice='Discuss the outage consequences.',retest_prompt='Design a rate limiter with strict per-user limits.',expectations=['State the failure policy.'])
    with pytest.raises(ValueError,match='change'):learning.validate_variant(draft,'  DESIGN a rate limiter with strict per-user limits. ')


def test_lesson_read_preserves_gap_citations():
    gap=SimpleNamespace(id='c',skill_id='sw.system_design',text='Explicit misconception.',evidence_seq=[17])
    lesson=learning.lesson_result(gap,None)
    assert lesson.claim_id=='c' and lesson.evidence_seq==[17]
    assert not lesson.retest_ready and not lesson.body


def test_retest_resolves_only_the_original_gap_criterion():
    scores=[{'criterion_id':'scope','score':100,'claim_ids':['scope']},
            {'criterion_id':'failure_policy','score':50,'claim_ids':['partial']}]
    assert assessment.resolved_criterion(scores,'failure_policy') is None
    assert assessment.resolved_criterion(scores,'unobserved') is None
    scores[1]['score']=75
    assert assessment.resolved_criterion(scores,'failure_policy')['claim_ids']==['partial']
