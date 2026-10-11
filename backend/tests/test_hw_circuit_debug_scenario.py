"""contracts/examples/hw_circuit_debug.two_step.v2.json (a project interview, then an LED debug) and its answer key.
The key point: the planted fault must not reach the interviewer model, the evaluator model or the browser. The leak
tests call the real v2 prompt-building code (service.respond, assessment.evaluate) with the database functions
replaced by stubs, so they show what that code does with a scenario row that holds the answer key in `params`."""
import asyncio
import json
import re
from datetime import datetime, timezone
from pathlib import Path

import pytest

from app.modules.prepcrew import hardware_interview as hw
from app.v2 import assessment, engine, rubrics, service
from app.v2.models import Event, RubricEvaluation

ROOT = Path(__file__).resolve().parents[2]
SCENARIO = ROOT / "contracts/examples/hw_circuit_debug.two_step.v2.json"
KEY = ROOT / "contracts/examples/hw_circuit_debug.answer_key.json"
OLDER_LED = ROOT / "contracts/examples/led_reversed.v2.json"
SEED_SQL = ROOT / "backend/migrations/sql/001_v23.sql"


def load(path):
    return json.loads(path.read_text(encoding="utf-8"))


def at(doc, pointer):
    for part in pointer.split("/")[1:]:
        part = part.replace("~1", "/").replace("~0", "~")
        doc = doc[int(part)] if isinstance(doc, list) else doc[part]
    return doc


# Words and values that give the planted fault away. Taken from the key's own contents, lower case.
FAULTED = load(KEY)["circuit"]["expected_voltages"]["faulted"]
SECRETS = ["reversed", "led_reversed", "orientation", "faulted", "expected_voltages", "passes no current",
           json.dumps(FAULTED), json.dumps(FAULTED, separators=(",", ":"))]


class Stop(Exception):
    pass


def leaks(text):
    low = text.lower()
    return [s for s in SECRETS if s.lower() in low]


def interviewer_prompt(monkeypatch, row, step):
    """The prompt service.respond builds for a candidate turn on this step, for a scenario row like the database's."""
    definition = {**row, "steps": engine.parse_steps(row["spec"])}
    first = Event(session_id="s", seq=1, kind="turn", actor="candidate", step=step,
                  payload={"text": "I would check the supply voltage first."}, ts=datetime.now(timezone.utc))
    seen = {}

    async def events(sid, after=0):
        return [first]

    async def context(sid, conn=None):
        return definition

    async def none(*args, **kwargs):
        return None

    async def generate(kind, subject, prompt, schema, cached=None, **kwargs):
        seen["prompt"] = prompt
        raise Stop
    monkeypatch.setattr(service, "events", events)
    monkeypatch.setattr(service.engine, "context", context)
    monkeypatch.setattr(service.db, "one", none)
    monkeypatch.setattr(service, "generate", generate)
    with pytest.raises(Stop):
        asyncio.run(service.respond("s", first))
    return seen["prompt"]


def evaluator_prompt(monkeypatch, row, step):
    """The prompt assessment.evaluate builds for the first evaluator, given the row's spec as run() passes it."""
    policy = rubrics.load(row["rubric"], row["engine_id"])
    name = next(iter(policy.evaluators))
    events = [{"seq": 2, "kind": "turn", "actor": "candidate", "step": step, "ts": "2026-10-11T00:00:00+00:00",
               "payload": {"text": "I would check the supply voltage first."}}]
    seen = {}

    async def none(*args, **kwargs):
        return None

    async def generate(kind, subject, prompt, schema, cached=None, **kwargs):
        seen["prompt"] = prompt
        raise Stop  # evaluate catches it and records a failed run through the stubbed db.execute
    monkeypatch.setattr(assessment.db, "one", none)
    monkeypatch.setattr(assessment.db, "execute", none)
    monkeypatch.setattr(assessment, "generate", generate)
    asyncio.run(assessment.evaluate("s", name, events, row["spec"], policy))
    return seen["prompt"]


