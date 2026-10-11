import asyncio
import hashlib
import json
from unittest.mock import AsyncMock

import pytest

from app.v2 import planning, service
from app.v2.models import Intake, PlanDraft, LessonReview

CATALOG = [
    {'id':'hw.circuit_debug','domain_id':'hw','title':'Circuit debugging','engine_id':'dc_solver'},
    {'id':'sw.sysdesign','domain_id':'sw','title':'System design','engine_id':'conceptual'},
]


def profile(role, question):
    return Intake(user_id='synthetic-planning',role=role,question=question,struggles=[],companies=[])


def test_recorded_plans_change_focus_and_workload_without_scores():
    hardware = PlanDraft.model_validate(planning.recorded_plan(profile('Embedded firmware','Debug a power circuit.'), CATALOG))
    software = PlanDraft.model_validate(planning.recorded_plan(profile('Software engineer','Design an API.'), CATALOG))
    planning.validate(hardware, CATALOG); planning.validate(software, CATALOG)
    assert hardware.primary_domain == 'hw' and software.primary_domain == 'sw'
    assert hardware.priorities[0].template_id == 'hw.circuit_debug'
    assert software.priorities[0].template_id == 'sw.sysdesign'
    assert hardware.system_design.requirements.identity != software.system_design.requirements.identity
    assert 'score' not in hardware.model_dump()


def test_missing_duplicate_and_unsupported_scenarios_fail_closed():
    valid = PlanDraft.model_validate(planning.recorded_plan(profile('Software engineer','Design an API.'), CATALOG))
    for priorities in (valid.priorities[:1],valid.priorities[:1]*2):
        with pytest.raises(ValueError):planning.validate(valid.model_copy(update={'priorities':priorities}),CATALOG)
    invalid = valid.model_copy(deep=True)
    invalid.system_design.prompt = 'Design an unrelated database storage engine using a B-tree.'
    with pytest.raises(ValueError):planning.validate(invalid,CATALOG)


def test_rejected_review_never_publishes_or_supersedes_a_plan(monkeypatch):
    body=profile('Software engineer','Design an API.')
    draft=PlanDraft.model_validate(planning.recorded_plan(body,CATALOG))
    monkeypatch.setattr(planning.sources,'selected',AsyncMock(return_value=[]))
    monkeypatch.setattr(planning,'catalog',AsyncMock(return_value=CATALOG))
    monkeypatch.setattr(planning.jobs,'stage',AsyncMock())
    monkeypatch.setattr(planning,'generate',AsyncMock(side_effect=[(draft,'generation','recorded'),(LessonReview(supported=False,reason='Incoherent scenario.'),'review','recorded')]))
    publish=AsyncMock();monkeypatch.setattr(service,'create_plan',publish)
    row={'id':'job','payload':{'intake':body.model_dump(),'sources':[],
        'catalog_hash':hashlib.sha256(json.dumps(CATALOG,sort_keys=True).encode()).hexdigest()}}
    with pytest.raises(ValueError,match='independent review'):asyncio.run(planning.create(row))
    publish.assert_not_called()
