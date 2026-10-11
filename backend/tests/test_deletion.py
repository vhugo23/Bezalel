"""Consent deletion must win every race: nothing written after DELETE survives, and Backboard copies that could
not be deleted right away are retried until they are gone."""
import asyncio

import httpx
import pytest

from app import config
from app.core import memory, store
from app.modules.prepcrew import evaluators, service, timeseries
from app.modules.prepcrew.service import NotFound
from tests.test_memory import FakeBackboard, _session_with_gap, client
from tests.test_prepcrew import new_session, scenario  # noqa: F401  (fixture)


def test_grading_that_finishes_after_delete_writes_nothing(monkeypatch):
    sid = new_session("late_grader")["session_id"]
    client.post(f"/api/sessions/{sid}/turns", json={"answer": "I'd check the supply first."})
    written = []

    async def scenario_():
        gate = asyncio.Event()

        async def slow_grade(session_id, answers, transcript, probes, publish):
            await gate.wait()
            return {"results": [], "total_ms": 1.0}

        async def spy(rows):
            written.extend(rows)

        monkeypatch.setattr(evaluators, "grade_session", slow_grade)
        monkeypatch.setattr(timeseries, "write_scores", spy)
        grading = asyncio.create_task(service.run_grading(sid))
        await asyncio.sleep(0)
        await service.delete_session(sid)
        gate.set()
        await grading
        assert await store.get_record(sid) is None
        assert await store.list_events(sid, limit=1000) == []

    asyncio.run(scenario_())
    assert written == []


def test_probe_queued_behind_delete_is_rejected(scenario):  # noqa: F811
    sid = new_session("prober")["session_id"]

    async def scenario_():
        lock = service._seq_locks[sid]
        await lock.acquire()                     # hold the lock so delete and the probe both queue on it
        deleting = asyncio.create_task(service.delete_session(sid))
        await asyncio.sleep(0.01)
        probing = asyncio.create_task(service.record_probe(sid, "probe_voltage", "n1", scenario))
        await asyncio.sleep(0.01)
        lock.release()
        await deleting
        with pytest.raises(NotFound):
            await probing
        assert await store.list_events(sid, limit=1000) == []

    asyncio.run(scenario_())


def test_answer_queued_behind_delete_is_rejected():
    sid = new_session("talker")["session_id"]

    async def scenario_():
        lock = service._turn_locks[sid]
        await lock.acquire()
        deleting = asyncio.create_task(service.delete_session(sid))
        await asyncio.sleep(0.01)
        answering = asyncio.create_task(service.handle_answer(sid, "hello"))
        await asyncio.sleep(0.01)
        lock.release()
        await deleting
        with pytest.raises(NotFound):
            await answering
        assert await store.list_events(sid, limit=1000) == []

    asyncio.run(scenario_())


def test_timing_after_delete_is_dropped():
    sid = new_session("timer")["session_id"]
    client.delete(f"/api/sessions/{sid}")
    asyncio.run(service.record_timing(sid, "stt", 12.0))
    assert asyncio.run(store.list_events(sid, limit=10)) == []


@pytest.fixture
def bb(monkeypatch):
    fake = FakeBackboard()
    monkeypatch.setattr(config, "MEMORY_BACKEND", "backboard")
    monkeypatch.setattr(config, "BACKBOARD_API_KEY", "test-key")
    monkeypatch.setattr(memory, "_transport", httpx.MockTransport(fake.handler))
    return fake


def test_backboard_down_during_delete_is_retried_later(bb):
    _, sid = _session_with_gap("kim")
    assert asyncio.run(service.save_session_memories(sid)) == 2
    bb.fail = True
    assert client.delete(f"/api/sessions/{sid}").status_code == 200
    assert bb.count() == 2                                   # could not delete yet...
    pending = asyncio.run(store.list_records("memory_forget_pending", limit=100))
    assert len(pending) == 2                                 # ...but we kept track of them
    bb.fail = False
    assert asyncio.run(service.retry_pending_forgets()) == 2
    assert bb.count() == 0
    assert asyncio.run(store.list_records("memory_forget_pending", limit=100)) == []


def test_memory_already_gone_on_backboard_counts_as_deleted(bb, monkeypatch):
    ref = asyncio.run(memory.remember("lee", "Gap: ADC"))

    def gone(request):                                       # someone removed it in the Backboard dashboard
        return httpx.Response(404, json={"detail": "memory not found"})

    monkeypatch.setattr(memory, "_transport", httpx.MockTransport(gone))
    removed, failed = asyncio.run(memory.forget_detailed([ref]))
    assert failed == []                                      # not retried forever


def test_delete_waits_for_an_answer_in_progress(monkeypatch):
    from app.modules.prepcrew import interviewer
    sid = new_session("slow_talker")["session_id"]

    async def scenario_():
        gate, started = asyncio.Event(), asyncio.Event()
        real = interviewer.next_question

        async def slow(*a, **k):
            started.set()
            await gate.wait()
            return await real(*a, **k)

        monkeypatch.setattr(interviewer, "next_question", slow)
        answering = asyncio.create_task(service.handle_answer(sid, "I'd check the supply first."))
        await started.wait()                                 # the answer is past its checks, mid-LLM call
        deleting = asyncio.create_task(service.delete_session(sid))
        await asyncio.sleep(0.02)
        assert not deleting.done()                           # delete waits for the answer...
        gate.set()
        await answering
        await deleting
        assert await store.list_events(sid, limit=1000) == []  # ...then removes it too

    asyncio.run(scenario_())


def test_slow_memory_recall_does_not_hold_up_plans(monkeypatch):
    async def stuck(*a, **k):
        await asyncio.sleep(60)

    monkeypatch.setattr(memory, "recall", stuck)
    monkeypatch.setattr(service, "RECALL_TIMEOUT_SECONDS", 0.05)
    assert asyncio.run(service.recall_memories("u", "q")) == []
