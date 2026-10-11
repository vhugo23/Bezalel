import pytest
from fastapi import HTTPException
from app.v2 import learning_variants as variants,pi_lab,rubrics
from app.v2.models import LessonDraft


def draft():
    return LessonDraft(title='Check the layer',explanation='Compare direct application requests with proxy responses before changing the route. '*2,
        practice='Inspect the error log and the listening service, then verify the scoped repair.',
        retest_prompt='Investigate a second simulated Pi deployment that returns a gateway error. Discover the new service endpoint and explain the evidence.',
        expectations=['Explain the proxy versus application distinction.'])


@pytest.mark.parametrize('old',[0,1])
def test_pi_retest_changes_executable_constraint_and_keeps_comparable_rubric(old):
    data=pi_lab.definition(old);original={'id':'old','engine_id':'linux_fault',**data}
    prepared=variants.prepare(original)
    result=variants.publication(original,prepared,draft(),'infra.reverse_proxy','review','Checked.')
    assert result['params']['variant']==1-old
    assert pi_lab.initial(old)['app_port']!=pi_lab.initial(result['params']['variant'])['app_port']
    assert result['validity']['kind']=='reference_run_and_model_review'
    assert 'five_reference_goals_pass' in result['validity']['checks']
    assert result['layer']==2 and not result['validity']['semantic_guarantee']
    assert rubrics.load(result['rubric'],'linux_fault').version==rubrics.load(original['rubric'],'linux_fault').version
    assert result['spec']['focus_skill']=='infra.reverse_proxy'
    assert original['params']['variant']==old


def test_conceptual_retest_drops_old_requirements_and_preserves_review_semantics():
    original={'engine_id':'conceptual','spec':{'prompt':'original','requirements':{'old':True},'steps':['Clarify','Draw','Defend']},'rubric':{}}
    prepared=variants.prepare(original)
    result=variants.publication(original,prepared,draft(),'sw.system_design','review','Checked.')
    assert 'requirements' not in result['spec'] and 'requirements' in original['spec']
    assert result['engine_id']=='conceptual' and result['validity']['kind']=='second_model_review'
    assert result['layer']==3


def test_recorded_review_is_not_labelled_as_a_live_provider_review():
    original={'engine_id':'linux_fault',**pi_lab.definition()}
    result=variants.publication(original,variants.prepare(original),draft(),'infra.reverse_proxy','review','Synthetic fixture',True)
    assert result['validity']['recorded_review'] and 'recorded' in result['validity']['label']


def test_other_engines_cannot_fall_through_to_rate_limiter_retests():
    with pytest.raises(HTTPException) as error:variants.prepare({'engine_id':'behavioral','spec':{},'rubric':{}})
    assert error.value.status_code==409
    with pytest.raises(ValueError):variants.prepare({'engine_id':'linux_fault','params':{'variant':23}})
