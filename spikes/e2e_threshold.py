"""Real-model check of the patience meter (live Gemini from backend/.env, in-memory storage, no TTS).
1. Reads the requirements from the posting and prints them with their levels.
2. Runs 12 hand-written answers through the assessor and compares with MY labels (not an independent check).
3. Plays three short interviews: a missed required skill, a missed preferred skill, two missed required skills.
Run:  backend\\.venv\\Scripts\\python spikes\\e2e_threshold.py
Posting and resume are made-up test text. The weights are starting values, nothing here validates them."""
import asyncio
import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import e2e_interview as base  # noqa: E402  (sets up paths, env and in-memory storage)

from fastapi.testclient import TestClient  # noqa: E402

from app import config  # noqa: E402
from app.main import app  # noqa: E402
from app.modules.prepcrew import assessor  # noqa: E402

# (answer, {skill keyword: expected result}). An empty dict means the answer touches no listed skill: expect no finding.
CASES = [
    ("Honestly I've never used SPI, I only did I2C.", {"spi": "unknown", "i2c": "knows"}),
    ("I haven't touched UART before, that's new to me.", {"uart": "unknown"}),
    ("I've only used the oscilloscope once or twice, so I'm not great with it.", {"oscilloscope": "partial"}),
    ("I've never used Altium, I only know KiCad.", {"kicad": "knows"}),  # "KiCad or Altium": either one meets it
    ("EMI is something I've only read about, I haven't dealt with it on a real board.", {"emi": "partial"}),
    ("I've never heard of MOSFET gate drivers, sorry.", {"gate": "unknown"}),
    ("I used I2C on the weather station and fixed a lockup with a bus recovery routine.", {"i2c": "knows"}),
    ("I designed the board in KiCad and used SPI to talk to the flash chip.", {"kicad": "knows", "spi": "knows"}),
    ("The hardest part was the brownout, I traced it with a scope on the 5V rail.", {}),
    ("I don't remember the exact part number of the inductor, but I sized it from the datasheet.", {}),
    ("I wrote the firmware in C and used a logic analyzer to check the UART output.", {"uart": "knows"}),
    ("We split the work three ways and I handled the power stage.", {}),
    ("I've never used Altium but KiCad is what I use for everything.", {"kicad": "knows"}),
    ("I know I2C and UART fine, it's only SPI I haven't tried.", {"spi": "unknown", "i2c": "knows", "uart": "knows"}),
    ("Buck converters are new to me, I only copied a reference design.", {"buck": "partial"}),
]


def find(reqs: list[dict], keyword: str):
    return next((r for r in reqs if keyword in r["text"].lower()), None)


async def judge(reqs):
    rows, agree, total = [], 0, 0
    for text, expected in CASES:
        got = await assessor.assess(reqs, text)
        by_text = {r["id"]: r["text"].lower() for r in reqs}
        seen = {by_text[f["requirement_id"]]: f["result"] for f in got}
        line = {"answer": text[:70], "expected": expected, "got": seen}
        verdicts = []
        for keyword, want in expected.items():
            req = find(reqs, keyword)
            if req is None:
                verdicts.append("skill not extracted")
                continue
            total += 1
            ok = seen.get(req["text"].lower()) == want
            agree += ok
            verdicts.append("ok" if ok else f"DIFFERENT (wanted {want})")
        if not expected:  # a gap is "unknown" or "partial". A correct "knows" on an unrelated skill is fine.
            total += 1
            ok = not any(v in ("unknown", "partial") for v in seen.values())
            agree += ok
            verdicts.append("ok" if ok else "FLAGGED A GAP THAT IS NOT ONE")
        line["verdict"] = verdicts
        rows.append(line)
    return rows, agree, total


def play(client, plan_id, answers, strict=True):
    sid = client.post("/api/sessions", json={"plan_id": plan_id, "user_id": "e2e", "consent": True, "strict": strict}).json()["session_id"]
    out = []
    for text in answers:
        r = client.post(f"/api/sessions/{sid}/turns", json={"answer": text})
        if r.status_code != 200:
            out.append({"answer": text[:60], "refused": r.json()["detail"]})
            break
        j = r.json()
        out.append({"answer": text[:60], "reply": j["next_question"], "source": j["source"], "meter": j["meter"],
                    "ended_early": j["ended_early"]})
    return out


def main() -> None:
    client = TestClient(app)
    plan = client.post("/api/plans", json={"job_posting": base.POSTING, "resume": base.RESUME, "user_id": "e2e"}).json()
    print(json.dumps({"model": config.GEMINI_MODEL, "plan_degraded": plan["degraded"],
                      "requirements": [(r["text"], r["level"]) for r in plan["requirements"]]}, indent=1))
    if not plan["requirements"]:
        raise SystemExit("no requirements extracted, the meter would be off")
    rows, agree, total = asyncio.run(judge(plan["requirements"]))
    for row in rows:
        print(json.dumps(row))
    print(f"\nagreement with my labels: {agree} of {total} checks (my labels, not independent)\n")

    neutral = "The board kept resetting under load, so I put a scope on the 5V rail and found it dipping."
    scenarios = {
        "missed required skill": [neutral, "Honestly I've never used SPI.", "I mostly did the power stage."],
        "missed preferred skill": [neutral, "I've never worked with MOSFET gate drivers.", "I mostly did the power stage."],
        "missed two required skills": [neutral, "Honestly I've never used SPI.", "And I've never used I2C either."],
    }
    for name, answers in scenarios.items():
        print(f"== {name}")
        for step in play(client, plan["plan_id"], answers):
            print(json.dumps(step))


if __name__ == "__main__":
    main()
