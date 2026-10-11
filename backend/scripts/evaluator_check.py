"""Grades the contract's example answer with the real Gemini model, 3 times, and reports what came back.

    cd backend
    python scripts/evaluator_check.py

Uses the example rubric, answer and probe log in contracts/examples/ (the rubric is a DRAFT, used here only to
exercise the code; it is never used in a real session). No database. Costs about 3 to 6 Gemini calls.
Prints scores, whether every quote really appears in the answer, needs_review, and measured time per call.
These are a few samples on one answer, not an accuracy claim.
"""
import asyncio
import json
import os
import sys
import time
from pathlib import Path

BACKEND = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND))
os.chdir(BACKEND)

from app import config  # noqa: E402  (loads backend/.env)
from app.modules.prepcrew import evaluators  # noqa: E402

EX = BACKEND.parent / "contracts" / "examples"
RUNS = 3


async def main():
    config.DATABASE_URL = ""
    provider = config.EVALUATOR_PROVIDER or config.LLM_PROVIDER
    model = config.EVALUATOR_MODEL or config.GEMINI_MODEL
    if provider != "gemini":
        sys.exit(f"provider is '{provider}'. Set LLM_PROVIDER=gemini (or EVALUATOR_PROVIDER=gemini) in backend/.env")
    print(f"grading with {provider} / {model}\n")
    rubric = json.loads((EX / "debug_process_rubric.json").read_text(encoding="utf-8"))
    transcript = (EX / "transcript.txt").read_text(encoding="utf-8")
    text = " ".join(line.split(":", 1)[1].strip() for line in transcript.splitlines() if line.startswith("Candidate:"))
    probes = json.loads((EX / "probe_events.json").read_text(encoding="utf-8"))
    answer = {"answer_id": "check", "text": text}
    ok = 0
    for i in range(1, RUNS + 1):
        start = time.perf_counter()
        try:
            out = await asyncio.wait_for(evaluators.run_evaluator(rubric, answer, "", probes),
                                         timeout=config.EVALUATOR_TIMEOUT_SECONDS)
        except Exception as e:
            print(f"run {i}: FAILED after {time.perf_counter() - start:.1f}s -> {type(e).__name__}: {str(e)[:160]}\n")
            continue
        ms = (time.perf_counter() - start) * 1000
        quotes_ok = all(text[c["evidence_span"][0]:c["evidence_span"][1]] == c["evidence_quote"] for c in out["criteria"])
        ok += (not out["needs_review"]) and quotes_ok
        print(f"run {i}: {ms:.0f} ms   needs_review={out['needs_review']}   every quote found in the answer={quotes_ok}"
              f"   confidence={out['confidence']}")
        for c in out["criteria"]:
            q = f'"{c["evidence_quote"][:70]}"' if c["evidence_quote"] else "(no quote)"
            print(f"   {c['id']:<28} {c['score']}/{rubric['score_max']}  {q}")
        print(f"   skill flags: {out['skill_flags']}\n")
    print(f"{ok} of {RUNS} runs passed every check")


if __name__ == "__main__":
    asyncio.run(main())
