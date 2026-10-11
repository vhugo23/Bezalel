"""One entry point for the lane 1 hardware interview, for a caller that keeps its own storage (the v2 app).

Three functions. No database, no store, no websocket, no locks:
  start(job_posting, resume, strict=True)  -> the plan, the opening line and the first state
  answer(state, text)                      -> the next interviewer line, the new state, the patience meter, done flags
  debrief(state)                           -> the dict debrief.build gives the legacy GET /api/sessions/{id}/debrief

The state is a plain dict of JSON types (str, int, float, bool, None, list, dict). Keep it in a JSONB column and pass
it back unchanged. answer() never changes the dict it is given, it returns a new one. It does not lock: call it once
at a time per interview, and compare state["turn"] before saving if two answers could race.

The state holds only what the interviewer needs (plan, the interview transcript so far, the meter). It is not the
transcript of record. The caller stores each answer and each reply itself.

This is the same logic as service.handle_answer, which stays the legacy path's own copy. It calls the same
interviewer.build_plan, interviewer.next_question, assessor.assess, meter.apply, meter.snapshot and debrief.build, so
it degrades the same way: a model timeout, an error or bad JSON gives the planned question (source "fallback") and no
penalty, and a gap or a skipped question counts only when its quote is in the candidate's words. Nothing is invented.
tests/test_hardware_interview.py runs both paths on the same inputs and compares them.

    r = await hardware_interview.start(posting_text, resume_text)
    state = r["state"]                       # save this
    speak(r["opening"])
    t = await hardware_interview.answer(state, "I never used SPI")
    state = t["state"]                       # save this
    speak(t["reply"])
    if t["phase"] != "interview": ...        # the interview part is over, see below
    summary = hardware_interview.debrief(state)

phase: "interview" while questions continue. "walkthrough" once the plan is used up (the reply is the hand-off line,
done is True). The caller now moves to its own next step. More answers get the legacy placeholder line. "debrief"
after the patience meter ended a strict interview (the reply is the closing line, done and ended_early are True).
Answers are then refused with InterviewEnded."""
import asyncio
import copy
import logging

from app import config
from app.modules.prepcrew import assessor, interviewer, meter
from app.modules.prepcrew import debrief as _debrief

log = logging.getLogger("prepcrew.hardware_interview")

VERSION = 1
MAX_ANSWER_CHARS = 5000  # same limit as service.MAX_ANSWER_CHARS
INTERVIEW, WALKTHROUGH, DEBRIEF = "interview", "walkthrough", "debrief"
PHASES = (INTERVIEW, WALKTHROUGH, DEBRIEF)
SCRIPTED = "scripted"  # a line from the code's own pools (closing, hand-off, placeholder), never the model


class InterviewError(ValueError):
    pass


class BadAnswer(InterviewError):
    """The answer is empty or too long. The state is unchanged."""


class InterviewEnded(InterviewError):
    """The patience meter already ended this interview. Build the debrief instead."""


class InvalidState(InterviewError):
    """The state is not one that start() or answer() produced (wrong version, missing or corrupted parts)."""


async def start(job_posting: str, resume: str, strict: bool = True) -> dict:
    """Builds the plan and the opening question. Never fails on a model problem: a model error, timeout or bad JSON
    gives generic questions and "degraded": True (and no skills, so the meter can then only count skipped questions).
    strict=False means the meter steers the interview toward a close but never ends it.
    Returns {"plan", "opening", "degraded", "state"}."""
    plan = await interviewer.build_plan(job_posting, resume)
    opening = plan["questions"][0]  # build_plan always returns at least one question
    state = {
        "version": VERSION, "phase": INTERVIEW, "strict": bool(strict), "plan": plan, "turn": 0,
        "turns": [{"role": "interviewer", "text": opening, "turn": 0, "shape": None}],
        "last_interviewer_text": opening, "degraded_turns": 0,
        "meter_state": meter.new_state(), "meter_findings": [],
        "ended_early": False, "end_reason": None, "end_gaps": [],
    }
    return {"plan": copy.deepcopy(plan), "opening": opening, "degraded": plan["degraded"], "state": state}


