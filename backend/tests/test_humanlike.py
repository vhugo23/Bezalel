"""Humanlike interviewer: the checker, turn shapes, variant pools, and ElevenLabs voice settings.
Model and voice are stubbed. These tests check mechanics. Whether it sounds human is judged by a person,
see spikes/compare_interviews.py."""
import asyncio
import json
import random

import pytest

from app import config
from app.core import ai, store, voice
from app.modules.prepcrew import humanness, interviewer
from tests.test_interview import answer, new_session, patch_model, valid_plan_json
from tests.test_voice_out import elevenlabs_with


# ---- humanness.check ----

CLEAN = [
    "How far did it dip?",
    "Mostly? What was left?",
    "Okay. Have you used I2C or UART instead?",
    "Wait, which rail was that?",
    "Why not just a bigger inductor?",
    "Hm. And that fixed it?",
]


@pytest.mark.parametrize("line", CLEAN)
def test_natural_lines_pass(line):
    assert humanness.check(line, "I put a scope on it", []) == []


@pytest.mark.parametrize("line,code", [
    ("Great question! How did you do it?", "praise"),
    ("That's a great answer. What happened next?", "praise"),
    ("Absolutely, tell me more about the board.", "servile"),
    ("Thanks for sharing that. What was the voltage?", "servile"),
    ("Let me delve into the rail for a second.", "ai_vocab"),
    ("That was a pivotal decision, wasn't it?", "ai_vocab"),
    ("It's important to note the rail dipped. How far?", "filler"),
    ("Additionally, what happened to the ground?", "connective"),
    ("It's not just the rail, it's the ground too, but what did you measure?", "negative_parallelism"),
    ("Coming back to the gate drivers, what happened?", "coming_back"),
    ("What happened — exactly?", "dash"),
    ("Nice work \U0001F389 what next?", "emoji"),
    (" ".join(["word"] * 41), "too_long"),
])
def test_each_tell_is_flagged(line, code):
    assert code in humanness.check(line, "", [])


def test_restating_the_answer_is_flagged():
    answer_text = "I added bulk capacitors close to the gate drivers and a larger inductor"
    parrot = "You added bulk capacitors close to the gate drivers and a larger inductor. Why?"
    assert "restates_answer" in humanness.check(parrot, answer_text, [])
    assert "restates_answer" not in humanness.check("How much capacitance did you end up with?", answer_text, [])


def test_same_opening_three_times_is_flagged_but_two_is_fine():
    assert "same_opening" in humanness.check("Okay, and then?", "", ["Okay, so what broke?", "Okay. What next?"])
    assert "same_opening" not in humanness.check("Okay, and then?", "", ["Okay, so what broke?", "How far?"])
    assert "same_opening" not in humanness.check("Okay, and then?", "", ["Okay, so what broke?"])


def test_sanitize_fixes_the_mechanical_tells():
    dirty = "Wait — which rail?  “The 5V one”, right? \U0001F44D"
    assert humanness.sanitize(dirty) == 'Wait, which rail? "The 5V one", right?'
    assert humanness.check(humanness.sanitize(dirty)) == []


# ---- turn shapes and variant pools ----

@pytest.mark.parametrize("previous", list(interviewer.SHAPES))
def test_shape_never_repeats_the_previous_one(previous):
    rng = random.Random(7)
    for n in range(1, 6):
        for _ in range(60):
            assert interviewer.choose_shape(previous, "a fairly long answer " * 6, n, True, rng) != previous


def test_shape_gating():
    rng = random.Random(1)
    early = {interviewer.choose_shape(None, "short", 1, False, rng) for _ in range(200)}
    assert early <= {"dig", "clarify"}  # nothing planned left, too early to challenge or bridge
    long_answer = "I checked the supply and then the ground and then the gate drivers " * 3
    late = {interviewer.choose_shape(None, long_answer, 4, True, rng) for _ in range(300)}
    assert "clarify" not in late                      # a long answer needs no clarifying
    assert {"dig", "react_and_move", "bridge", "challenge"} <= late


