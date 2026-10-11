import asyncio

from fastapi.testclient import TestClient

from app.core import ai, memory
from app.core.jobs import fan_out
from app.main import app

client = TestClient(app)


def test_health():
    body = client.get("/api/health").json()
    assert body["status"] == "ok"


def test_store_records_roundtrip():
    """The generic store is internal now (no public endpoint), so test it directly."""
    from app.core import store

    async def go():
        created = await store.create_record("note", {"a": 1}, owner_id="u1")
        assert (await store.get_record(created["id"]))["data"] == {"a": 1}
        merged = await store.update_record(created["id"], {"b": 2})
        assert merged["data"] == {"a": 1, "b": 2}
        assert any(r["id"] == created["id"] for r in await store.list_records("note", owner_id="u1"))
        assert await store.get_record("does-not-exist") is None

    asyncio.run(go())


def test_store_events():
    from app.core import store

    async def go():
        await store.add_event("s1", "score", value=0.5)
        events = await store.list_events("s1", kind="score")
        assert events and events[0]["value"] == 0.5

    asyncio.run(go())


def test_removed_endpoints_stay_removed():
    """Open read/write and AI endpoints were removed on purpose: they exposed session data and the AI key."""
    for method, path in [("post", "/api/records/note"), ("get", "/api/record/x"), ("post", "/api/events"),
                         ("get", "/api/events/s1"), ("post", "/api/ai/text"), ("post", "/api/ai/json")]:
        assert client.request(method.upper(), path).status_code in (404, 405), path


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