async def answer(state: dict, text: str) -> dict:
    """Takes one candidate answer and returns what the interviewer says next.
    Returns {"reply", "turn", "done", "ended_early", "phase", "source", "degraded", "meter", "findings", "shape",
    "violations", "state"}. source is "model", "fallback" (the planned question, because the model failed), "fake"
    (no model configured) or "scripted". meter is None when no model is configured. meter["checked"] is False when the
    gap check failed or timed out on this answer, which means nothing was judged and nothing was counted.
    findings are this answer's verified gaps and strengths, each with the candidate's own words.
    Raises BadAnswer, InterviewEnded or InvalidState, and leaves the given state untouched."""
    _check_state(state)
    text = (text or "").strip()
    if not text:
        raise BadAnswer("empty answer")
    if len(text) > MAX_ANSWER_CHARS:
        raise BadAnswer(f"answer is over {MAX_ANSWER_CHARS} characters")
    if state["phase"] == DEBRIEF:
        raise InterviewEnded("the interview has ended, build the debrief")

    s = copy.deepcopy(state)
    phase = s["phase"]
    turn = s["turn"] + 1
    s["turn"] = turn
    done, ended_early, source, shape, violations = False, False, SCRIPTED, None, []
    findings, snap = [], None
    if phase == INTERVIEW:
        s["turns"].append({"role": "candidate", "text": text, "turn": turn, "shape": None})
        plan = s["plan"]
        requirements = plan.get("requirements", [])
        strict = s["strict"]
        enabled = config.LLM_PROVIDER != "fake"  # the check needs a real model
        before = meter.snapshot(s["meter_state"], strict) if enabled else None
        pressure = "wrapping_up" if before and before["level"] != "ok" else "normal"
        question_asked = s["last_interviewer_text"] or ""
        reply, assessment = await _reply_and_check(plan, s["turns"], pressure, requirements, text, question_asked)
        findings = assessment.findings
        counted_no_answer = meter.counts_as_no_answer(findings, assessment.no_answer)
        mstate = meter.apply(s["meter_state"], findings, requirements, assessment.no_answer)
        snap = {**meter.snapshot(mstate, strict), "checked": assessment.ok} if enabled else None
        new = [{**f, "turn": turn} for f in findings]
        if counted_no_answer:
            new.append({"kind": "no_answer", "turn": turn, "question": question_asked,
                        "evidence_quote": assessment.no_answer["evidence_quote"]})
        s["meter_state"], s["meter_findings"] = mstate, s["meter_findings"] + new
        question, source, shape, violations = reply.text, reply.source, reply.shape, reply.violations
        if snap and snap["level"] == "ended":
            done = ended_early = True
            question, source, shape, violations = interviewer.closing(), SCRIPTED, None, []
            s.update(phase=DEBRIEF, ended_early=True, end_reason="requirement_gaps",
                     end_gaps=_end_gaps(requirements, mstate["items"], s["meter_findings"]))
        elif question is None:
            done = True
            question, source = interviewer.handoff(), SCRIPTED
            s["phase"] = WALKTHROUGH
        s["turns"].append({"role": "interviewer", "text": question, "turn": turn, "shape": shape})
    else:  # walkthrough: the legacy placeholder, nothing is judged
        question = interviewer.walkthrough_placeholder(s["last_interviewer_text"])
    degraded = source == interviewer.FALLBACK
    s["last_interviewer_text"] = question
    s["degraded_turns"] += 1 if degraded else 0
    return {"reply": question, "turn": turn, "done": done, "ended_early": ended_early, "phase": s["phase"],
            "source": source, "degraded": degraded, "meter": snap, "findings": findings, "shape": shape,
            "violations": violations, "state": s}


def debrief(state: dict) -> dict:
    """The same debrief the legacy path serves: gaps worst first with the candidate's quotes, strengths, up to two
    links per gap, a template summary. No model call. Works at any point; before the end it describes what is known."""
    _check_state(state)
    return _debrief.build({**state, "state": state["phase"]}, state["plan"])


async def _reply_and_check(plan: dict, turns: list[dict], pressure: str, requirements: list[dict], text: str,
                           question_asked: str):
    """The next line and the gap check, run side by side. Both already catch model errors themselves. This also
    catches a bug in either one, so a live demo turn falls back to the planned question instead of failing."""
    reply, assessment = await asyncio.gather(
        interviewer.next_question(plan, turns, pressure=pressure),
        assessor.assess(requirements, text, question_asked), return_exceptions=True)
    for result in (reply, assessment):
        if isinstance(result, BaseException) and not isinstance(result, Exception):
            raise result  # a cancellation is not a failure to hide
    if isinstance(reply, Exception):
        log.warning("reply fallback after unexpected %s", type(reply).__name__)
        asked = sum(1 for t in turns if t["role"] == "candidate")
        questions = plan["questions"]
        reply = interviewer.Reply(questions[asked] if asked < len(questions) else None, interviewer.FALLBACK)
    if isinstance(assessment, Exception):
        log.warning("gap check skipped after unexpected %s", type(assessment).__name__)
        assessment = assessor.Assessment(ok=False)
    return reply, assessment


def _end_gaps(requirements: list[dict], items: dict[str, str], findings: list[dict]) -> list[dict]:
    """The gaps behind an early end, with the candidate's own words. Same as service._gap_list (a test compares them)."""
    by_id = {r["id"]: r for r in requirements}
    gaps = []
    for rid, result in items.items():
        if result == "knows" or rid not in by_id:
            continue
        quote = next((f["evidence_quote"] for f in reversed(findings)
                      if f.get("requirement_id") == rid and f.get("result") == result), "")
        gaps.append({"requirement_id": rid, "text": by_id[rid]["text"], "level": by_id[rid]["level"],
                     "result": result, "evidence_quote": quote})
    for f in findings:  # questions the candidate ignored
        if f.get("kind") == "no_answer":
            gaps.append({"requirement_id": None, "text": f"did not answer: {f['question']}", "level": None,
                         "result": "no_answer", "evidence_quote": f["evidence_quote"]})
    return gaps


def _check_state(state) -> None:
    """Stops a stale, hand-edited or foreign dict early with one clear error, not a KeyError deep in the meter."""
    try:
        ok = (isinstance(state, dict) and state["version"] == VERSION and state["phase"] in PHASES
              and type(state["turn"]) is int and state["turn"] >= 0 and type(state["strict"]) is bool
              and isinstance(state["plan"]["questions"], list) and isinstance(state["plan"].get("requirements", []), list)
              and isinstance(state["degraded_turns"], int) and isinstance(state["meter_findings"], list)
              and isinstance(state["turns"], list)
              and all(t["role"] in ("candidate", "interviewer") and isinstance(t["text"], str) for t in state["turns"])
              and all(isinstance(q, str) for q in state["plan"]["questions"])
              and isinstance(state["meter_state"]["unanswered"], int) and isinstance(state["meter_state"]["raw"], (int, float))
              and isinstance(state["meter_state"]["score"], (int, float))
              and all(v in ("knows", "partial", "unknown") for v in state["meter_state"]["items"].values()))
    except (KeyError, TypeError, AttributeError):
        ok = False
    if not ok:
        raise InvalidState("not a state made by hardware_interview.start or answer")
