"""The hidden "patience meter". A gap on a skill the job posting REQUIRES pushes the interviewer hard toward ending
the interview. A gap on a PREFERRED skill pushes only a little. Pure functions, no model and no storage.

The weights and thresholds in config.py are starting values chosen by hand. They are not validated.
Two things move the meter: a stated gap on a skill from the posting, and an answer that ignores the question.
Each requirement counts once, at its worst result, so repeating "I don't know SPI" cannot stack. There is no recovery.
One answer can add at most MAX_PENALTY_PER_ANSWER, so ending an interview always takes at least two answers."""
from app import config

_RANK = {"knows": 0, "partial": 1, "unknown": 2}


def penalty(level: str, result: str) -> float:
    return {
        ("required", "unknown"): config.PENALTY_REQUIRED_UNKNOWN,
        ("required", "partial"): config.PENALTY_REQUIRED_PARTIAL,
        ("preferred", "unknown"): config.PENALTY_PREFERRED_UNKNOWN,
        ("preferred", "partial"): config.PENALTY_PREFERRED_PARTIAL,
    }.get((level, result), 0.0)


def update(items: dict[str, str], findings: list[dict]) -> dict[str, str]:
    """Merge new findings into {requirement_id: worst result so far}. Returns a new dict."""
    merged = dict(items)
    for f in findings:
        old = merged.get(f["requirement_id"])
        if old is None or _RANK[f["result"]] > _RANK[old]:
            merged[f["requirement_id"]] = f["result"]
    return merged


def score(items: dict[str, str], requirements: list[dict]) -> float:
    level_of = {r["id"]: r["level"] for r in requirements}
    return round(sum(penalty(level_of[rid], result) for rid, result in items.items() if rid in level_of), 6)


def level(value: float, strict: bool) -> str:
    """ok, wrapping_up (steer toward closing), or ended. A non-strict session never reaches ended."""
    if value >= config.FAIL_THRESHOLD:
        return "ended" if strict else "wrapping_up"
    return "wrapping_up" if value >= config.WRAP_UP_AT else "ok"


def counts_as_no_answer(findings: list[dict], no_answer: dict | None) -> bool:
    """An answer that admits a gap on a skill ("I've never used SPI") answered the question, honestly. The gap is
    already penalized, so it is not also counted as a non-answer."""
    return no_answer is not None and not any(f["result"] in ("unknown", "partial") for f in findings)


def new_state() -> dict:
    """items: worst result per requirement. unanswered: questions the candidate ignored. raw: what those add up to.
    score: the running total after the per-answer cap."""
    return {"items": {}, "unanswered": 0, "raw": 0.0, "score": 0.0}


def apply(state: dict, findings: list[dict], requirements: list[dict], no_answer: dict | None = None) -> dict:
    """Fold one answer into the state. Returns a new state."""
    items = update(state["items"], findings)
    unanswered = state.get("unanswered", 0) + (1 if counts_as_no_answer(findings, no_answer) else 0)
    raw = round(score(items, requirements) + unanswered * config.PENALTY_NON_ANSWER, 6)
    gained = min(max(0.0, raw - state["raw"]), config.MAX_PENALTY_PER_ANSWER)
    return {"items": items, "unanswered": unanswered, "raw": raw, "score": round(state["score"] + gained, 6)}


def snapshot(state: dict, strict: bool) -> dict:
    return {"score": state["score"], "threshold": config.FAIL_THRESHOLD, "level": level(state["score"], strict),
            "unanswered": state.get("unanswered", 0)}
