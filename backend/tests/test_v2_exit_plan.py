import pytest
from pydantic import ValidationError
from app.v2 import exit_plan
from app.v2.models import QuitInput, QuitPlan

TITLES=['Clarify the load','Draw the design','Defend a trade-off']


def plan(reason,**facts):
    base=dict(track='Rate limiter',titles=TITLES,step=1,answered=[0,1],hints_used=1,hints_total=3)
    return exit_plan.build(reason,facts.pop('note',''),**{**base,**facts})


@pytest.mark.parametrize('reason',list(exit_plan.REASONS))
def test_every_reason_gives_a_plan_with_next_steps(reason):
    result=plan(reason)
    assert result.reason==reason and result.reason_label==exit_plan.REASONS[reason]
    assert result.headline and 2<=len(result.next_steps)<=4
    assert result.source=='authored'
    assert QuitPlan(**result.model_dump())==result  # survives the saved event payload


def test_reasons_match_the_request_model():
    for reason in exit_plan.REASONS:QuitInput(reason=reason)
    with pytest.raises(ValidationError):QuitInput(reason='bored')
    with pytest.raises(ValidationError):QuitInput(reason='lost',note='x'*301)


def test_summary_states_only_recorded_facts():
    summary=plan('lost').summary
    assert 'step 2 of 3, "Draw the design"' in summary
    assert 'answered on 2 of 3 steps' in summary and 'used 1 of 3 hints' in summary


def test_grading_is_offered_only_when_something_was_said():
    assert any(s.action=='grade' for s in plan('lost').next_steps)
    assert not any(s.action=='grade' for s in plan('lost',answered=[]).next_steps)
    assert not any(s.action=='grade' for s in plan('time',answered=[]).next_steps)


def test_hint_advice_follows_hint_use():
    titles=lambda p:[s.title for s in p.next_steps]
    assert 'Use the hints you skipped' in titles(plan('lost'))
    assert '2 hints' in next(s.detail for s in plan('lost').next_steps if s.title=='Use the hints you skipped')
    assert 'Go back to the basics behind this step' in titles(plan('lost',hints_used=3))
    assert not {'Use the hints you skipped','Go back to the basics behind this step'}&set(titles(plan('lost',hints_total=0,hints_used=0)))


def test_restart_names_the_steps_not_reached():
    restart=next(s for s in plan('time',step=0).next_steps if s.action=='restart')
    assert 'Draw the design, Defend a trade-off' in restart.detail
    last=next(s for s in plan('time',step=2).next_steps if s.action=='restart')
    assert 'not reached' not in last.detail


def test_quitting_after_the_last_step_does_not_index_past_the_end():
    result=plan('other',step=3,answered=[0,1,2])
    assert 'the last step' in result.summary and 'hint' not in result.summary


def decide(reason,**facts):
    return exit_plan.decide(reason,**{**dict(step=0,total=3,skipped=0,lab=False),**facts})


def test_a_first_unknown_step_is_skipped_not_ended():
    for reason in exit_plan.SKIP_TEXT:assert decide(reason)=='moved_on'


@pytest.mark.parametrize('reason',['time','technical','wrong_track'])
def test_reasons_about_the_session_always_end_it(reason):
    assert decide(reason)=='session'


def test_the_lesson_ends_when_skipping_cannot_help():
    assert decide('lost',step=2)=='last'      # nothing after the last step
    assert decide('lost',step=3)=='last'      # already past the end
    assert decide('lost',lab=True)=='lab'     # lab stages depend on each other
    assert decide('unclear',skipped=1)=='repeat'
    assert decide('lost',total=1)=='last'


def test_every_ending_explains_itself():
    assert set(exit_plan.WHY_ENDED)=={'session','last','lab','repeat'}
    assert 'second step you could not answer' in plan('lost',why='repeat').summary
    assert plan('time').summary.endswith('on this one.')


def test_note_is_trimmed_and_kept():
    assert plan('other',note='  mic kept cutting out ').note=='mic kept cutting out'
