"""Interview loop tests. Run on the fake provider, or with ai.generate_text patched to misbehave.
No keys and no network needed."""
import asyncio
import json

import pytest
from fastapi.testclient import TestClient

from app import config
from app.core import ai
from app.main import app
from app.modules.prepcrew import interviewer, session

client = TestClient(app)


def new_session() -> str:
    plan = client.post("/api/plans", json={"job_posting": "Embedded firmware intern", "resume": "Built an RC filter"}).json()
    return client.post("/api/sessions", json={"plan_id": plan["plan_id"]}).json()["session_id"]


def answer(sid: str, text: str = "I checked the supply first."):
    return client.post(f"/api/sessions/{sid}/turns", json={"answer": text})


def test_full_typed_interview_on_fake_provider():
    sid = new_session()
    ids, last = [], None
    for i in range(interviewer.MAX_ANSWERS):
        r = answer(sid, f"answer {i}")
        assert r.status_code == 200
        last = r.json()
        ids.append(last["answer_id"])
    assert ids == [f"{sid}:a{n}" for n in range(1, interviewer.MAX_ANSWERS + 1)]
    assert last["done"] is True
    assert answer(sid).status_code == 409  # interview is over, session is in walkthrough


def test_session_opens_with_a_question_and_stores_transcript():
    plan = client.post("/api/plans", json={"job_posting": "j", "resume": "r"}).json()
    started = client.post("/api/sessions", json={"plan_id": plan["plan_id"]}).json()
    assert started["opening"] == plan["questions"][0]
    assert started["state"] == "interview"
    answer(started["session_id"], "hello there")
    turns = asyncio.run(session.transcript(started["session_id"]))
    assert [t["role"] for t in turns] == ["interviewer", "candidate", "interviewer"]
    assert turns[1]["answer_id"].endswith(":a1")


@pytest.mark.parametrize("text", ["", "   ", "\n\t"])
def test_empty_answer_rejected(text):
    assert answer(new_session(), text).status_code == 400


def test_oversized_answer_rejected():
    assert answer(new_session(), "x" * 5001).status_code == 422


def test_unknown_ids():
    assert client.post("/api/sessions", json={"plan_id": "nope"}).status_code == 404
    assert answer("nope").status_code == 404


def test_session_id_cannot_be_used_as_plan_id():
    sid = new_session()
    assert client.post("/api/sessions", json={"plan_id": sid}).status_code == 404


def test_bad_transition_rejected():
    with pytest.raises(session.SessionError):
        session.check_transition("interview", "retest")
    session.check_transition("interview", "walkthrough")


# ---- model misbehaviour ----

def patch_model(monkeypatch, fn):
    monkeypatch.setattr(config, "LLM_PROVIDER", "gemini")  # anything but fake, so the model path runs
    monkeypatch.setattr(ai, "generate_text", fn)


def test_plan_falls_back_on_bad_model_json(monkeypatch):
    async def junk(prompt, system=None):
        return "this is not json at all"
    patch_model(monkeypatch, junk)
    plan = client.post("/api/plans", json={"job_posting": "j", "resume": "r"}).json()
    assert plan["degraded"] is True
    assert plan["questions"]


def test_plan_falls_back_on_wrong_json_shape(monkeypatch):
    async def wrong(prompt, system=None):
        return json.dumps({"project": "x"})  # missing topics and questions
    patch_model(monkeypatch, wrong)
    assert client.post("/api/plans", json={"job_posting": "j", "resume": "r"}).json()["degraded"] is True


def test_plan_uses_valid_model_json(monkeypatch):
    async def good(prompt, system=None):
        return json.dumps({"project": "RC filter", "topics": ["circuits1.ohms_law"], "questions": ["Tell me about the RC filter."]})
    patch_model(monkeypatch, good)
    plan = client.post("/api/plans", json={"job_posting": "j", "resume": "r"}).json()
    assert plan["degraded"] is False
    assert plan["project"] == "RC filter"


def test_plan_falls_back_when_model_returns_no_questions(monkeypatch):
    async def empty(prompt, system=None):
        return json.dumps({"project": "x", "topics": [], "questions": []})
    patch_model(monkeypatch, empty)
    assert client.post("/api/plans", json={"job_posting": "j", "resume": "r"}).json()["degraded"] is True


def test_turn_falls_back_on_model_timeout(monkeypatch):
    sid = new_session()  # created on the fake provider
    async def hang(prompt, system=None):
        await asyncio.sleep(30)
    patch_model(monkeypatch, hang)
    monkeypatch.setattr(config, "TASK_TIMEOUT_SECONDS", 0.05)
    r = answer(sid).json()
    assert r["degraded"] is True
    assert r["next_question"]  # planned question asked instead
    assert r["answer_id"].endswith(":a1")


def test_turn_falls_back_on_model_error(monkeypatch):
    sid = new_session()
    async def boom(prompt, system=None):
        raise ai.AIError("Gemini error 500")
    patch_model(monkeypatch, boom)
    assert answer(sid).json()["degraded"] is True


def test_turn_falls_back_on_empty_model_text(monkeypatch):
    sid = new_session()
    async def blank(prompt, system=None):
        return "   "
    patch_model(monkeypatch, blank)
    assert answer(sid).json()["degraded"] is True


def test_turn_uses_model_text_when_it_works(monkeypatch):
    sid = new_session()
    async def fine(prompt, system=None):
        return "  What did the scope show?  "
    patch_model(monkeypatch, fine)
    r = answer(sid).json()
    assert r["degraded"] is False
    assert r["next_question"] == "What did the scope show?"


def test_degraded_turns_are_counted():
    sid = new_session()
    asyncio.run(session.take_turn(sid, "one"))
    rec = asyncio.run(session._load(sid))
    assert rec["data"]["degraded_turns"] == 0


def test_concurrent_turns_get_distinct_answer_ids():
    async def run():
        plan = await session.create_plan("j", "r")
        sid = (await session.start(plan["plan_id"]))["session_id"]
        results = await asyncio.gather(*(session.take_turn(sid, f"a{i}") for i in range(3)))
        return sorted(r["answer_id"] for r in results), sid
    ids, sid = asyncio.run(run())
    assert ids == [f"{sid}:a1", f"{sid}:a2", f"{sid}:a3"]
