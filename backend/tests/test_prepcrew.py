import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app import config
from app.main import app
from app.modules.prepcrew import evaluators, service, simulator

client = TestClient(app)
CONTRACTS = Path(__file__).resolve().parents[2] / "contracts" / "examples"


@pytest.fixture
def scenario(tmp_path, monkeypatch):
    """The contract's example scenario, loaded from a temp folder (the real data folder stays empty)."""
    (tmp_path / "led_reversed.json").write_text((CONTRACTS / "led_reversed.json").read_text(encoding="utf-8"))
    monkeypatch.setattr(simulator, "SCENARIOS_DIR", tmp_path)
    simulator.load_scenario.cache_clear()
    yield "led_reversed"
    simulator.load_scenario.cache_clear()


def new_session(user="u1"):
    plan = client.post("/api/plans", json={"job_posting": "hw intern", "resume": "r", "user_id": user}).json()
    r = client.post("/api/sessions", json={"plan_id": plan["plan_id"], "user_id": user, "consent": True})
    assert r.status_code == 200, r.text
    return r.json()


# ---- namespaces: the frontend owns everything outside /api and /ws ----
def test_backend_serves_no_pages_by_default():
    assert client.get("/").json()["docs"] == "/docs"
    for path in ["/plan", "/session/x", "/report/x", "/lesson/x", "/season", "/static/app.js"]:
        assert client.get(path).status_code == 404, path
    def walk(routes, prefix=""):  # newer FastAPI nests included routers; look inside them
        for r in routes:
            if hasattr(r, "original_router"):
                yield from walk(r.original_router.routes, prefix)
            elif getattr(r, "routes", None) is not None and not getattr(r, "path", None):
                yield from walk(r.routes, prefix)
            elif getattr(r, "path", None):
                yield prefix + r.path

    owned = sorted(set(walk(app.routes)))
    assert "/api/plans" in owned and "/ws/voice/{session_id}" in owned  # proves the walk sees module routes
    allowed = ("/api/", "/ws/", "/docs", "/redoc", "/openapi.json")
    stray = [p for p in owned if p != "/" and not p.startswith(allowed)]
    assert stray == [], f"routes outside /api and /ws would clash with the frontend: {stray}"


def test_cors_allows_vite_dev_server_only():
    ok = client.options("/api/plans", headers={"Origin": "http://localhost:5173", "Access-Control-Request-Method": "POST"})
    assert ok.headers.get("access-control-allow-origin") == "http://localhost:5173"
    bad = client.options("/api/plans", headers={"Origin": "http://evil.example", "Access-Control-Request-Method": "POST"})
    assert bad.headers.get("access-control-allow-origin") is None


# ---- sessions ----
def test_plan_and_session_shapes():
    plan = client.post("/api/plans", json={"job_posting": "p", "resume": "r"}).json()
    assert set(plan) == {"plan_id", "topics", "questions", "scenario_ids", "project", "requirements", "degraded", "memories"}
    s = client.post("/api/sessions", json={"plan_id": plan["plan_id"], "user_id": "u", "consent": True}).json()
    assert s["kind"] == "interview" and len(s["pair_code"]) == 6


def test_session_requires_consent_and_real_plan():
    plan = client.post("/api/plans", json={"job_posting": "p", "resume": "r"}).json()
    assert client.post("/api/sessions", json={"plan_id": plan["plan_id"], "user_id": "u", "consent": False}).status_code == 400
    assert client.post("/api/sessions", json={"plan_id": "nope", "user_id": "u", "consent": True}).status_code == 404


def test_unknown_session_is_404_everywhere():
    assert client.post("/api/sessions/nope/turns", json={"answer": "x"}).status_code == 404
    assert client.post("/api/sessions/nope/end").status_code == 404
    assert client.get("/api/sessions/nope/report").status_code == 404
    assert client.get("/api/sessions/nope/events").status_code == 404
    assert client.get("/api/metrics/nope").status_code == 404
    assert client.delete("/api/sessions/nope").status_code == 404


def test_turns_store_answers_and_measure_latency():
    s = new_session()
    t = client.post(f"/api/sessions/{s['session_id']}/turns", json={"answer": "I'd check the supply"}).json()
    assert t["answer_id"] and t["next_question"]
    m = client.get(f"/api/metrics/{s['session_id']}").json()
    assert m["turn_total_ms"] is not None and m["stt_ms"] is None  # measured vs not measured


