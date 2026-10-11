"""Memory across sessions. Backboard is replaced by a fake server that follows its documented API
(https://docs.backboard.io/api-reference), so no test ever calls the real service."""
import asyncio
import json
import uuid

import httpx
import pytest
from fastapi.testclient import TestClient

from app import config
from app.core import memory, store
from app.main import app
from app.modules.prepcrew import service

client = TestClient(app)


class FakeBackboard:
    """Assistants and memories in a dict. `fail` makes every call return 500; `id_key` picks the add-memory reply."""

    def __init__(self, id_key="memory_id"):
        self.assistants: dict[str, list[dict]] = {}
        self.calls: list[str] = []
        self.fail = False
        self.id_key = id_key

    def handler(self, request: httpx.Request) -> httpx.Response:
        assert request.headers.get("X-API-Key") == "test-key"
        path, m = request.url.path.removeprefix("/api"), request.method
        self.calls.append(f"{m} {path}")
        if self.fail:
            return httpx.Response(500, text="down")
        parts = path.strip("/").split("/")
        if m == "POST" and parts == ["assistants"]:
            aid = str(uuid.uuid4()); self.assistants[aid] = []
            return httpx.Response(200, json={"assistant_id": aid, "name": json.loads(request.content)["name"]})
        aid = parts[1]
        if m == "DELETE" and len(parts) == 2:
            self.assistants.pop(aid, None)
            return httpx.Response(200, json={"message": "deleted", "assistant_id": aid, "deleted_at": "now"})
        if aid not in self.assistants:
            return httpx.Response(404, json={"detail": "no such assistant"})
        mems = self.assistants[aid]
        if m == "POST" and parts[2:] == ["memories"]:
            body = json.loads(request.content); mid = str(uuid.uuid4())
            mems.append({"id": mid, "content": body["content"], "metadata": body.get("metadata")})
            return httpx.Response(201, json={self.id_key: mid} if self.id_key else {"status": "queued"})
        if m == "POST" and parts[2:] == ["memories", "search"]:
            q = set(json.loads(request.content)["query"].lower().split())
            ranked = sorted(mems, key=lambda x: -len(q & set(x["content"].lower().split())))
            limit = json.loads(request.content).get("limit", 5)
            return httpx.Response(200, json={"memories": [{"id": x["id"], "content": x["content"], "score": 1.0}
                                                          for x in ranked[:limit]], "total_count": len(ranked)})
        if m == "GET" and parts[2:] == ["memories"]:
            return httpx.Response(200, json={"memories": mems, "total_count": len(mems)})
        if m == "DELETE" and parts[2] == "memories":
            before = len(mems); mems[:] = [x for x in mems if x["id"] != parts[3]]
            return httpx.Response(200, json={"success": len(mems) < before, "message": "ok"})
        return httpx.Response(404)

    def count(self) -> int:
        return sum(len(v) for v in self.assistants.values())


@pytest.fixture
def bb(monkeypatch):
    fake = FakeBackboard()
    monkeypatch.setattr(config, "MEMORY_BACKEND", "backboard")
    monkeypatch.setattr(config, "BACKBOARD_API_KEY", "test-key")
    monkeypatch.setattr(memory, "_transport", httpx.MockTransport(fake.handler))
    return fake


def run(coro):
    return asyncio.run(coro)


# ---- core.memory ----
def test_backboard_roundtrip_one_assistant_per_owner(bb):
    r1 = run(memory.remember("alice", "Gap: never used an oscilloscope"))
    run(memory.remember("alice", "Strength: knows Ohm's law"))
    run(memory.remember("bob", "Gap: no soldering"))
    assert r1["backend"] == "backboard" and r1["id"]
    assert len(bb.assistants) == 2                       # alice and bob, each created once
    assert "oscilloscope" in run(memory.recall("alice", "oscilloscope probing", limit=1))[0]
    assert run(memory.recall("bob")) == ["Gap: no soldering"]  # no cross-user leakage
    assert run(memory.forget([r1])) == 1
    assert all("oscilloscope" not in t for t in run(memory.recall("alice")))


def test_backboard_down_falls_back_and_never_raises(bb):
    bb.fail = True
    ref = run(memory.remember("carol", "Gap: SPI"))
    assert ref["backend"] == "memory"                    # local fallback (no database in tests)
    assert run(memory.recall("carol", "SPI")) == ["Gap: SPI"]
    assert run(memory.forget([{"backend": "backboard", "id": "x", "assistant_id": "y"}])) == 0