def scenario_row(spec, params):
    """What `SELECT sc.*, ...` in engine.context returns: every column of the scenarios row."""
    return {"id": "sc1", "track_id": "t1", "engine_id": "dc_solver", "engine_version": "1", "spec": spec,
            "params": params, "rubric": spec.get("rubric", {}), "validity": "passed",
            "validity_report": {"kind": "authored_structure_check", "semantic_guarantee": False},
            "domain_id": "hw", "engine_state": {}, "step": 0, "status": "live"}


# ---- the files ----

def test_both_files_are_valid_json_and_marked_synthetic():
    spec, key = load(SCENARIO), load(KEY)
    assert spec["synthetic"] is True and key["synthetic"] is True
    assert spec["provenance"]["reviewed_by_a_person"] is False
    assert spec["rubric"]["status"] == "draft" and spec["rubric"]["reviewed_by"] is None
    pi = spec["project_interview"]
    assert pi["synthetic"] is True and "SYNTHETIC EXAMPLE" in pi["label"]
    assert pi["posting"].startswith("SYNTHETIC EXAMPLE") and pi["resume"].startswith("SYNTHETIC EXAMPLE")
    for text in (pi["posting"], pi["resume"]):
        assert "%" not in text  # no result is quoted as a figure
        # the earlier sample resume mentioned "swapped LED polarity", which is the planted fault in a different coat
        assert not [w for w in ("reversed", "polarity", "backward", "flipped", "swapped") if w in text.lower()]


def test_the_two_steps_pass_the_v2_step_validator_and_step_zero_is_the_project_interview():
    spec = load(SCENARIO)
    steps = engine.parse_steps(spec)
    assert [s.idx for s in steps] == [0, 1] and [s.surface for s in steps] == ["voice", "voice"]
    assert steps[0].config["driver"] == "hardware_interview" and steps[0].config["strict"] is False
    assert steps[0].config["strict_why"] and "calibration" in steps[0].config["strict_why"]
    assert steps[1].title == "LED does not light" and len(steps[1].hints) == 2
    assert all(s.success["min_turns"] == 2 for s in steps)


def test_the_rubric_loads_for_the_dc_solver_engine_and_cites_only_the_led_step():
    spec = load(SCENARIO)
    policy = rubrics.load(spec["rubric"], "dc_solver")
    assert list(policy.evaluators) == ["Debug process"]
    assert rubrics.load(rubrics.dump(policy), "dc_solver").version == policy.version
    rubrics.validate_evaluation("Debug process", RubricEvaluation(
        criteria=[{"id": c.id} for c in policy.evaluators["Debug process"]]), policy)
    assert all(list(c.steps) == [1] and list(c.rules) == ["quoted_turn"] for c in policy.evaluators["Debug process"])
    seeded = set(re.findall(r"\('((?:infra|hw|sw|comm)\.[a-z0-9_]+)','\w+','", SEED_SQL.read_text(encoding="utf-8")))
    assert {c.skill_id for c in policy.evaluators["Debug process"]} <= seeded


def test_the_assumption_pointers_in_the_key_resolve_and_the_led_drop_is_marked():
    key = load(KEY)
    marked = {a["id"]: a for a in key["assumptions"]}
    assert [at(key, p) for p in marked["led_forward_drop"]["paths"]] == [2.0, 2.0]
    assert at(key, marked["reversed_led_passes_no_current"]["paths"][0]) == 5.0
    assert all(a["statement"] and a["paths"] for a in key["assumptions"])


def test_the_circuit_and_hints_match_the_earlier_led_scenario_file():
    spec, key, led = load(SCENARIO), load(KEY), load(ROOT / "contracts/examples/led_reversed.json")
    for field in ("ground_net", "parts", "nets", "expected_voltages"):
        assert key["circuit"][field] == led[field], field
    assert key["circuit"]["fault"] == {"type": led["fault"]["type"], "part": led["fault"]["part"]}
    assert spec["steps"][1]["hints"] == led["fault"]["hint_ladder"] and spec["steps"][1]["task"] == led["prompt"]