# ---- probes ----
def test_probe_events_follow_contract(scenario):
    s = new_session()
    url = f"/api/sessions/{s['session_id']}/probe"
    e0 = client.post(url, json={"action": "probe_voltage", "node": "n2", "scenario_id": scenario}).json()
    e1 = client.post(url, json={"action": "swap_part", "node": "D1", "scenario_id": scenario}).json()
    assert (e0["seq"], e0["value"], e0["unit"]) == (0, 5.0, "V")  # faulted reading from the scenario
    assert (e1["seq"], e1["value"], e1["unit"]) == (1, None, "none")
    assert "fault" not in json.dumps([e0, e1])
    assert client.post(url, json={"action": "probe_voltage", "node": "zz", "scenario_id": scenario}).status_code == 400
    assert client.post(url, json={"action": "probe_voltage", "node": "n1", "scenario_id": "nope"}).status_code == 404
    assert client.post(url, json={"action": "probe_continuity", "node": "n1", "scenario_id": scenario}).status_code == 501


# ---- grading pipeline + SSE + mastery ----
RUBRIC = {"rubric_id": "test_rubric", "title": "t", "module": "debug", "status": "reviewed", "score_max": 2,
          "criteria": [{"id": "checked_supply_first", "description": "d", "skill_id": "circuits1.dc_measurement",
                        "anchors": {"0": "no", "2": "yes"}}]}


def test_end_grades_and_streams_events(tmp_path, monkeypatch):
    (tmp_path / "test_rubric.json").write_text(json.dumps(RUBRIC))
    monkeypatch.setattr(evaluators, "RUBRICS_DIR", tmp_path)

    async def fake_evaluator(rubric, answer, transcript, probe_log):
        quote = "supply first"
        start = transcript.index(quote)
        return {"answer_id": answer["answer_id"], "rubric_id": rubric["rubric_id"], "skill_flags": [],
                "confidence": 0.8, "criteria": [{"id": "checked_supply_first", "score": 2, "evidence_quote": quote,
                                                  "evidence_span": [start, start + len(quote)], "rationale": "ok"}]}

    monkeypatch.setattr(evaluators, "run_evaluator", fake_evaluator)
    s = new_session("grader")
    sid = s["session_id"]
    client.post(f"/api/sessions/{sid}/turns", json={"answer": "I'd measure the supply first."})

    end = client.post(f"/api/sessions/{sid}/end").json()
    assert end == {"status": "grading", "session_id": sid, "events_url": f"/api/sessions/{sid}/events"}

    with client.stream("GET", end["events_url"]) as r:
        assert r.headers["content-type"].startswith("text/event-stream")
        events = [line.split(": ", 1)[1] for line in r.iter_lines() if line.startswith("event: ")]
    assert events == ["evaluator_started", "evaluator_done", "grading_complete"]

    rep = client.get(f"/api/sessions/{sid}/report").json()
    assert rep["status"] == "graded" and rep["results"][0]["criteria"][0]["score"] == 2
    series = client.get("/api/mastery", params={"user_id": "grader"}).json()["series"]
    assert series[0]["skill_id"] == "circuits1.dc_measurement" and series[0]["points"][0]["mastery"] == 1.0
    assert client.get(f"/api/metrics/{sid}").json()["evaluator_fleet_ms"] is not None
    assert client.post(f"/api/sessions/{sid}/end").json()["status"] == "grading"  # idempotent, no regrade


def test_failed_evaluator_reports_reason(tmp_path, monkeypatch):
    (tmp_path / "test_rubric.json").write_text(json.dumps(RUBRIC))
    monkeypatch.setattr(evaluators, "RUBRICS_DIR", tmp_path)

    async def mismatch(*a):
        raise evaluators.EvidenceMismatch("quote not in transcript")

    monkeypatch.setattr(evaluators, "run_evaluator", mismatch)
    sid = new_session()["session_id"]
    client.post(f"/api/sessions/{sid}/turns", json={"answer": "x"})
    client.post(f"/api/sessions/{sid}/end")
    with client.stream("GET", f"/api/sessions/{sid}/events") as r:
        lines = list(r.iter_lines())
    failed = [json.loads(lines[i + 1][6:]) for i, l in enumerate(lines) if l == "event: evaluator_failed"]
    assert failed and failed[0]["reason"] == "quote_mismatch"


def test_draft_rubrics_are_not_used(tmp_path, monkeypatch):
    (tmp_path / "draft.json").write_text(json.dumps({**RUBRIC, "status": "draft"}))
    monkeypatch.setattr(evaluators, "RUBRICS_DIR", tmp_path)
    assert evaluators.load_rubrics() == []


def test_evidence_check_matches_contract_reference():
    transcript = (CONTRACTS / "transcript.txt").read_text(encoding="utf-8")
    out = json.loads((CONTRACTS / "evaluator_output.json").read_text(encoding="utf-8"))
    assert evaluators.check_evidence(out, transcript, 2) == []
    out["criteria"][0]["evidence_quote"] = "I would check the fuse first."
    assert evaluators.check_evidence(out, transcript, 2)


