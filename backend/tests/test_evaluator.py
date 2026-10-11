"""The evaluator (contracts/api.md, evaluator pipeline). The model is replaced by scripted replies."""
import asyncio
import json

import pytest
from fastapi.testclient import TestClient

from app import config
from app.core import ai, store
from app.main import app
from app.modules.prepcrew import evaluators

client = TestClient(app)
ANSWER = {"answer_id": "a1", "text": "I'd measure the supply first to make sure we have five volts. Then I'd check ground."}
RUBRIC = {"rubric_id": "debug_v0", "title": "Debug process", "module": "debug", "status": "reviewed", "score_max": 2,
          "criteria": [
              {"id": "supply_first", "description": "Checks the supply first.", "skill_id": "circuits1.dc_measurement",
               "uses_probe_log": True, "anchors": {"0": "never", "2": "first"}},
              {"id": "hypothesis", "description": "States a hypothesis.", "skill_id": "circuits1.fault_isolation",
               "anchors": {"0": "none", "2": "clear"}}]}


def scripted(*replies):
    """generate_text stand-in returning these replies in order; records prompts."""
    calls = []

    async def fake(prompt, system=None, **kw):
        calls.append({"prompt": prompt, **kw})
        r = replies[min(len(calls) - 1, len(replies) - 1)]
        if isinstance(r, Exception):
            raise r
        return r if isinstance(r, str) else json.dumps(r)
    return fake, calls


GOOD = {"confidence": 0.8, "criteria": [
    {"id": "supply_first", "score": 2, "evidence_quote": "I'd measure the supply first", "rationale": "Supply first."},
    {"id": "hypothesis", "score": 0, "evidence_quote": "", "rationale": "No hypothesis."}]}


def run(coro):
    return asyncio.run(coro)


def test_good_reply_spans_computed_by_server_and_flags_low_skills(monkeypatch):
    fake, calls = scripted(GOOD)
    monkeypatch.setattr(ai, "generate_text", fake)
    out = run(evaluators.run_evaluator(RUBRIC, ANSWER, "", [{"seq": 0, "action": "probe_voltage", "node": "n1",
                                                             "value": 5.0, "unit": "V"}]))
    c0 = out["criteria"][0]
    assert ANSWER["text"][c0["evidence_span"][0]:c0["evidence_span"][1]] == c0["evidence_quote"]
    assert out["criteria"][1]["evidence_span"] == [0, 0]
    assert out["skill_flags"] == ["circuits1.fault_isolation"] and out["needs_review"] is False
    assert evaluators.check_evidence(out, ANSWER["text"], 2) == []
    assert "probe_voltage n1 -> 5.0 V" in calls[0]["prompt"]          # probe log shown for uses_probe_log
    assert "<answer>" in calls[0]["prompt"]


def test_invented_quote_retries_once_then_needs_review(monkeypatch):
    bad = {**GOOD, "criteria": [{**GOOD["criteria"][0], "evidence_quote": "I would check the fuse"}, GOOD["criteria"][1]]}
    fake, calls = scripted(bad, bad)
    monkeypatch.setattr(ai, "generate_text", fake)
    out = run(evaluators.run_evaluator(RUBRIC, ANSWER, "", []))
    assert len(calls) == 2 and "rejected" in calls[1]["prompt"]
    assert out["needs_review"] is True and out["failure_reason"] == "quote_mismatch"


def test_invented_quote_fixed_on_retry(monkeypatch):
    bad = {**GOOD, "criteria": [{**GOOD["criteria"][0], "evidence_quote": "I would check the fuse"}, GOOD["criteria"][1]]}
    fake, calls = scripted(bad, GOOD)
    monkeypatch.setattr(ai, "generate_text", fake)
    out = run(evaluators.run_evaluator(RUBRIC, ANSWER, "", []))
    assert len(calls) == 2 and out["needs_review"] is False


@pytest.mark.parametrize("draft", [
    {**GOOD, "criteria": GOOD["criteria"][:1]},                                         # missing a criterion
    {**GOOD, "criteria": GOOD["criteria"] + [{"id": "made_up", "score": 1, "evidence_quote": "", "rationale": ""}]},
    {**GOOD, "criteria": [{**GOOD["criteria"][0], "score": 3}, GOOD["criteria"][1]]},   # above score_max
    {**GOOD, "criteria": [GOOD["criteria"][0], {**GOOD["criteria"][1], "score": 1}]},   # score without evidence
])
def test_contract_violations_are_never_accepted(monkeypatch, draft):
    fake, _ = scripted(draft, draft)
    monkeypatch.setattr(ai, "generate_text", fake)
    assert run(evaluators.run_evaluator(RUBRIC, ANSWER, "", []))["needs_review"] is True


