"""End to end check of the live interview: real /ws/voice route, real Gemini (from backend/.env), optional real TTS.
Sends scripted answers to a realistic resume and posting, prints every interviewer line with its source and
measured timings, so a human can judge whether the follow-ups actually react to the answers.
Run:  backend\\.venv\\Scripts\\python spikes\\e2e_interview.py          (set E2E_NO_TTS=1 to skip audio)
Uses in-memory storage, never the database. The posting and resume below are made-up test text."""
import json
import os
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "backend"))
os.chdir(ROOT / "backend")
if not os.getenv("E2E_NO_TTS"):
    os.environ.setdefault("VOICE_PROVIDER", "elevenlabs")
    os.environ.setdefault("ELEVENLABS_MODEL", "eleven_flash_v2_5")

from fastapi.testclient import TestClient  # noqa: E402

from app import config  # noqa: E402
from app.main import app  # noqa: E402

config.DATABASE_URL = ""  # in-memory storage only

POSTING = """Hardware Engineering Intern, Motor Controls
Join our drives team building compact brushless motor controllers for robotics. You will bring up new PCB
revisions, debug power and gate-drive problems on the bench, and write test firmware in C for STM32 parts.
Requirements: coursework in circuits and digital logic; hands-on experience with oscilloscopes and
multimeters; familiarity with I2C, SPI and UART; experience reading schematics and datasheets; C or C++.
Nice to have: KiCad or Altium, buck converters, MOSFET gate drivers, EMI basics, version control for hardware.
You will work with two senior engineers and present your findings at weekly design reviews."""

RESUME = """Alex Rivera, Computer Engineering, third year.
Projects
- Three-axis motor controller PCB (team of 3): designed a 4-layer board in KiCad with an STM32G4, three
  half-bridge gate drivers and a 12V to 5V buck converter. Brought it up and found a brownout that reset the
  MCU when the motors started; traced it with a scope to the 5V rail dipping under load and added bulk
  capacitance and a larger inductor.
- Weather station: ESP32 with an I2C humidity sensor and an SPI flash logger, firmware in C. Fixed a bus
  lockup by adding pull-up resistors and a timeout in the driver.
- Digital logic lab: built a traffic light FSM on an FPGA board in Verilog, tested with a self-checking bench.
Experience: lab assistant for intro circuits, helped students debug breadboards (floating grounds, swapped LED polarity).
Skills: KiCad, C, Python, oscilloscope, logic analyzer, soldering SMD parts."""

ANSWERS = [
    "So the motor controller was my main project. The board kept resetting whenever the motors spun up, so I put the scope on the five volt rail and saw it dip below the brownout threshold for a few hundred microseconds.",
    "I first checked the input supply to make sure the twelve volts was stable, then moved to the buck converter output. The dip lined up with the motor current spike, so I suspected the inductor was saturating.",
    "I added bulk capacitors close to the gate drivers and swapped to an inductor with a higher saturation current rating. After that the rail only dipped about fifty millivolts, which the MCU tolerated.",
    "On the weather station the I2C bus locked up randomly. I used the logic analyzer and saw SDA stuck low after a failed read, so I added a bus recovery routine that clocks SCL nine times and a timeout.",
    "Honestly I'd probably simulate the buck converter first next time instead of finding the problem on the bench. I didn't model the inductor current at all.",
]


def recv(ws):
    m = ws.receive()
    return m["bytes"] if m.get("bytes") is not None else json.loads(m["text"])


def main() -> None:
    client = TestClient(app)
    plan = client.post("/api/plans", json={"job_posting": POSTING, "resume": RESUME, "user_id": "e2e"}).json()
    s = client.post("/api/sessions", json={"plan_id": plan["plan_id"], "user_id": "e2e", "consent": True}).json()
    sid = s["session_id"]
    print(json.dumps({"llm": config.LLM_PROVIDER, "model": config.GEMINI_MODEL, "voice": config.VOICE_PROVIDER,
                      "plan_degraded": plan["degraded"], "project": plan["project"], "topics": plan["topics"],
                      "planned_questions": plan["questions"], "opening": s["opening"]}, indent=2))
    turns = []
    with client.websocket_connect(f"/ws/voice/{sid}") as ws:
        recv(ws), recv(ws)  # state, opening text
        for i, answer in enumerate(ANSWERS, 1):
            ws.send_json({"type": "text_answer", "text": answer})
            t0, frames, said, timing, src_msgs = time.perf_counter(), 0, None, {}, []
            while True:
                m = recv(ws)
                if isinstance(m, bytes):
                    frames += 1
                    continue
                if m["type"] == "interviewer_text":
                    said = m["text"]
                elif m["type"] == "timing":
                    timing[m["stage"]] = m["ms"]
                elif m["type"] == "error":
                    src_msgs.append(m["code"])
                elif m["type"] == "tts_done":
                    break
            rec = client.get(f"/api/metrics/{sid}").json()
            turns.append({"turn": i, "candidate": answer[:70] + "...", "interviewer": said, "timings_ms": timing,
                          "audio_frames": frames, "errors": src_msgs})
    state = client.get(f"/api/sessions/{sid}/report").json()
    for t in turns:
        print(json.dumps(t, indent=2))
    totals = [t["timings_ms"].get("turn_total") for t in turns]
    print(json.dumps({"turn_total_ms_per_turn": totals,
                      "tts_first_audio_ms_per_turn": [t["timings_ms"].get("tts_first_audio") for t in turns],
                      "fallback_or_error_turns": [t["turn"] for t in turns if t["errors"]],
                      "report_status": state["status"]}, indent=2))


if __name__ == "__main__":
    main()