# ---- retests, lessons, skills, deletion ----
def test_retest_creates_new_session():
    s = new_session()
    r = client.post("/api/retests", json={"session_id": s["session_id"], "skill_ids": ["circuits1.grounding"]}).json()
    assert r["kind"] == "retest" and r["session_id"] != s["session_id"]


def test_lessons_and_skills_without_content():
    assert client.get("/api/lessons/circuits1.ohms_law").status_code == 404
    assert client.get("/api/skills").json() == {"user_id": None, "nodes": []}


def test_delete_session_removes_everything(scenario):
    s = new_session()
    sid = s["session_id"]
    client.post(f"/api/sessions/{sid}/turns", json={"answer": "hi"})
    client.post(f"/api/sessions/{sid}/probe", json={"node": "n1", "scenario_id": scenario})
    d = client.delete(f"/api/sessions/{sid}").json()
    assert d["deleted_rows"] >= 3
    assert client.get(f"/api/sessions/{sid}/report").status_code == 404


# ---- websockets ----
def test_voice_ws_text_fallback_and_resume():
    sid = new_session()["session_id"]
    with client.websocket_connect(f"/ws/voice/{sid}") as ws:
        assert ws.receive_json() == {"type": "state", "state": "interview"}
        assert ws.receive_json()["type"] == "interviewer_text"  # the opening question
        ws.send_json({"type": "text_answer", "text": "hello"})
        types = [ws.receive_json()["type"] for _ in range(4)]
        assert types == ["transcript_final", "interviewer_text", "timing", "tts_done"]
        ws.send_json({"type": "something_new"})  # unknown types are ignored, not fatal
        ws.send_bytes(b"\x00\x00")  # audio is buffered until speech_end, so nothing comes back
        ws.send_json({"type": "speech_end"})
        assert ws.receive_json()["code"] == "too_short"
    with client.websocket_connect(f"/ws/voice/{sid}") as ws:  # reconnect resumes
        assert ws.receive_json()["state"] == "interview"
        assert ws.receive_json()["type"] == "interviewer_text"


def test_voice_ws_unknown_session():
    with client.websocket_connect("/ws/voice/nope") as ws:
        msg = ws.receive_json()
        assert msg["code"] == "session_not_found" and msg["recoverable"] is False


def test_board_ws_pairing_and_probe_broadcast(scenario):
    s = new_session()
    sid = s["session_id"]
    with client.websocket_connect(f"/ws/board/{sid}") as laptop, client.websocket_connect(f"/ws/board/{sid}") as ipad:
        ipad.send_json({"type": "pair", "code": "WRONG1"})
        assert ipad.receive_json()["code"] == "bad_pair_code"
        ipad.send_json({"type": "pair", "code": s["pair_code"].lower()})
        assert ipad.receive_json() == {"type": "paired", "session_id": sid}
        ipad.send_json({"type": "probe", "node": "n1", "scenario_id": scenario})
        assert ipad.receive_json()["code"] == "laptop_only"
        laptop.send_json({"type": "probe", "action": "probe_voltage", "node": "n1", "scenario_id": scenario})
        a, b = laptop.receive_json(), ipad.receive_json()
        assert a == b and a["type"] == "probe_result" and a["value"] == 5.0 and a["seq"] == 0


def test_delete_removes_plan_when_no_session_uses_it():
    from app.core import store
    s = new_session("del_user")
    plan_id = (asyncio_run(store.get_record(s["session_id"])))["data"]["plan_id"]
    retest = client.post("/api/retests", json={"session_id": s["session_id"], "skill_ids": []}).json()
    client.delete(f"/api/sessions/{s['session_id']}")
    assert asyncio_run(store.get_record(plan_id)) is not None  # the retest still needs it
    client.delete(f"/api/sessions/{retest['session_id']}")
    assert asyncio_run(store.get_record(plan_id)) is None      # last user gone: resume text removed


def asyncio_run(coro):
    import asyncio
    return asyncio.run(coro)


def test_report_is_saved_before_grading_complete_is_announced(monkeypatch):
    from app.core import bus
    seen = {}
    real_publish = bus.publish

    async def spy(channel, event, data):
        if event == "grading_complete":
            sid = data["session_id"]
            seen["status"] = (await __import__("app.core.store", fromlist=["x"]).get_record(sid))["data"]["status"]
        await real_publish(channel, event, data)

    monkeypatch.setattr(bus, "publish", spy)
    sid = new_session()["session_id"]
    client.post(f"/api/sessions/{sid}/turns", json={"answer": "hello"})
    client.post(f"/api/sessions/{sid}/end")
    with client.stream("GET", f"/api/sessions/{sid}/events") as r:
        list(r.iter_lines())
    assert seen.get("status") == "graded"