def test_add_memory_reply_without_id_is_tolerated(monkeypatch):
    fake = FakeBackboard(id_key="")
    monkeypatch.setattr(config, "MEMORY_BACKEND", "backboard")
    monkeypatch.setattr(config, "BACKBOARD_API_KEY", "test-key")
    monkeypatch.setattr(memory, "_transport", httpx.MockTransport(fake.handler))
    ref = run(memory.remember("dan", "Gap: I2C"))
    assert ref == {"backend": "backboard", "id": None, "assistant_id": ref["assistant_id"]}
    assert run(memory.forget([ref])) == 0                # nothing to delete one by one, and no crash


def test_alternate_id_key_is_understood(monkeypatch):
    fake = FakeBackboard(id_key="id")
    monkeypatch.setattr(config, "MEMORY_BACKEND", "backboard")
    monkeypatch.setattr(config, "BACKBOARD_API_KEY", "test-key")
    monkeypatch.setattr(memory, "_transport", httpx.MockTransport(fake.handler))
    assert run(memory.remember("erin", "Gap: UART"))["id"]


def test_local_backend_forget():
    ref = run(memory.remember("frank", "note"))
    assert ref["backend"] == "memory" and run(memory.forget([ref])) == 1 and run(memory.recall("frank")) == []


# ---- session lifecycle ----
def _session_with_gap(user="grace"):
    plan = client.post("/api/plans", json={"job_posting": "Embedded intern, oscilloscope", "resume": "r", "user_id": user}).json()
    sid = client.post("/api/sessions", json={"plan_id": plan["plan_id"], "user_id": user, "consent": True}).json()["session_id"]

    async def seed():
        await store.update_record(plan["plan_id"], {"requirements": [
            {"id": "r1", "text": "oscilloscope debugging", "level": "required"},
            {"id": "r2", "text": "Ohm's law", "level": "preferred"}]})
        await store.update_record(sid, {
            "meter_state": {"items": {"r1": "unknown", "r2": "knows"}, "unanswered": 0, "raw": 0.6, "score": 0.6},
            "meter_findings": [{"requirement_id": "r1", "result": "unknown", "evidence_quote": "I haven't used a scope", "turn": 1},
                               {"requirement_id": "r2", "result": "knows", "evidence_quote": "V equals I R", "turn": 2}]})
    run(seed())
    return plan, sid


def test_end_saves_memories_next_plan_recalls_them_delete_removes_them(bb):
    plan, sid = _session_with_gap()
    client.post(f"/api/sessions/{sid}/end")
    with client.stream("GET", f"/api/sessions/{sid}/events") as r:
        list(r.iter_lines())
    assert bb.count() == 2                               # one gap, one strength
    saved = [m["content"] for a in bb.assistants.values() for m in a]
    assert any("oscilloscope debugging" in t and "I haven't used a scope" in t for t in saved)

    plan2 = client.post("/api/plans", json={"job_posting": "Hardware intern, oscilloscope", "resume": "r", "user_id": "grace"}).json()
    assert plan2["memories"] and "oscilloscope" in plan2["memories"][0]
    s2 = client.post("/api/sessions", json={"plan_id": plan2["plan_id"], "user_id": "grace", "consent": True}).json()
    assert s2["recalled"] == plan2["memories"]

    client.delete(f"/api/sessions/{sid}")
    assert bb.count() == 0                               # consent: the Backboard copies are gone too
    assert run(store.find_records("memory_ref", "session_id", sid)) == []


def test_saving_twice_does_not_duplicate(bb):
    _, sid = _session_with_gap("henry")
    assert run(service.save_session_memories(sid)) == 2
    assert run(service.save_session_memories(sid)) == 0
    assert bb.count() == 2


def test_session_deleted_while_saving_leaves_nothing(bb, monkeypatch):
    _, sid = _session_with_gap("ivy")
    real = memory.remember

    async def remember_then_delete(owner, text, data=None):
        ref = await real(owner, text, data)
        await store.delete_linked(sid)                   # user deletes mid-save
        return ref

    monkeypatch.setattr(memory, "remember", remember_then_delete)
    run(service.save_session_memories(sid))
    assert bb.count() == 0


def test_first_session_and_anonymous_plans_have_no_memories(bb):
    assert client.post("/api/plans", json={"job_posting": "p", "resume": "r", "user_id": "new_user"}).json()["memories"] == []
    assert client.post("/api/plans", json={"job_posting": "p", "resume": "r"}).json()["memories"] == []
    assert not any(c.startswith("POST /assistants") and c.endswith("/memories") for c in bb.calls)
