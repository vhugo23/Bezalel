import asyncio

from fastapi.testclient import TestClient

from app.core import ai, memory
from app.core.jobs import fan_out
from app.main import app

client = TestClient(app)


def test_health():
    body = client.get("/api/health").json()
    assert body["status"] == "ok"


def test_records_roundtrip():
    created = client.post("/api/records/note", json={"data": {"a": 1}, "owner_id": "u1"}).json()
    assert client.get(f"/api/record/{created['id']}").json()["data"] == {"a": 1}
    merged = client.patch(f"/api/record/{created['id']}", json={"data": {"b": 2}}).json()
    assert merged["data"] == {"a": 1, "b": 2}
    listed = client.get("/api/records/note", params={"owner_id": "u1"}).json()
    assert any(r["id"] == created["id"] for r in listed)
    assert client.get("/api/record/does-not-exist").status_code == 404


def test_events():
    client.post("/api/events", json={"subject_id": "s1", "kind": "score", "value": 0.5})
    events = client.get("/api/events/s1", params={"kind": "score"}).json()
    assert events and events[0]["value"] == 0.5


def test_ai_fake_provider():
    assert "text" in client.post("/api/ai/text", json={"prompt": "hi"}).json()
    assert "note" in client.post("/api/ai/json", json={"prompt": "hi"}).json()


def test_ai_key_guard(monkeypatch):
    from app import config
    monkeypatch.setattr(config, "APP_API_KEY", "secret")
    assert client.post("/api/ai/text", json={"prompt": "hi"}).status_code == 401
    ok = client.post("/api/ai/text", json={"prompt": "hi"}, headers={"x-api-key": "secret"})
    assert ok.status_code == 200


def test_generate_json_retries_then_fails(monkeypatch):
    calls = []

    async def bad(prompt, system=None):
        calls.append(prompt)
        return "not json"

    monkeypatch.setattr(ai, "generate_text", bad)
    try:
        asyncio.run(ai.generate_json("x"))
        assert False, "should have raised"
    except ai.AIError:
        pass
    assert len(calls) == 2  # first try + one retry


def test_memory_roundtrip():
    asyncio.run(memory.remember("owner", "likes circuits"))
    assert asyncio.run(memory.recall("owner")) == ["likes circuits"]


def test_fan_out_keeps_partial_results():
    async def ok():
        return 1

    async def boom():
        raise ValueError("x")

    async def slow():
        await asyncio.sleep(1)

    out = asyncio.run(fan_out({"ok": ok, "boom": boom, "slow": slow}, timeout=0.05))
    assert out["ok"]["ok"] and out["ok"]["result"] == 1
    assert not out["boom"]["ok"] and "ValueError" in out["boom"]["error"]
    assert not out["slow"]["ok"] and "TimeoutError" in out["slow"]["error"]


def test_fan_out_respects_concurrency_limit():
    running, peak = 0, 0

    async def job():
        nonlocal running, peak
        running += 1
        peak = max(peak, running)
        await asyncio.sleep(0.02)
        running -= 1
        return True

    out = asyncio.run(fan_out({str(i): job for i in range(6)}, timeout=2, limit=2))
    assert all(o["ok"] for o in out.values()) and peak == 2


def test_bus_replays_history_to_late_subscribers():
    from app.core import bus

    async def go():
        await bus.publish("c1", "a", {"n": 1})
        await bus.publish("c1", "b", {"n": 2})
        sub = bus.subscribe("c1")
        got = [await sub.__anext__(), await sub.__anext__()]
        await sub.aclose()
        return [g["event"] for g in got]

    assert asyncio.run(go()) == ["a", "b"]
