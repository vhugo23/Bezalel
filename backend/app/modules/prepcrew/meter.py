"""The hidden "patience meter". A gap on a skill the job posting REQUIRES pushes the interviewer hard toward ending
the interview. A gap on a PREFERRED skill pushes only a little. Pure functions, no model and no storage.

The weights and thresholds in config.py are starting values chosen by hand. They are not validated.
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


def new_state() -> dict:
    """items: worst result per requirement. raw: what items add up to. score: the running total after the per-answer cap."""
    return {"items": {}, "raw": 0.0, "score": 0.0}


def apply(state: dict, findings: list[dict], requirements: list[dict]) -> dict:
    """Fold one answer's findings into the state. Returns a new state."""
    items = update(state["items"], findings)
    raw = score(items, requirements)
    gained = min(max(0.0, raw - state["raw"]), config.MAX_PENALTY_PER_ANSWER)
    return {"items": items, "raw": raw, "score": round(state["score"] + gained, 6)}


def snapshot(state: dict, requirements: list[dict], strict: bool) -> dict | None:
    """None when there are no requirements: the meter is off and the interview never ends early."""
    if not requirements:
        return None
    return {"score": state["score"], "threshold": config.FAIL_THRESHOLD, "level": level(state["score"], strict)}
