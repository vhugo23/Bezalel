"""PrepCrew business logic shared by the HTTP routes (routes.py) and the WebSockets (ws.py).
Storage goes through core.store (records + time-series events), so no new tables are needed yet.

Stored shapes:
  record kind "plan":    {user_id, job_posting, resume, topics, questions, scenario_ids}
  record kind "session": {plan_id, user_id, kind, pair_code, state, status, scenario_ids, current_scenario_id,
                          results, skill_flags, total_ms, parent_session_id, skill_ids, last_interviewer_text, turn}
  record kind "lesson":  {skill_id, body, ai_generated}
  events (subject = session id): "answer" {answer_id, text, turn}, "probe" {probe event},
                                 "timing" value=ms {stage}, "score" value=0..1 {user_id, skill_id, criterion_id, ...}
TODO: when contracts/db.sql (answer_scores, probe_events, mastery_daily) is verified on Tiger Data,
write scores and probes there instead of the generic events table.
"""
import asyncio
import secrets
import statistics
import time
import uuid
from collections import defaultdict
from datetime import datetime, timezone

from app.core import bus, store
from app.modules.prepcrew import evaluators, simulator, topic_graph

PAIR_ALPHABET = "ABCDEFGHJKMNPQRSTUVWXYZ23456789"  # no 0/O/1/I/L
_seq_locks: dict[str, asyncio.Lock] = defaultdict(asyncio.Lock)
_seq_next: dict[str, int] = {}


class NotFound(LookupError):
    pass


class BadRequest(ValueError):
    pass


class NotImplementedYet(NotImplementedError):
    pass


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def channel(session_id: str) -> str:
    return f"session:{session_id}"


# ---- plans ----
async def create_plan(job_posting: str, resume: str, user_id: str | None) -> dict:
    # TODO: core.ai.generate_json extracts required skills from the posting and resume,
    # maps them onto topic_graph skill ids, picks scenario ids from simulator.list_scenarios().
    data = {"user_id": user_id, "job_posting": job_posting, "resume": resume,
            "topics": [], "questions": [], "scenario_ids": []}
    rec = await store.create_record("plan", data, owner_id=user_id)
    return {"plan_id": rec["id"], **data}


# ---- sessions ----
async def get_session(session_id: str) -> dict:
    rec = await store.get_record(session_id)
    if rec is None or rec["kind"] != "session":
        raise NotFound("session not found")
    return rec


async def create_session(plan_id: str, user_id: str, consent: bool, kind: str = "interview",
                         parent_session_id: str | None = None, skill_ids: list[str] | None = None) -> dict:
    if not consent:
        raise BadRequest("consent must be true to start a session")
    plan = await store.get_record(plan_id)
    if plan is None or plan["kind"] != "plan":
        raise NotFound("plan not found")
    scenario_ids = plan["data"].get("scenario_ids", [])
    data = {
        "plan_id": plan_id, "user_id": user_id, "consent": True, "kind": kind,
        "pair_code": "".join(secrets.choice(PAIR_ALPHABET) for _ in range(6)),
        "state": "retest" if kind == "retest" else "intake", "status": "not_ended",
        "scenario_ids": scenario_ids, "current_scenario_id": scenario_ids[0] if scenario_ids else None,
        "results": [], "skill_flags": [], "total_ms": None, "turn": 0,
        "parent_session_id": parent_session_id, "skill_ids": skill_ids or [],
        "last_interviewer_text": None,
    }
    return await store.create_record("session", data, owner_id=user_id)


async def handle_answer(session_id: str, text: str) -> dict:
    """Stores one candidate answer and produces the next interviewer line. Used by POST /turns and /ws/voice."""
    start = time.perf_counter()
    session = await get_session(session_id)
    turn = int(session["data"].get("turn", 0)) + 1
    answer_id = str(uuid.uuid4())
    await store.add_event(session_id, "answer", data={"answer_id": answer_id, "text": text, "turn": turn})
    # TODO: core.memory.recall(user_id) + core.ai.generate_text with config.INTERVIEWER_MODEL. Keep it fast;
    # no grading during the live interview.
    next_question = "TODO: interviewer not implemented yet"
    await store.update_record(session_id, {"turn": turn, "last_interviewer_text": next_question,
                                           "state": "interview"})
    ms = (time.perf_counter() - start) * 1000
    await store.add_event(session_id, "timing", value=ms, data={"stage": "turn_total", "turn": turn})
    return {"answer_id": answer_id, "next_question": next_question, "turn": turn, "turn_total_ms": ms}


# ---- circuit probes (contracts/probe_event.schema.json) ----
async def _next_seq(session_id: str) -> int:
    if session_id not in _seq_next:
        existing = await store.list_events(session_id, kind="probe", limit=100000)
        _seq_next[session_id] = len(existing)
    seq = _seq_next[session_id]
    _seq_next[session_id] = seq + 1
    return seq


