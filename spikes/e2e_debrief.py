"""Plays a short interview against live Gemini (backend/.env, in-memory storage) until the patience meter ends it,
then prints the debrief the endpoint returns. Shows exactly what a frontend receives.
Run:  backend\\.venv\\Scripts\\python spikes\\e2e_debrief.py"""
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import e2e_interview as base  # noqa: E402  (sets up paths, env and in-memory storage)

from fastapi.testclient import TestClient  # noqa: E402

from app.main import app  # noqa: E402

ANSWERS = [
    "The board kept resetting under load, so I scoped the 5V rail and found it dipping.",
    "Honestly I've never used SPI, I only did I2C on the weather station.",
    "I mostly did the power stage.",
    "And I've never worked with MOSFET gate drivers either, and I haven't used UART.",
    "I'd rather talk about something else.",
]


def main() -> None:
    client = TestClient(app)
    plan = client.post("/api/plans", json={"job_posting": base.POSTING, "resume": base.RESUME, "user_id": "e2e"}).json()
    sid = client.post("/api/sessions", json={"plan_id": plan["plan_id"], "user_id": "e2e", "consent": True}).json()["session_id"]
    for text in ANSWERS:
        r = client.post(f"/api/sessions/{sid}/turns", json={"answer": text})
        if r.status_code != 200:
            break
        j = r.json()
        m = j["meter"] or {}
        print(f"{text[:58]!r:62} score={m.get('score')} unanswered={m.get('unanswered')} checked={m.get('checked')} "
              f"level={m.get('level')} ended={j['ended_early']}")
        if j["ended_early"]:
            print("   interviewer:", j["next_question"])
            break
        time.sleep(1.5)
    d = client.get(f"/api/sessions/{sid}/debrief").json()
    print("\nSUMMARY:", d["summary"], "\nstatus:", d["status"], "| meter:", d["meter"])
    for g in d["gaps"]:
        print(f"\n- [{g['kind']}] {g['title']}  ({g['level']}, {g['result']})  quote: {g['evidence_quote']!r}")
        for r in g["resources"]:
            print(f"    link: {r['title']}  {r['url']}")
        if g["search_hint"]:
            print("    ", g["search_hint"])
        if g["tip"]:
            print("    tip:", g["tip"])
    print("\nstrengths:", [(s["title"], s["evidence_quote"]) for s in d["strengths"]])
    print("\nnote:", d["resources_note"])


if __name__ == "__main__":
    main()
