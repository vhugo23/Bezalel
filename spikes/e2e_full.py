"""The whole product loop over real sockets against the RUNNING backend (port 8000), with every real provider:
real Gemini for the plan, replies and checks, real ElevenLabs for the opening question, the replies and the CANDIDATE'S
voice (generated, then sent back as push-to-talk audio), real speech to text, the patience meter, the debrief, the
CORS check the browser needs, grading, metrics, and deletion. Prints PASS or FAIL per check with measured values.
Start the backend first (see CONTEXT.md). The backend must run with DATABASE_URL blank (in-memory).
Run:  backend\\.venv\\Scripts\\python spikes\\e2e_full.py"""
import asyncio
import json
import os
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "backend"))
sys.path.insert(0, str(Path(__file__).parent))
os.chdir(ROOT / "backend")
os.environ["VOICE_PROVIDER"] = "elevenlabs"
os.environ.setdefault("ELEVENLABS_MODEL", "eleven_flash_v2_5")

from websockets.sync.client import connect  # noqa: E402

from app import config  # noqa: E402
from app.core import voice  # noqa: E402
import e2e_interview as base  # noqa: E402

config.DATABASE_URL = ""
HTTP, WS = "http://127.0.0.1:8000", "ws://127.0.0.1:8000"
results: list[tuple[str, bool, str]] = []


def check(name: str, ok: bool, detail: str = "") -> bool:
    results.append((name, bool(ok), detail))
    print(f"{'PASS' if ok else 'FAIL'}  {name}" + (f"  [{detail}]" if detail else ""))
    return bool(ok)


def _body(raw: bytes):
    try:
        return json.loads(raw) if raw else None
    except ValueError:
        return raw.decode(errors="replace")  # an HTML page such as /docs


def call(method: str, path: str, body=None, headers=None):
    req = urllib.request.Request(HTTP + path, data=json.dumps(body).encode() if body is not None else None,
                                 method=method, headers={"Content-Type": "application/json", **(headers or {})})
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            return r.status, _body(r.read()), dict(r.headers)
    except urllib.error.HTTPError as e:
        raw = e.read()
        return e.code, _body(raw), dict(e.headers)


def collect(ws, until="tts_done", timeout=60):
    """Read messages until one of this type. Returns (json messages, audio frame count, audio bytes)."""
    msgs, frames, size = [], 0, 0
    deadline = time.time() + timeout
    while time.time() < deadline:
        m = ws.recv(timeout=timeout)
        if isinstance(m, bytes):
            frames += 1
            size += len(m)
            continue
        j = json.loads(m)
        msgs.append(j)
        if j["type"] == until:
            return msgs, frames, size
    raise TimeoutError(f"no {until} within {timeout}s")


def speak_answer(ws, text: str):
    """Candidate speech: ElevenLabs makes the audio, we send it as 100 ms frames like a browser would."""
    pcm = asyncio.run(voice.speak(text))
    ws.send(json.dumps({"type": "barge_in"}))
    for i in range(0, len(pcm), 3200):
        ws.send(pcm[i:i + 3200])
    ws.send(json.dumps({"type": "speech_end"}))
    return len(pcm) / 32000


def types(msgs):
    return [m["type"] for m in msgs]


