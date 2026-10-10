"""Interview session state and transcript, stored with core.store records.
Each candidate answer gets a stable answer_id ("<session_id>:a<n>") that evaluators reference later."""
import asyncio
import copy

from app.core import store
from app.modules.prepcrew import interviewer

# Allowed moves. Only intake -> interview -> walkthrough is exercised so far.
TRANSITIONS = {
    "intake": {"interview"},
    "interview": {"walkthrough", "debrief"},
    "walkthrough": {"drill", "debrief"},
    "drill": {"debrief"},
    "debrief": {"lesson"},
    "lesson": {"retest"},
    "retest": {"debrief"},
}

FALLBACK_SOURCE = "fallback"
HANDOFF = "Okay, that's the project part. Next I'll show you a circuit that isn't working."

_locks: dict[str, asyncio.Lock] = {}


class SessionError(Exception):
    def __init__(self, message: str, status: int = 400):
        super().__init__(message)
        self.status = status


def check_transition(old: str, new: str) -> None:
    if new not in TRANSITIONS.get(old, set()):
        raise SessionError(f"cannot go from {old} to {new}", 409)


async def create_plan(job_posting: str, resume: str) -> dict:
    plan = await interviewer.build_plan(job_posting, resume)
    rec = await store.create_record("plan", {**plan, "job_posting": job_posting, "resume": resume})
    return {"plan_id": rec["id"], **plan}


async def start(plan_id: str, user_id: str | None = None) -> dict:
    plan_rec = await store.get_record(plan_id)
    if not plan_rec or plan_rec["kind"] != "plan":
        raise SessionError("unknown plan_id", 404)
    check_transition("intake", "interview")
    opening = plan_rec["data"]["questions"][0]
    turns = [{"turn": 0, "role": "interviewer", "text": opening, "source": "plan"}]
    rec = await store.create_record(
        "session", {"plan_id": plan_id, "state": "interview", "turns": turns, "degraded_turns": 0}, owner_id=user_id
    )
    return {"session_id": rec["id"], "state": "interview", "opening": opening}


async def _load(session_id: str) -> dict:
    rec = await store.get_record(session_id)
    if not rec or rec["kind"] != "session":
        raise SessionError("unknown session_id", 404)
    return rec


async def take_turn(session_id: str, answer: str) -> dict:
    """Store the candidate answer, ask the model for the next question, store that too."""
    answer = answer.strip()
    if not answer:
        raise SessionError("empty answer", 400)
    await _load(session_id)  # unknown ids get a 404 before any lock is created
    async with _locks.setdefault(session_id, asyncio.Lock()):
        rec = await _load(session_id)
        data = rec["data"]
        if data["state"] != "interview":
            raise SessionError(f"session is in state {data['state']}, not interview", 409)
        turns = list(data["turns"])
        n = sum(1 for t in turns if t["role"] == "candidate") + 1
        answer_id = f"{session_id}:a{n}"
        turns.append({"turn": len(turns), "role": "candidate", "text": answer, "answer_id": answer_id})

        plan_rec = await store.get_record(data["plan_id"])
        if not plan_rec:
            raise SessionError("plan for this session is missing", 409)
        question, source = await interviewer.next_question(plan_rec["data"], turns)
        degraded = source == FALLBACK_SOURCE
        update = {"degraded_turns": data.get("degraded_turns", 0) + (1 if degraded else 0)}
        done = question is None
        if done:
            update["state"] = "walkthrough"
            question, source = HANDOFF, "scripted"
        turns.append({"turn": len(turns), "role": "interviewer", "text": question, "source": source})
        await store.update_record(session_id, {**update, "turns": turns})
        if done:
            _locks.pop(session_id, None)  # the session can't take more turns, free its lock
        return {"next_question": question, "answer_id": answer_id, "done": done,
                "degraded": degraded, "source": source}


async def transcript(session_id: str) -> list[dict]:
    return copy.deepcopy((await _load(session_id))["data"]["turns"])
