"""Real-model check that the patience meter notices when the candidate does not answer the question.
1. 14 question and answer pairs, labeled by me (not independent), through the assessor.
2. A short interview where the candidate keeps dodging, to see the meter climb and a strict interview end.
Run:  backend\\.venv\\Scripts\\python spikes\\e2e_nonanswer.py
Live Gemini from backend/.env, in-memory storage. Calls are spaced out, a burst gets rate limited."""
import asyncio
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import e2e_interview as base  # noqa: E402  (sets up paths, env and in-memory storage)

from fastapi.testclient import TestClient  # noqa: E402

from app.main import app  # noqa: E402
from app.modules.prepcrew import assessor  # noqa: E402

Q_CAP = "How did you pick the bulk capacitor value that fixed the brownout?"
Q_SCOPE = "What did you see on the scope when the board reset?"
Q_I2C = "How did you fix the I2C lockup on the weather station?"
# (question, answer, my label). "no" = ignored the question. "yes" = answered, even badly. "partly" = only part.
CASES = [
    (Q_CAP, "I used a 100 microfarad cap because the datasheet suggested it and it was what we had.", "yes"),
    (Q_CAP, "I mostly did the power stage.", "no"),
    (Q_CAP, "Um, not sure, idk.", "no"),
    (Q_CAP, "Honestly I'd rather talk about the firmware side of things.", "no"),
    (Q_CAP, "I don't know.", "no"),
    (Q_CAP, "Hm, about a hundred I think? Not totally sure why.", "yes"),
    (Q_SCOPE, "The five volt rail dipped to about four volts for a few hundred microseconds.", "yes"),
    (Q_SCOPE, "Which rail do you mean, the input or the regulated one?", "yes"),
    (Q_SCOPE, "It was a really interesting project and I learned a lot from my teammates.", "no"),
    (Q_SCOPE, "It dipped. I didn't write down how far.", "partly"),
    (Q_I2C, "I added a bus recovery routine that clocks SCL nine times, and a timeout in the driver.", "yes"),
    (Q_I2C, "We had pizza after the demo, it was great.", "no"),
    (Q_I2C, "Sorry, can you repeat the question?", "yes"),
    (Q_I2C, "Next question please.", "no"),
]


async def judge():
    agree = 0
    for q, a, label in CASES:
        got = await assessor.assess([], a, q)
        said = "no" if got.no_answer else "yes_or_partly"
        ok = (label == "no") == bool(got.no_answer)
        agree += ok
        print(json.dumps({"answer": a[:62], "my_label": label, "flagged_as_no_answer": bool(got.no_answer),
                          "agree": ok, "quote": got.no_answer and got.no_answer["evidence_quote"]}))
        await asyncio.sleep(1.5)
    print(f"\nagreement with my labels (no answer or not): {agree} of {len(CASES)} (my labels, not independent)\n")


def interview():
    client = TestClient(app)
    plan = client.post("/api/plans", json={"job_posting": base.POSTING, "resume": base.RESUME, "user_id": "e2e"}).json()
    sid = client.post("/api/sessions", json={"plan_id": plan["plan_id"], "user_id": "e2e", "consent": True}).json()["session_id"]
    print("plan degraded:", plan["degraded"], "| opening:", plan["questions"][0])
    for text in ["I mostly did the power stage.", "Um, not sure, idk.", "Honestly I'd rather talk about something else.", "Can we try again?"]:
        r = client.post(f"/api/sessions/{sid}/turns", json={"answer": text})
        if r.status_code != 200:
            print(f"  {text!r:50} -> refused: {r.json()['detail']}")
            break
        j = r.json()
        m = j["meter"] or {}
        print(f"  {text!r:50} -> score={m.get('score')} unanswered={m.get('unanswered')} level={m.get('level')} "
              f"source={j['source']} ended={j['ended_early']}")
        print(f"      interviewer: {j['next_question']}")
        time.sleep(1.5)


if __name__ == "__main__":
    asyncio.run(judge())
    interview()