def test_bad_json_twice_raises_so_pipeline_reports_bad_json(monkeypatch):
    fake, _ = scripted("not json", "still not json")
    monkeypatch.setattr(ai, "generate_text", fake)
    with pytest.raises(ai.AIError):
        run(evaluators.run_evaluator(RUBRIC, ANSWER, "", []))


def test_busy_provider_is_retried_once(monkeypatch):
    fake, calls = scripted(ai.AIError("Gemini error 503: busy"), GOOD)
    monkeypatch.setattr(ai, "generate_text", fake)
    assert run(evaluators.run_evaluator(RUBRIC, ANSWER, "", []))["needs_review"] is False and len(calls) == 2


def test_evaluator_uses_its_own_model_setting(monkeypatch):
    fake, calls = scripted(GOOD)
    monkeypatch.setattr(ai, "generate_text", fake)
    monkeypatch.setattr(config, "EVALUATOR_MODEL", "strong-model")
    run(evaluators.run_evaluator(RUBRIC, ANSWER, "", []))
    assert calls[0].get("llm_model") == "strong-model"


def test_answers_are_graded_only_by_rubrics_for_their_phase(monkeypatch, tmp_path):
    (tmp_path / "debug.json").write_text(json.dumps(RUBRIC))
    (tmp_path / "interview.json").write_text(json.dumps({**RUBRIC, "rubric_id": "interview_v0", "module": "interview"}))
    monkeypatch.setattr(evaluators, "RUBRICS_DIR", tmp_path)
    graded = []

    async def fake_eval(rubric, answer, transcript, probe_log):
        graded.append((answer["answer_id"], rubric["rubric_id"]))
        return {"answer_id": answer["answer_id"], "rubric_id": rubric["rubric_id"], "criteria": [], "skill_flags": [],
                "confidence": 1, "needs_review": False}

    async def publish(e, d):
        pass

    monkeypatch.setattr(evaluators, "run_evaluator", fake_eval)
    answers = [{"answer_id": "proj", "text": "x", "turn": 1, "phase": "interview"},
               {"answer_id": "dbg", "text": "y", "turn": 2, "phase": "walkthrough"},
               {"answer_id": "old", "text": "z", "turn": 3}]           # stored before phases existed
    run(evaluators.grade_session("s", answers, "", [], publish))
    assert sorted(graded) == [("dbg", "debug_v0"), ("old", "interview_v0"), ("proj", "interview_v0")]


def test_end_to_end_needs_review_reported_and_kept_out_of_mastery(monkeypatch, tmp_path):
    (tmp_path / "r.json").write_text(json.dumps({**RUBRIC, "module": "interview"}))
    monkeypatch.setattr(evaluators, "RUBRICS_DIR", tmp_path)
    bad = {**GOOD, "criteria": [{**GOOD["criteria"][0], "evidence_quote": "never said this"}, GOOD["criteria"][1]]}
    fake, _ = scripted(bad)
    monkeypatch.setattr(ai, "generate_text", fake)
    plan = client.post("/api/plans", json={"job_posting": "p", "resume": "r", "user_id": "rev"}).json()
    sid = client.post("/api/sessions", json={"plan_id": plan["plan_id"], "user_id": "rev", "consent": True}).json()["session_id"]
    client.post(f"/api/sessions/{sid}/turns", json={"answer": ANSWER["text"]})
    monkeypatch.setattr(ai, "generate_text", fake)   # the turn may have used the stand-in too; reset its script
    client.post(f"/api/sessions/{sid}/end")
    with client.stream("GET", f"/api/sessions/{sid}/events") as r:
        lines = list(r.iter_lines())
    failed = [json.loads(lines[i + 1][6:]) for i, l in enumerate(lines) if l == "event: evaluator_failed"]
    assert failed and failed[0]["reason"] == "quote_mismatch"
    rep = client.get(f"/api/sessions/{sid}/report").json()
    assert rep["results"] and rep["results"][0]["needs_review"] is True
    assert client.get("/api/mastery", params={"user_id": "rev"}).json()["series"] == []