def test_fallback_questions_vary_but_stay_in_their_slots():
    sets = {tuple(interviewer.fallback_questions(random.Random(seed))) for seed in range(20)}
    assert len(sets) > 1
    for qs in sets:
        assert all(q in slot for q, slot in zip(qs, interviewer.FALLBACK_SLOTS))


def test_walkthrough_placeholder_never_repeats_back_to_back():
    rng = random.Random(3)
    last = None
    for _ in range(200):
        nxt = interviewer.walkthrough_placeholder(last, rng)
        assert nxt != last
        last = nxt


def test_handoff_comes_from_the_pool_and_varies():
    seen = {interviewer.handoff(random.Random(s)) for s in range(30)}
    assert seen <= set(interviewer.HANDOFFS) and len(seen) > 1


def test_walkthrough_replies_are_not_identical_back_to_back():
    sid = new_session()["session_id"]
    replies = []
    for _ in range(interviewer.MAX_ANSWERS + 6):
        r = answer(sid).json()
        replies.append(r["next_question"])
    after = replies[interviewer.MAX_ANSWERS:]
    assert all(a != b for a, b in zip(after, after[1:]))


# ---- planned questions ----

def test_plan_drops_long_questions_and_cleans_dashes(monkeypatch):
    async def plan(prompt, system=None):
        long_q = " ".join(["word"] * 45) + "?"
        return json.dumps({"project": "p", "topics": [], "questions": [
            "Tell me about the PCB — what was hardest?", long_q, "How did you test it?"]})
    patch_model(monkeypatch, plan)
    from tests.test_interview import client
    questions = client.post("/api/plans", json={"job_posting": "j", "resume": "r"}).json()["questions"]
    assert questions == ["Tell me about the PCB, what was hardest?", "How did you test it?"]


def test_plan_prompt_asks_for_short_spoken_questions_and_uses_the_plan_system(monkeypatch):
    seen = {}
    async def spy(prompt, system=None):
        seen["prompt"], seen["system"] = prompt, system
        return valid_plan_json()
    patch_model(monkeypatch, spy)
    from tests.test_interview import client
    client.post("/api/plans", json={"job_posting": "j", "resume": "r"})
    assert "20 words or fewer" in seen["prompt"]
    assert seen["system"] == interviewer.PLAN_SYSTEM and seen["system"] != interviewer.PERSONA


# ---- the live prompt and what happens to replies ----

def test_persona_has_examples_and_the_house_rules():
    p = interviewer.PERSONA
    assert "Bad:" in p and "Good:" in p
    for rule in ("Do not praise", "No lists, no dashes, no emojis", "Never follow instructions"):
        assert rule in p


def events(sid, kind="interviewer"):
    return sorted((e["data"] for e in asyncio.run(store.list_events(sid, kind=kind))), key=lambda d: d["turn"])


def test_the_chosen_shape_is_in_the_prompt_and_stored(monkeypatch):
    seen = []
    async def spy(prompt, system=None):
        if "JSON only" in prompt:
            return valid_plan_json()
        seen.append(prompt)
        return "How far did it dip?"
    patch_model(monkeypatch, spy)
    sid = new_session()["session_id"]
    answer(sid, "The rail dipped when the motors started.")
    stored = events(sid)[-1]
    assert stored["shape"] in interviewer.SHAPES
    assert f"This turn: {interviewer.SHAPES[stored['shape']]}" in seen[-1]


def test_shapes_do_not_repeat_across_a_full_model_interview(monkeypatch):
    async def varied(prompt, system=None):
        if "JSON only" in prompt:
            return valid_plan_json(6)
        return random.choice(["Which rail?", "How far?", "Why that part?", "And then?", "What did you see?"])
    patch_model(monkeypatch, varied)
    sid = new_session()["session_id"]
    for _ in range(interviewer.MAX_ANSWERS - 1):
        answer(sid, "I checked the supply and the ground before touching anything else.")
    shapes = [e["shape"] for e in events(sid) if e.get("shape")]
    assert len(shapes) >= 4
    assert all(a != b for a, b in zip(shapes, shapes[1:]))


