import asyncio
from dataclasses import asdict
from unittest.mock import AsyncMock
import pytest
from fastapi import HTTPException
from app.v2 import engine, rubrics
from app.v2.models import SessionStep, RubricEvaluation


def two_steps():
    return [SessionStep(idx=0,title='Choose a story',surface='star',task='Describe a real project.',success={'min_turns':1}),
            SessionStep(idx=1,title='Explain your action',surface='voice',task='What did you do?',success={'min_turns':1})]


def test_progression_uses_configured_objectives_and_final_index():
    steps=two_steps()
    assert engine.action_allowed('finish',0,10,True,'done',steps)=='continue'
    assert engine.action_allowed('advance',0,0,False,'done',steps)=='continue'
    assert engine.action_allowed('advance',0,1,False,'done',steps)=='advance'
    assert engine.action_allowed('advance',1,1,False,'done',steps)=='continue'
    assert engine.action_allowed('finish',1,1,False,'done',steps)=='finish'
    assert engine.action_allowed('look',0,1,False,'look at my board',steps)=='continue'


def test_whiteboard_can_be_first_or_last_step():
    steps=[SessionStep(idx=0,title='Draw it',surface='whiteboard',task='Draw while explaining.',success={'board_review':True})]
    assert engine.action_allowed('finish',0,1,False,'done',steps)=='continue'
    assert engine.action_allowed('look',0,1,False,'take a look',steps)=='look'
    assert engine.action_allowed('finish',0,1,True,'continue',steps)=='finish'


@pytest.mark.parametrize('raw',[[],[{'idx':1,'title':'Skipped','task':'Explain.'}],
    [{'idx':0,'title':'Invalid objective','task':'Explain.','success':{'min_turns':-1}}],
    [{'idx':0,'title':'Invalid pause','task':'Explain.','config':{'look':'always'}}]])
def test_invalid_step_configurations_are_not_runnable(raw):
    with pytest.raises(ValueError):engine.parse_steps({'steps':raw})


def test_paused_session_cannot_accept_candidate_work():
    with pytest.raises(HTTPException) as error:
        asyncio.run(engine.ensure_accepting({'engine_state':{'paused':True}},'s'))
    assert error.value.status_code==409


def test_rubrics_are_selected_per_scenario_without_global_mutation():
    criterion=rubrics.Criterion('ownership','comm.followups','Describe your own action.',('quoted_turn',),steps=(1,))
    payload={'version':'story-practice-v1','evaluators':{'Ownership':[asdict(criterion)]}}
    selected=rubrics.load(payload,'behavioral')
    assert rubrics.load(rubrics.dump(selected),'behavioral').version==selected.version
    compact={**payload,'evaluators':{'Ownership':[{k:v for k,v in asdict(criterion).items() if k!='scored'}]}}
    assert rubrics.load(compact,'behavioral').version==selected.version
    assert list(selected.evaluators)==['Ownership']
    assert list(rubrics.DEFAULT.evaluators)==['Requirements','Whiteboard','Trade-offs','Communication']
    rubrics.validate_evaluation('Ownership',RubricEvaluation(criteria=[{'id':'ownership'}]),selected)
    changed={**payload,'evaluators':{'Ownership':[{**asdict(criterion),'description':'A changed criterion.'}]}}
    assert rubrics.load(changed,'behavioral').version!=selected.version
    with pytest.raises(ValueError):rubrics.load({},'behavioral')