# ---- probe-step evidence for process criteria ----
PROBES = [{"seq": 0, "action": "probe_voltage", "node": "n1", "value": 5.0, "unit": "V"},
          {"seq": 1, "action": "probe_voltage", "node": "n2", "value": 5.0, "unit": "V"},
          {"seq": 2, "action": "swap_part", "node": "D1", "value": None, "unit": "none"}]


def test_process_criterion_can_cite_probe_steps_instead_of_a_quote(monkeypatch):
    draft = {"confidence": 0.8, "criteria": [
        {"id": "supply_first", "score": 2, "evidence_quote": "", "evidence_probe_seqs": [0], "rationale": "Probed n1 first."},
        {"id": "hypothesis", "score": 0, "evidence_quote": "", "rationale": "None."}]}
    fake, calls = scripted(draft)
    monkeypatch.setattr(ai, "generate_text", fake)
    out = run(evaluators.run_evaluator(RUBRIC, ANSWER, "", PROBES))
    c = out["criteria"][0]
    assert out["needs_review"] is False and c["evidence_probe_seqs"] == [0] and c["evidence_span"] == [0, 0]
    assert '"supply_first" [process' in calls[0]["prompt"] and '"hypothesis" [process' not in calls[0]["prompt"]


@pytest.mark.parametrize("bad_crit", [
    {"id": "supply_first", "score": 2, "evidence_quote": "", "evidence_probe_seqs": [7], "rationale": ""},  # no such step
    {"id": "hypothesis", "score": 2, "evidence_quote": "", "evidence_probe_seqs": [0], "rationale": ""},     # not a process criterion
])
def test_bad_probe_citations_are_rejected(monkeypatch, bad_crit):
    other = {"id": "hypothesis" if bad_crit["id"] == "supply_first" else "supply_first",
             "score": 0, "evidence_quote": "", "rationale": ""}
    draft = {"confidence": 0.5, "criteria": [bad_crit, other]}
    fake, _ = scripted(draft, draft)
    monkeypatch.setattr(ai, "generate_text", fake)
    assert run(evaluators.run_evaluator(RUBRIC, ANSWER, "", PROBES))["needs_review"] is True


def test_probe_evidence_reaches_the_report(monkeypatch, tmp_path):
    (tmp_path / "r.json").write_text(json.dumps({**RUBRIC, "module": "interview"}))
    monkeypatch.setattr(evaluators, "RUBRICS_DIR", tmp_path)
    draft = {"confidence": 0.8, "criteria": [
        {"id": "supply_first", "score": 2, "evidence_quote": "", "evidence_probe_seqs": [0], "rationale": "r"},
        {"id": "hypothesis", "score": 0, "evidence_quote": "", "rationale": "r"}]}

    async def fake_eval(rubric, answer, transcript, probe_log):
        out, problems = evaluators._assemble(rubric, answer, draft, PROBES)
        assert problems == []
        return out

    monkeypatch.setattr(evaluators, "run_evaluator", fake_eval)
    plan = client.post("/api/plans", json={"job_posting": "p", "resume": "r", "user_id": "pe"}).json()
    sid = client.post("/api/sessions", json={"plan_id": plan["plan_id"], "user_id": "pe", "consent": True}).json()["session_id"]
    client.post(f"/api/sessions/{sid}/turns", json={"answer": "hello"})
    client.post(f"/api/sessions/{sid}/end")
    with client.stream("GET", f"/api/sessions/{sid}/events") as r:
        list(r.iter_lines())
    crit = client.get(f"/api/sessions/{sid}/report").json()["results"][0]["criteria"][0]
    assert crit["evidence_probe_seqs"] == [0]


# ---- Tiger time-series is a no-op without a database ----
def test_timeseries_does_nothing_without_a_database():
    from app.modules.prepcrew import timeseries
    assert run(timeseries.write_probe({"event_id": "e", "seq": 0, "session_id": "s", "scenario_id": "x",
                                       "action": "power_cycle"})) is False
    assert run(timeseries.write_scores([{"user_id": "u"}])) == 0
    assert run(timeseries.mastery_series("u")) is None
    assert run(timeseries.delete_session("s")) == 0
