"""Validate the example files against the schemas and show the evidence-quote check.
Run from the contracts folder:  python check_contracts.py
Needs:  pip install jsonschema
The check_evidence function is the reference for the second-pass quote verifier."""
import json
import sys
from pathlib import Path

from jsonschema import Draft202012Validator

HERE = Path(__file__).parent


def load(p):
    return json.loads((HERE / p).read_text(encoding="utf-8"))


def schema_errors(schema_file: str, doc) -> list[str]:
    v = Draft202012Validator(load(schema_file))
    return [f"{'/'.join(map(str, e.path)) or '<root>'}: {e.message}" for e in v.iter_errors(doc)]


def check_evidence(output: dict, transcript: str, score_max: int) -> list[str]:
    """Return a list of problems. Empty list means the result passes. Any problem means reject."""
    problems = []
    for c in output["criteria"]:
        q, (s, e) = c["evidence_quote"], c["evidence_span"]
        seqs = c.get("evidence_probe_seqs") or []
        if c["score"] > score_max:
            problems.append(f"{c['id']}: score {c['score']} above score_max {score_max}")
        if q == "":
            if (c["score"] != 0 and not seqs) or [s, e] != [0, 0]:
                problems.append(f"{c['id']}: empty quote needs score 0 and span [0, 0], unless probe steps are cited")
        elif transcript[s:e] != q:
            problems.append(f"{c['id']}: quote does not match transcript[{s}:{e}]")
    return problems


def main() -> int:
    transcript = (HERE / "examples/transcript.txt").read_text(encoding="utf-8")
    failures = []
    for schema, ex in [
        ("netlist.schema.json", "examples/led_reversed.json"),
        ("rubric.schema.json", "examples/debug_process_rubric.json"),
        ("evaluator_output.schema.json", "examples/evaluator_output.json"),
    ]:
        failures += [f"{ex}: {m}" for m in schema_errors(schema, load(ex))]
    for i, ev in enumerate(load("examples/probe_events.json")):
        failures += [f"probe_events[{i}]: {m}" for m in schema_errors("probe_event.schema.json", ev)]

    out = load("examples/evaluator_output.json")
    failures += check_evidence(out, transcript, load("examples/debug_process_rubric.json")["score_max"])

    # Things that must be rejected
    bad_quote = json.loads(json.dumps(out))
    bad_quote["criteria"][0]["evidence_quote"] = "I would check the fuse first."
    if not check_evidence(bad_quote, transcript, 2):
        failures.append("bad quote was accepted")
    bad_schema = json.loads(json.dumps(out))
    del bad_schema["confidence"]
    if not schema_errors("evaluator_output.schema.json", bad_schema):
        failures.append("missing confidence was accepted")
    no_fault = json.loads(json.dumps(load("examples/led_reversed.json")))
    no_fault["fault"] = None
    if not schema_errors("netlist.schema.json", no_fault):
        failures.append("debug scenario without a fault was accepted")
    bad_probe = {**load("examples/probe_events.json")[0], "value": None}
    if not schema_errors("probe_event.schema.json", bad_probe):
        failures.append("probe_voltage without a value was accepted")

    for f in failures:
        print("FAIL", f)
    print("ok" if not failures else f"{len(failures)} problem(s)")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
