"""The debrief shown at the end of the interview: what stood out, what went fine, and where to learn each gap.

Built only from what the session recorded (the patience meter's findings with the candidate's own quoted words), the
posting's skills, and the verified resource library. No model call, so nothing in it is invented: every quote was
checked against the answer, every link comes from data/resources.json, and the summary is a template."""
from app import config
from app.modules.prepcrew import meter, resources

TIP_UNANSWERED = ("If you're not sure, say what you would check or try first. "
                  "A partial answer is better than none, and it gives the interviewer something to work with.")

# worst first
_ORDER = {("required", "unknown"): 0, ("required", "partial"): 1, ("preferred", "unknown"): 2, ("preferred", "partial"): 3}


def _names(items: list[str]) -> str:
    return items[0] if len(items) == 1 else ", ".join(items[:-1]) + " and " + items[-1]


def _latest(findings: list[dict], rid: str, result: str) -> tuple[str, int | None]:
    for f in reversed(findings):
        if f.get("requirement_id") == rid and f.get("result") == result:
            return f["evidence_quote"], f.get("turn")
    return "", None


def _summary(ended_early: bool, gaps: list[dict], strengths: list[dict]) -> str:
    unknown = [g["title"] for g in gaps if g["kind"] == "skill" and g["result"] == "unknown"]
    partial = [g["title"] for g in gaps if g["kind"] == "skill" and g["result"] == "partial"]
    unanswered = [g for g in gaps if g["kind"] == "unanswered"]
    parts = ["This interview ended early."] if ended_early else []
    if not gaps:
        parts.append("Nothing you said stood out as a gap.")
    else:
        bits = []
        if unknown:
            bits.append(f"you said you haven't used {_names(unknown)}")
        if partial:
            bits.append(f"you have only limited experience with {_names(partial)}")
        if unanswered:
            bits.append("one question didn't get an answer" if len(unanswered) == 1
                        else f"{len(unanswered)} questions didn't get an answer")
        parts.append("Here is what stood out: " + "; ".join(bits) + ".")
    if strengths:
        parts.append(f"You did show you know {_names([s['title'] for s in strengths])}.")
    return " ".join(parts)


def build(session: dict, plan: dict | None) -> dict:
    """session and plan are the stored `data` dicts. Works at any point: before the end it describes what is known so far."""
    d = session
    reqs = {r["id"]: r for r in (plan or {}).get("requirements", [])}
    state = d.get("meter_state") or meter.new_state()
    findings = d.get("meter_findings") or []

    skill_gaps, strengths = [], []
    for rid, result in state["items"].items():
        req = reqs.get(rid)
        if req is None:
            continue
        quote, turn = _latest(findings, rid, result)
        if result == "knows":
            strengths.append({"requirement_id": rid, "title": req["text"], "evidence_quote": quote})
            continue
        found = resources.match(req["text"])
        skill_gaps.append({"kind": "skill", "requirement_id": rid, "title": req["text"], "level": req["level"],
                           "result": result, "evidence_quote": quote, "turn": turn, "resources": found,
                           "search_hint": None if found else resources.search_hint(req["text"]), "tip": None})
    skill_gaps.sort(key=lambda g: _ORDER[(g["level"], g["result"])])

    unanswered = [{"kind": "unanswered", "requirement_id": None, "title": f"Didn't answer: {f['question']}",
                   "level": None, "result": "no_answer", "evidence_quote": f["evidence_quote"], "turn": f.get("turn"),
                   "resources": resources.match(f["question"]), "search_hint": None, "tip": TIP_UNANSWERED}
                  for f in findings if f.get("kind") == "no_answer"]
    gaps = skill_gaps + unanswered

    ended_early = bool(d.get("ended_early"))
    status = "ended_early" if ended_early else ("in_progress" if d.get("state") in ("intake", "interview")
                                                else "interview_finished")
    lib = resources.library()
    return {
        "status": status, "ended_early": ended_early, "end_reason": d.get("end_reason"),
        "summary": _summary(ended_early, gaps, strengths),
        "gaps": gaps, "strengths": strengths,
        "meter": ({**meter.snapshot(state, bool(d.get("strict", True)))}
                  if config.LLM_PROVIDER != "fake" else None),
        "resources_note": (f"These links come from a short hand-picked list. Each one was opened and checked on "
                           f"{resources.VERIFIED_ON}, but a person has not reviewed them yet. "
                           "Where nothing matched, you get a search term instead of a link."),
        "library_reviewed": all(r["reviewed"] for r in lib),
    }
