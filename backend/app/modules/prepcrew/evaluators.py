from app.core.jobs import fan_out

EVALUATORS: list[str] = []  # TODO: define evaluator names and rubrics


async def run_evaluator(name: str, transcript: str, probe_log: list[str]) -> dict:
    """TODO: core.ai.generate_json(...) grading the session for this evaluator;
    return a dict matching schemas.EvaluatorResult (without duration_ms)."""
    raise NotImplementedError


async def evaluate_session(transcript: str, probe_log: list[str]) -> list[dict]:
    """Run all evaluators at once (core.jobs.fan_out). Failed or timed-out ones are dropped, the rest kept."""
    outcomes = await fan_out({
        name: (lambda n=name: run_evaluator(n, transcript, probe_log)) for name in EVALUATORS
    })
    results = []
    for outcome in outcomes.values():
        if outcome["ok"]:
            results.append({**outcome["result"], "duration_ms": outcome["duration_ms"]})
    return results
