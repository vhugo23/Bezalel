"""Spike: Gemini Flash streaming over REST. Lists models from the API and picks a flash model that
supports streamGenerateContent instead of trusting a hard-coded id. Measures time to first token, 3 runs.
Run:  python spikes/spike_gemini.py"""
import json
import os
import re
import time

import httpx

from _common import key, report

BASE = "https://generativelanguage.googleapis.com/v1beta"
PROMPT = ("You are a hardware interviewer. The candidate said: 'I checked the resistor first.' "
          "Reply with one short follow-up question.")


def pick_model(headers) -> tuple[str, list[str]]:
    forced = os.getenv("INTERVIEWER_MODEL", "").strip()
    r = httpx.get(f"{BASE}/models", headers=headers, params={"pageSize": 200}, timeout=20)
    r.raise_for_status()
    # The list only shows generateContent for every model, never streamGenerateContent,
    # and streaming uses the same models. Plain "gemini-<version>-flash" ids only.
    names = [m["name"].removeprefix("models/") for m in r.json().get("models", [])
             if "generateContent" in m.get("supportedGenerationMethods", [])]
    flash = sorted((n for n in names if re.fullmatch(r"gemini-[\d.]+-flash", n)),
                   key=lambda n: [int(p) for p in n.split("-")[1].split(".")])
    if forced:
        return forced, flash
    if not flash:
        raise RuntimeError("no plain flash model found for this key")
    return flash[-1], flash


def main() -> None:
    headers = {"x-goog-api-key": key("GEMINI_API_KEY")}
    try:
        model, flash = pick_model(headers)
    except Exception as e:
        report("gemini", "FAIL", stage="list_models", error=f"{type(e).__name__}: {e}")
        return
    first_token_ms, total_ms, replies = [], [], []
    for i in range(3):
        t0 = time.perf_counter()
        first, text = None, ""
        try:
            with httpx.stream(
                "POST", f"{BASE}/models/{model}:streamGenerateContent", params={"alt": "sse"},
                headers=headers, json={"contents": [{"parts": [{"text": PROMPT}]}]}, timeout=60,
            ) as r:
                if r.status_code != 200:
                    report("gemini", "FAIL", model=model, status=r.status_code, body=r.read().decode(errors="replace")[:300])
                    return
                for line in r.iter_lines():
                    if not line.startswith("data:"):
                        continue
                    parts = json.loads(line[5:]).get("candidates", [{}])[0].get("content", {}).get("parts", [])
                    piece = "".join(p.get("text", "") for p in parts)
                    if piece and first is None:
                        first = (time.perf_counter() - t0) * 1000
                    text += piece
        except Exception as e:
            report("gemini", "FAIL", model=model, run=i, error=f"{type(e).__name__}: {e}")
            return
        first_token_ms.append(round(first, 1) if first else None)
        total_ms.append(round((time.perf_counter() - t0) * 1000, 1))
        replies.append(text.strip())
    report("gemini", "PASS" if all(first_token_ms) else "FAIL", model=model, flash_models_seen=flash,
           first_token_ms=first_token_ms, total_ms=total_ms, replies=replies)


if __name__ == "__main__":
    main()