# ---- the project interview text runs through the lane 1 module ----

def test_the_synthetic_posting_and_resume_run_through_hardware_interview_start_on_the_fake_provider():
    spec = load(SCENARIO)
    pi, config = spec["project_interview"], spec["steps"][0]["config"]
    assert 0 < len(pi["posting"]) <= 20000 and 0 < len(pi["resume"]) <= 20000  # the legacy plan route's limit
    started = asyncio.run(hw.start(pi["posting"], pi["resume"], strict=config["strict"]))
    assert started["opening"] and started["state"]["strict"] is False and started["state"]["phase"] == "interview"
    turn = asyncio.run(hw.answer(started["state"], "I traced the brownout to the 5V rail with a scope."))
    assert turn["reply"] and turn["meter"] is None  # the fake provider has no meter
    json.dumps(started), json.dumps(turn)


# ---- the planted fault stays out of every model prompt and the browser ----

def test_the_scenario_file_does_not_contain_the_answer_key():
    assert leaks(SCENARIO.read_text(encoding="utf-8")) == []
    assert "reversed" not in json.dumps(load(SCENARIO)).lower()


@pytest.mark.parametrize("step", [0, 1])
def test_the_interviewer_prompt_has_the_scenario_but_not_the_fault_or_the_key(monkeypatch, step):
    spec = load(SCENARIO)
    prompt = interviewer_prompt(monkeypatch, scenario_row(spec, load(KEY)), step)
    assert "SYNTHETIC EXAMPLE" in prompt and spec["steps"][1]["task"] in prompt  # the real prompt does carry the spec
    assert leaks(prompt) == []


@pytest.mark.parametrize("step", [0, 1])
def test_the_evaluator_prompt_has_the_rubric_and_scenario_but_not_the_fault_or_the_key(monkeypatch, step):
    spec = load(SCENARIO)
    prompt = evaluator_prompt(monkeypatch, scenario_row(spec, load(KEY)), step)
    assert "Verifies the supply rail" in prompt and "SYNTHETIC EXAMPLE" in prompt
    assert leaks(prompt) == []


def test_what_the_browser_gets_has_no_fault():
    spec = load(SCENARIO)
    steps = [s.model_dump() for s in engine.parse_steps(spec)]  # Session.steps, returned by GET /api/v2/sessions/{id}
    assert leaks(json.dumps(steps)) == [] and leaks(spec["prompt"]) == []  # and Session.opening is spec["prompt"]
    assert "spec" not in service.Session.model_fields and "params" not in service.Session.model_fields


def test_the_evaluator_query_does_not_select_params():
    # Not provable without a database, so pinned by the text of the query in assessment.py: the evaluator is given
    # `SELECT spec,engine_id,rubric`. If this fails, look at what the new query hands to the evaluator prompt.
    import inspect
    assert "SELECT spec,engine_id,rubric FROM scenarios" in inspect.getsource(assessment)


def test_the_leak_check_would_notice_a_leak(monkeypatch):
    # control: the same harness on a spec that embeds the circuit, as the earlier single file layout does
    key = load(KEY)
    leaky = {**load(SCENARIO), "circuit": key["circuit"]}
    assert leaks(interviewer_prompt(monkeypatch, scenario_row(leaky, key), 1))
    assert leaks(evaluator_prompt(monkeypatch, scenario_row(leaky, key), 1))


def test_the_earlier_led_reversed_v2_file_leaks_the_fault_if_it_is_loaded_whole(monkeypatch):
    # Evidence for the review of PR #11's led_reversed.v2.json. Delete this test when that file is fixed or removed.
    spec = load(OLDER_LED)
    assert "whole file is meant to be stored as scenarios.spec" in spec["provenance"]["format"]
    found = leaks(interviewer_prompt(monkeypatch, scenario_row(spec, {}), 0))
    assert {"reversed", "led_reversed", "faulted", "orientation"} <= set(found)
    assert {"reversed", "faulted", "orientation"} <= set(leaks(evaluator_prompt(monkeypatch, scenario_row(spec, {}), 0)))