async def record_probe(session_id: str, action: str, node: str | None, scenario_id: str | None) -> dict:
    session = await get_session(session_id)
    scenario_id = scenario_id or session["data"].get("current_scenario_id")
    if not scenario_id:
        raise BadRequest("no scenario selected for this session")
    try:
        simulator.load_scenario(scenario_id)
    except simulator.UnknownScenario:
        raise NotFound(f"unknown scenario '{scenario_id}'")

    value, unit = None, "none"
    if action in ("probe_voltage", "probe_continuity", "swap_part", "isolate_section") and not node:
        raise BadRequest(f"{action} needs a node")
    if action == "probe_voltage":
        try:
            value, unit = simulator.read_voltage(scenario_id, node), "V"
        except simulator.UnknownNode:
            raise BadRequest(f"unknown node '{node}'")
    elif action == "probe_continuity":
        raise NotImplementedYet("continuity readings need the solver")
    # swap_part, isolate_section, power_cycle: logged with no reading (TODO: apply effects in the solver)

    async with _seq_locks[session_id]:
        event = {
            "event_id": str(uuid.uuid4()), "seq": await _next_seq(session_id), "t": now_iso(),
            "session_id": session_id, "scenario_id": scenario_id, "action": action,
            "node": node, "value": value, "unit": unit,
        }
        await store.add_event(session_id, "probe", value=value, data=event)
    return event


# ---- grading ----
async def start_grading(session_id: str) -> bool:
    """Marks the session as grading. Returns False if it was already grading or graded."""
    session = await get_session(session_id)
    if session["data"].get("status") in ("grading", "graded"):
        return False
    await store.update_record(session_id, {"status": "grading", "state": "debrief"})
    return True


async def run_grading(session_id: str) -> None:
    session = await get_session(session_id)
    answers = sorted((e["data"] for e in await store.list_events(session_id, kind="answer", limit=100000)),
                     key=lambda a: a["turn"])
    probes = sorted((e["data"] for e in await store.list_events(session_id, kind="probe", limit=100000)),
                    key=lambda p: p["seq"])
    transcript = "\n".join(f"Candidate: {a['text']}" for a in answers)

    async def publish(event: str, data: dict):
        await bus.publish(channel(session_id), event, data)

    out = await evaluators.grade_session(session_id, answers, transcript, probes, publish)

    rubrics = {r["rubric_id"]: r for r in evaluators.load_rubrics(only_reviewed=False)}
    flags: set[str] = set()
    for result in out["results"]:
        flags.update(result.get("skill_flags", []))
        rubric = rubrics.get(result["rubric_id"])
        if rubric is None:
            continue
        crit_skill = {c["id"]: c["skill_id"] for c in rubric["criteria"]}
        for c in result["criteria"]:
            await store.add_event(session_id, "score", value=c["score"] / rubric["score_max"], data={
                "user_id": session["data"]["user_id"], "answer_id": result["answer_id"],
                "skill_id": crit_skill.get(c["id"], "unknown"), "criterion_id": c["id"],
                "needs_review": bool(result.get("needs_review")), "source": "evaluator"})
    await store.add_event(session_id, "timing", value=out["total_ms"], data={"stage": "evaluator_fleet"})
    await store.update_record(session_id, {"status": "graded", "results": out["results"],
                                           "skill_flags": sorted(flags), "total_ms": out["total_ms"]})


# ---- curriculum ----
async def _user_scores(user_id: str) -> list[dict]:
    scores = []
    for s in await store.list_records("session", owner_id=user_id, limit=1000):
        for e in await store.list_events(s["id"], kind="score", limit=100000):
            if not e["data"].get("needs_review"):
                scores.append(e)
    return scores


async def skills(user_id: str | None) -> list[dict]:
    mastery: dict[str, list[float]] = defaultdict(list)
    if user_id:
        for e in await _user_scores(user_id):
            mastery[e["data"]["skill_id"]].append(e["value"])
    return [{"skill_id": sid, "title": node.get("title", sid), "prerequisites": node.get("prerequisites", []),
             "mastery": (sum(mastery[sid]) / len(mastery[sid])) if mastery.get(sid) else None}
            for sid, node in topic_graph.load_topics().items()]


async def mastery_series(user_id: str) -> list[dict]:
    buckets: dict[str, dict[str, list[float]]] = defaultdict(lambda: defaultdict(list))
    for e in await _user_scores(user_id):
        buckets[e["data"]["skill_id"]][e["created_at"][:10]].append(e["value"])
    return [{"skill_id": sid, "points": [{"day": day, "mastery": sum(v) / len(v), "n": len(v)}
                                          for day, v in sorted(days.items())]}
            for sid, days in sorted(buckets.items())]


async def lesson(skill_id: str) -> dict:
    for rec in await store.list_records("lesson", limit=1000):
        if rec["data"].get("skill_id") == skill_id:
            return rec["data"]
    raise NotFound("no lesson for this skill yet")


async def create_retest(session_id: str, skill_ids: list[str]) -> dict:
    original = await get_session(session_id)
    d = original["data"]
    return await create_session(d["plan_id"], d["user_id"], consent=bool(d.get("consent")), kind="retest",
                                parent_session_id=session_id, skill_ids=skill_ids)


# ---- metrics and deletion ----
async def metrics(session_id: str) -> dict:
    session = await get_session(session_id)
    by_stage: dict[str, list[float]] = defaultdict(list)
    timings = await store.list_events(session_id, kind="timing", limit=100000)
    for e in timings:
        by_stage[e["data"].get("stage")].append(e["value"])

    def med(stage):
        return statistics.median(by_stage[stage]) if by_stage.get(stage) else None

    return {"session_id": session_id, "stt_ms": med("stt"), "llm_first_token_ms": med("llm_first_token"),
            "tts_first_audio_ms": med("tts_first_audio"), "turn_total_ms": med("turn_total"),
            "evaluator_fleet_ms": session["data"].get("total_ms"), "samples": len(timings)}


async def delete_session(session_id: str) -> int:
    await get_session(session_id)
    removed = await store.delete_linked(session_id)
    bus.clear(channel(session_id))
    _seq_next.pop(session_id, None)
    _seq_locks.pop(session_id, None)
    return removed
