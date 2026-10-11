"""contracts/examples/led_reversed.v2.json is the reversed LED scenario in the v2 scenario format. These tests call the
v2 loaders that need no database (engine.parse_steps, rubrics.load), check the skill ids against the seeded skills,
and check the file against the original led_reversed.json and debug_process_rubric.json so nothing drifted or was invented."""
import json
import re
from pathlib import Path

import pytest

from app.v2 import engine, rubrics
from app.v2.models import RubricEvaluation

ROOT = Path(__file__).resolve().parents[2]
V2 = ROOT / "contracts/examples/led_reversed.v2.json"
SOURCE = ROOT / "contracts/examples/led_reversed.json"
SOURCE_RUBRIC = ROOT / "contracts/examples/debug_process_rubric.json"
SEED_SQL = ROOT / "backend/migrations/sql/001_v23.sql"


def load(path):
    return json.loads(path.read_text(encoding="utf-8"))


def at(doc, pointer):
    """Follow an RFC 6901 JSON pointer such as /circuit/parts/2/value."""
    for part in pointer.split("/")[1:]:
        part = part.replace("~1", "/").replace("~0", "~")
        doc = doc[int(part)] if isinstance(doc, list) else doc[part]
    return doc


def test_the_file_is_valid_json_and_marked_synthetic_and_unreviewed():
    spec = load(V2)
    assert spec["synthetic"] is True
    assert spec["provenance"]["reviewed_by_a_person"] is False
    assert spec["rubric"]["status"] == "draft" and spec["rubric"]["reviewed_by"] is None


def test_the_steps_pass_the_v2_step_validator():
    spec = load(V2)
    steps = engine.parse_steps(spec)
    assert [s.idx for s in steps] == list(range(len(steps))) == [0]
    assert steps[0].surface == "voice"  # nothing in the app draws a schematic, so this step does not claim one
    assert len(steps[0].hints) <= 5 and steps[0].success["min_turns"] == 2


def test_the_rubric_loads_for_the_dc_solver_engine_and_round_trips():
    spec = load(V2)
    policy = rubrics.load(spec["rubric"], "dc_solver")
    assert list(policy.evaluators) == ["Debug process"]
    assert rubrics.load(rubrics.dump(policy), "dc_solver").version == policy.version
    assert policy.version.startswith("debug-process-draft-v0:")
    unscored = RubricEvaluation(criteria=[{"id": c.id} for c in policy.evaluators["Debug process"]])
    rubrics.validate_evaluation("Debug process", unscored, policy)
    for criterion in policy.evaluators["Debug process"]:
        assert list(criterion.steps) == [0]  # evidence comes from the one step that exists
        assert list(criterion.rules) == ["quoted_turn"]  # the only evidence a voice step has


def test_every_skill_id_is_a_seeded_v2_skill():
    seeded = set(re.findall(r"\('((?:infra|hw|sw|comm)\.[a-z0-9_]+)','\w+','", SEED_SQL.read_text(encoding="utf-8")))
    assert {"hw.circuit_probing", "hw.power_rails"} <= seeded  # the regex found the seed list
    used = {c["skill_id"] for group in load(V2)["rubric"]["evaluators"].values() for c in group}
    assert used <= seeded


def test_the_prompt_hints_and_circuit_match_the_original_scenario():
    spec, source = load(V2), load(SOURCE)
    assert spec["prompt"] == source["prompt"]
    assert spec["steps"][0]["title"] == source["title"]
    assert spec["steps"][0]["hints"] == source["fault"]["hint_ladder"]
    circuit = spec["circuit"]
    assert circuit["source_scenario_id"] == source["scenario_id"] and circuit["kind"] == source["kind"]
    for key in ("ground_net", "parts", "nets", "expected_voltages"):
        assert circuit[key] == source[key], key
    assert circuit["fault"] == {"type": source["fault"]["type"], "part": source["fault"]["part"]}


def test_the_criteria_keep_the_original_ids_and_wording():
    source = load(SOURCE_RUBRIC)["criteria"]
    mine = load(V2)["rubric"]["evaluators"]["Debug process"]
    assert [(c["id"], c["description"]) for c in mine] == [(c["id"], c["description"]) for c in source]


def test_every_assumption_points_at_a_real_value_and_the_led_drop_is_one():
    spec, source = load(V2), load(SOURCE)
    marked = {a["id"]: a for a in spec["assumptions"]}
    drop = marked["led_forward_drop"]
    assert source["parts"][2]["id"] == "D1" and source["parts"][2]["value"] == 2.0
    assert [at(spec, p) for p in drop["paths"]] == [2.0, 2.0]  # D1's drop and the healthy reading at n2
    assert at(spec, marked["reversed_led_passes_no_current"]["paths"][0]) == 5.0
    for a in spec["assumptions"]:
        assert a["statement"] and a["paths"]
        for p in a["paths"]:
            at(spec, p)  # raises if the pointer no longer resolves


def test_the_step_validator_would_catch_a_broken_step():
    spec = load(V2)
    spec["steps"][0]["config"] = {"look": "always"}  # a board look mode the engine does not know
    with pytest.raises(ValueError):
        engine.parse_steps(spec)
    spec = load(V2)
    spec["steps"][0]["idx"] = 1  # steps must start at 0 and be contiguous
    with pytest.raises(ValueError):
        engine.parse_steps(spec)