def main() -> int:
    status, _, _ = call("GET", "/docs")
    if status != 200:
        print("backend is not running on port 8000, start it first (see CONTEXT.md)")
        return 2

    # 1. plan and session
    t = time.perf_counter()
    status, plan, _ = call("POST", "/api/plans", {"job_posting": base.POSTING, "resume": base.RESUME, "user_id": "full-e2e"})
    plan_s = time.perf_counter() - t
    check("plan from real Gemini, not the generic fallback", status == 200 and not plan["degraded"] and plan["questions"],
          f"{plan_s:.1f}s, {len(plan['requirements'])} skills: {sum(r['level'] == 'required' for r in plan['requirements'])} required")
    status, sess, _ = call("POST", "/api/sessions", {"plan_id": plan["plan_id"], "user_id": "full-e2e", "consent": True})
    sid = sess["session_id"]
    check("session starts in interview with an opening question", status == 200 and sess["state"] == "interview" and sess["opening"],
          sess["opening"][:70])
    status, _, _ = call("POST", "/api/sessions", {"plan_id": plan["plan_id"], "user_id": "x", "consent": False})
    check("a session without consent is refused", status == 400)

    with connect(f"{WS}/ws/voice/{sid}", max_size=None) as ws:
        first, _, _ = collect(ws, "interviewer_text", 10)
        check("socket sends state then the opening line", types(first) == ["state", "interviewer_text"])

        # 2. opening question spoken
        ws.send(json.dumps({"type": "start"}))
        msgs, frames, size = collect(ws)
        check("opening question is spoken (audio frames, whole 16-bit samples)", frames > 0 and size % 2 == 0,
              f"{frames} frames, {size / 32000:.1f}s of audio")

        # 3. a SPOKEN answer: voice in, speech to text, reply, voice out
        said1 = "I put a scope on the five volt rail and saw it dipping when the motors started."
        secs = speak_answer(ws, said1)
        msgs, frames, size = collect(ws)
        tt = {m["stage"]: m["ms"] for m in msgs if m["type"] == "timing"}
        heard = next((m["text"] for m in msgs if m["type"] == "transcript_final"), "")
        reply = next((m["text"] for m in msgs if m["type"] == "interviewer_text"), "")
        meter1 = next((m for m in msgs if m["type"] == "meter"), None)
        import difflib, re
        words = lambda t: re.sub(r"[^a-z0-9' ]", " ", t.lower().replace("-", " ")).split()
        ratio = difflib.SequenceMatcher(None, words(said1), words(heard)).ratio()
        diff = [f"{tag} {' '.join(words(said1)[i1:i2])!r}->{' '.join(words(heard)[j1:j2])!r}"
                for tag, i1, i2, j1, j2 in difflib.SequenceMatcher(None, words(said1), words(heard)).get_opcodes() if tag != "equal"]
        check("spoken answer is transcribed (at least 85 percent of words match)", ratio >= 0.85,
              f"{ratio:.0%} of words match, differences: {diff or 'none'}; heard: {heard!r}")
        check("interviewer replies with text and then audio", bool(reply) and frames > 0, f"{reply[:80]!r}, {frames} frames")
        check("timing for every stage was measured", {"stt", "turn_total", "tts_first_audio"} <= set(tt),
              ", ".join(f"{k} {v:.0f} ms" for k, v in tt.items()))
        check("meter is on and nothing was penalized", meter1 and meter1["score"] == 0 and meter1["checked"] is True, str(meter1))
        time.sleep(2)

        # 4. a TYPED answer admitting a required skill gap
        ws.send(json.dumps({"type": "text_answer", "text": "Honestly I've never used SPI."}))
        msgs, frames, _ = collect(ws)
        m2 = next((m for m in msgs if m["type"] == "meter"), None)
        check("a missed required skill moves the meter and starts the wrap-up",
              m2 and m2["score"] == config.PENALTY_REQUIRED_UNKNOWN and m2["level"] == "wrapping_up" and m2["checked"],
              str(m2))
        time.sleep(2)

        # 5. a SPOKEN second gap ends the interview
        said3 = "And I've never used I2C either."
        speak_answer(ws, said3)
        msgs, frames, _ = collect(ws)
        m3 = next((m for m in msgs if m["type"] == "meter"), None)
        closing = next((m["text"] for m in msgs if m["type"] == "interviewer_text"), "")
        check("two missed required skills end the interview", m3 and m3["level"] == "ended" and m3["score"] >= 1.0, str(m3))
        check("closing line, debrief state and debrief_ready arrive in order, and the closing is spoken",
              types(msgs).index("state") < types(msgs).index("debrief_ready") and frames > 0, f"{closing!r}")
        time.sleep(1)

        # 6. after the end, the socket stays up and refuses more answers
        ws.send(json.dumps({"type": "text_answer", "text": "wait, can I try again?"}))
        err = json.loads(ws.recv(timeout=10))
        check("further answers are refused without closing the socket", err["type"] == "error" and err["code"] == "bad_answer")

    # 7. debrief, fetched the way the browser does (cross-origin)
    status, d, headers = call("GET", f"/api/sessions/{sid}/debrief", headers={"Origin": "http://localhost:5173"})
    allow = {k.lower(): v for k, v in headers.items()}.get("access-control-allow-origin")
    check("debrief loads from the browser's origin (CORS)", status == 200 and allow in ("http://localhost:5173", "*"), f"allow-origin: {allow}")
    titles = [g["title"] for g in d["gaps"]]
    check("debrief lists both missed skills", {"SPI", "I2C"} <= set(titles), str(titles))
    everything = " ".join([said1, "Honestly I've never used SPI.", said3]).lower().replace("'", "")
    quotes_ok = all(" ".join(g["evidence_quote"].lower().replace("'", "").replace(".", "").split()) in everything.replace(".", "")
                    for g in d["gaps"] if g["evidence_quote"])
    check("every quote in the debrief is something the candidate really said", quotes_ok)
    links = [r["url"] for g in d["gaps"] for r in g["resources"]]
    check("each gap has a link or a search term, and no link is invented",
          all(g["resources"] or g["search_hint"] or g["tip"] for g in d["gaps"]) and
          all(u in {r["url"] for r in json.loads((ROOT / "backend/app/modules/prepcrew/data/resources.json").read_text(encoding="utf-8"))} for u in links),
          f"{len(links)} links")
    check("debrief says its links are unreviewed", d["library_reviewed"] is False and d["status"] == "ended_early")

    # 8. grading, report, metrics, deletion
    status, g, _ = call("POST", f"/api/sessions/{sid}/end")
    check("end of session returns right away with status grading", status == 200 and g["status"] == "grading")
    time.sleep(1)
    status, _, _ = call("GET", f"/api/sessions/{sid}/report")
    check("report endpoint still works after an early end", status == 200)
    status, mt, _ = call("GET", f"/api/metrics/{sid}")
    check("metrics report measured values only", status == 200 and mt["stt_ms"] and mt["tts_first_audio_ms"] and mt["turn_total_ms"],
          f"stt {mt['stt_ms']:.0f} ms, first audio {mt['tts_first_audio_ms']:.0f} ms, turn {mt['turn_total_ms']:.0f} ms (medians)")
    status, _, _ = call("DELETE", f"/api/sessions/{sid}")
    check("tester session can be deleted", status == 200)
    status, _, _ = call("GET", f"/api/sessions/{sid}/debrief")
    check("a deleted session has no debrief", status == 404)

    failed = [n for n, ok, _ in results if not ok]
    print(f"\n{len(results) - len(failed)} of {len(results)} checks passed" + (f"; FAILED: {failed}" if failed else ""))
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
