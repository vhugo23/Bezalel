"""Compare saved interview runs (spikes/_runs/<tag>.json from e2e_interview.py) and build a blind reading file.
Run:  backend\\.venv\\Scripts\\python spikes\\compare_interviews.py before after
      (groups every spikes/_runs/<prefix>_*.json. Needs the runs to exist first.)
Metrics are mechanical. Whether a reply sounds human is for a person to judge, so this also writes
spikes/_runs/blind_read.md (A/B in random order, no labels) and blind_key.json (which side was which)."""
import json
import random
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "backend"))

from app.modules.prepcrew import humanness  # noqa: E402

RUNS = Path(__file__).parent / "_runs"


def first_sentence(text: str) -> str:
    for i, ch in enumerate(text):
        if ch in ".?!" and i > 0:
            return text[: i + 1]
    return text


def load(prefix: str) -> list[dict]:
    return [json.loads(p.read_text(encoding="utf-8")) for p in sorted(RUNS.glob(f"{prefix}_*.json"))]


def metrics(runs: list[dict]) -> dict:
    replies, violation_codes, parrots, long_replies, opener_repeats, exact_repeats = [], Counter(), 0, 0, 0, 0
    for run in runs:
        said = [t["interviewer"] for t in run["turns"]]
        replies += said
        seen = set()
        for i, t in enumerate(run["turns"]):
            codes = humanness.check(t["interviewer"], t["candidate"], said[:i])
            violation_codes.update(codes)
            parrots += "restates_answer" in codes
            long_replies += len(humanness.words(t["interviewer"])) > 25
            norm = " ".join(humanness.words(t["interviewer"]))
            exact_repeats += norm in seen
            seen.add(norm)
        openers = Counter(humanness.first_word(r) for r in said)
        opener_repeats += sum(c - 1 for c in openers.values() if c > 1)
    n = len(replies) or 1
    return {
        "runs": len(runs), "replies": len(replies),
        "plan_degraded_runs": sum(1 for r in runs if r["planned_questions"][:1] and False),  # filled by caller
        "avg_words": round(sum(len(humanness.words(r)) for r in replies) / n, 1),
        "replies_over_25_words": long_replies,
        "repeated_openers": opener_repeats, "verbatim_repeats": exact_repeats,
        "restates_answer": parrots,
        "first_sentence_restates": sum(1 for run in runs for t in run["turns"]
                                       if humanness.restated_fraction(first_sentence(t["interviewer"]), t["candidate"]) >= 0.5),
        "replies_with_any_violation": sum(1 for run in runs for i, t in enumerate(run["turns"])
                                          if humanness.check(t["interviewer"], t["candidate"],
                                                             [x["interviewer"] for x in run["turns"][:i]])),
        "violation_codes": dict(violation_codes),
    }


def blind_file(before: list[dict], after: list[dict]) -> None:
    rng = random.Random()
    key, lines = [], ["# Blind read", "",
                      "For each candidate answer, two interviewer replies are shown in random order. "
                      "Write which one sounds more like a real person interviewing, A or B, and anything that felt off.", ""]
    n = 0
    for b, a in zip(before, after):
        for tb, ta in zip(b["turns"], a["turns"]):
            n += 1
            sides = [("before", tb["interviewer"]), ("after", ta["interviewer"])]
            rng.shuffle(sides)
            key.append({"item": n, "A": sides[0][0], "B": sides[1][0]})
            lines += [f"## {n}", "", f"Candidate: {tb['candidate']}", "", f"A: {sides[0][1]}", "", f"B: {sides[1][1]}", "",
                      "Which sounds more human, A or B? ____", ""]
    (RUNS / "blind_read.md").write_text("\n".join(lines), encoding="utf-8")
    (RUNS / "blind_key.json").write_text(json.dumps(key, indent=2), encoding="utf-8")
    print(f"wrote {RUNS / 'blind_read.md'} ({n} items) and blind_key.json (do not open the key until you have answered)")


def main() -> None:
    names = sys.argv[1:] or ["before", "after"]
    groups = {name: load(name) for name in names}
    for name, runs in groups.items():
        if not runs:
            raise SystemExit(f"no runs found for '{name}' in {RUNS}")
        m = metrics(runs)
        m["plan_degraded_runs"] = sum(1 for r in runs if r.get("plan_degraded"))
        print(f"\n== {name} ==")
        for k, v in m.items():
            print(f"  {k}: {v}")
        print("  sample replies:")
        for t in runs[0]["turns"]:
            print(f"    - {t['interviewer']}")
    if len(names) == 2:
        blind_file(groups[names[0]], groups[names[1]])


if __name__ == "__main__":
    main()