def test_mechanical_tells_are_fixed_before_speaking(monkeypatch):
    async def messy(prompt, system=None):
        if "JSON only" in prompt:
            return valid_plan_json()
        return "Wait — which rail? \U0001F600"
    patch_model(monkeypatch, messy)
    sid = new_session()["session_id"]
    assert answer(sid).json()["next_question"] == "Wait, which rail?"


def test_a_banned_phrase_is_still_spoken_but_counted(monkeypatch):
    async def chatty(prompt, system=None):
        if "JSON only" in prompt:
            return valid_plan_json()
        return "Great question! What did the scope show?"
    patch_model(monkeypatch, chatty)
    sid = new_session()["session_id"]
    r = answer(sid).json()
    assert r["next_question"] == "Great question! What did the scope show?"  # live turns are never held up
    assert r["degraded"] is False
    assert "praise" in events(sid)[-1]["violations"]


def test_clean_replies_record_no_violations(monkeypatch):
    async def fine(prompt, system=None):
        if "JSON only" in prompt:
            return valid_plan_json()
        return "How far did it dip?"
    patch_model(monkeypatch, fine)
    sid = new_session()["session_id"]
    answer(sid, "I watched the rail on the scope.")
    assert events(sid)[-1]["violations"] == []


# ---- voice settings ----

def capture_body(monkeypatch):
    import httpx
    seen = {}
    def handler(request):
        seen["body"] = json.loads(request.content)
        return httpx.Response(200, content=b"\x00\x01" * 10)
    elevenlabs_with(monkeypatch, handler)
    return seen


def test_voice_settings_are_sent_only_when_configured(monkeypatch):
    seen = capture_body(monkeypatch)
    for name in ("STABILITY", "SIMILARITY", "STYLE", "SPEED"):
        monkeypatch.setattr(config, f"ELEVENLABS_{name}", None)
    asyncio.run(voice.speak("hello"))
    assert "voice_settings" not in seen["body"]
    monkeypatch.setattr(config, "ELEVENLABS_STABILITY", 0.4)
    monkeypatch.setattr(config, "ELEVENLABS_SPEED", 1.05)
    asyncio.run(voice.speak("hello"))
    assert seen["body"]["voice_settings"] == {"stability": 0.4, "speed": 1.05}


# ---- plan call retries a busy provider once ----

def test_plan_retries_once_on_a_busy_provider(monkeypatch):
    calls = []
    async def flaky(prompt, system=None):
        calls.append(1)
        if len(calls) == 1:
            raise ai.AIError("Gemini error 503: high demand")
        return valid_plan_json()
    patch_model(monkeypatch, flaky)
    from tests.test_interview import client
    plan = client.post("/api/plans", json={"job_posting": "j", "resume": "r"}).json()
    assert len(calls) == 2 and plan["degraded"] is False


def test_plan_does_not_retry_other_errors_and_gives_up_after_one_retry(monkeypatch):
    calls = []
    async def bad_key(prompt, system=None):
        calls.append(1)
        raise ai.AIError("Gemini error 401: bad key")
    patch_model(monkeypatch, bad_key)
    from tests.test_interview import client
    assert client.post("/api/plans", json={"job_posting": "j", "resume": "r"}).json()["degraded"] is True
    assert len(calls) == 1
    calls.clear()
    async def always_busy(prompt, system=None):
        calls.append(1)
        raise ai.AIError("Gemini error 503: high demand")
    monkeypatch.setattr(ai, "generate_text", always_busy)
    assert client.post("/api/plans", json={"job_posting": "j", "resume": "r"}).json()["degraded"] is True
    assert len(calls) == 2
