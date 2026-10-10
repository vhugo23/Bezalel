"""Evaluator pipeline (contracts/api.md, "Evaluator pipeline contract").

One call per answer per rubric, run through core.jobs.fan_out with a concurrency limit from config.
Only rubrics with status "reviewed" are used in a real run. Events are published for the SSE stream.
"""
import json
import time
from pathlib import Path
from typing import Awaitable, Callable

from app import config
from app.core.jobs import fan_out

RUBRICS_DIR = Path(__file__).resolve().parent / "data" / "rubrics"

Publish = Callable[[str, dict], Awaitable[None]]


class EvidenceMismatch(ValueError):
    pass


def load_rubrics(only_reviewed: bool = True) -> list[dict]:
    rubrics = [json.loads(p.read_text(encoding="utf-8")) for p in sorted(RUBRICS_DIR.glob("*.json"))]
    return [r for r in rubrics if r.get("status") == "reviewed"] if only_reviewed else rubrics


def check_evidence(output: dict, transcript: str, score_max: int) -> list[str]:
    """Reference rules from contracts/check_contracts.py. Empty list = pass, anything else = reject."""
    problems = []
    for c in output["criteria"]:
        q, (s, e) = c["evidence_quote"], c["evidence_span"]
        if c["score"] > score_max:
            problems.append(f"{c['id']}: score {c['score']} above score_max {score_max}")
        if q == "":
            if c["score"] != 0 or [s, e] != [0, 0]:
                problems.append(f"{c['id']}: empty quote needs score 0 and span [0, 0]")
        elif transcript[s:e] != q:
            problems.append(f"{c['id']}: quote does not match transcript[{s}:{e}]")
    return problems


async def run_evaluator(rubric: dict, answer: dict, transcript: str, probe_log: list[dict]) -> dict:
    """TODO: call the evaluator model (config.EVALUATOR_PROVIDER / EVALUATOR_MODEL) with the transcript,
    the rubric, and the probe log for criteria with uses_probe_log. Validate with schemas.EvaluatorOutput
    (core.ai.generate_json retries once), then check_evidence; on a mismatch retry once, then set
    needs_review and raise EvidenceMismatch."""
    raise NotImplementedError("evaluator model call not implemented yet")


def _reason(error: str | None) -> str:
    # contract reasons: timeout | bad_json | quote_mismatch
    if error and error.startswith("TimeoutError"):
        return "timeout"
    if error and error.startswith("EvidenceMismatch"):
        return "quote_mismatch"
    return "bad_json"


async def grade_session(session_id: str, answers: list[dict], transcript: str,
                        probe_log: list[dict], publish: Publish) -> dict:
    """Grades every answer against every reviewed rubric. Returns {"results": [...], "total_ms": int}."""
    start = time.perf_counter()
    rubrics = load_rubrics()
    jobs, meta = {}, {}
    for a in answers:
        for r in rubrics:
            key = f"{a['answer_id']}:{r['rubric_id']}"
            meta[key] = (a["answer_id"], r["rubric_id"])
            jobs[key] = (lambda r=r, a=a: run_evaluator(r, a, transcript, probe_log))
            await publish("evaluator_started", {"answer_id": a["answer_id"], "rubric_id": r["rubric_id"]})

    outcomes = await fan_out(jobs, timeout=config.EVALUATOR_TIMEOUT_SECONDS, limit=config.EVALUATOR_CONCURRENCY)

    results = []
    for key, out in outcomes.items():
        answer_id, rubric_id = meta[key]
        if out["ok"]:
            result = out["result"]
            results.append(result)
            await publish("evaluator_done", {"answer_id": answer_id, "rubric_id": rubric_id,
                                             "duration_ms": out["duration_ms"],
                                             "needs_review": bool(result.get("needs_review"))})
        else:
            await publish("evaluator_failed", {"answer_id": answer_id, "rubric_id": rubric_id,
                                               "reason": _reason(out["error"])})

    total_ms = int((time.perf_counter() - start) * 1000)
    await publish("grading_complete", {"session_id": session_id, "total_ms": total_ms})
    return {"results": results, "total_ms": total_ms}
