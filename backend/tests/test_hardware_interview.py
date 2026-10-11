"""hardware_interview: the storage-free entry point for the lane 1 interviewer. These tests try to break it (bad model
JSON, timeouts, a skipped question, a strict interview reaching its end, a state that went through JSON, a state that
was damaged) and compare it with the legacy service.handle_answer on the same inputs. The model is stubbed, so no
keys and no network are needed."""
import asyncio
import copy
import json
import random
import zlib

import pytest

from app import config
from app.core import ai, store
from app.modules.prepcrew import assessor, debrief, interviewer, service
from app.modules.prepcrew import hardware_interview as hw
from tests.test_interview import ALL_FALLBACKS, patch_model
from tests.test_threshold import PLAN, REQS, finding

SPI = "Honestly I have never used SPI."
I2C = "I've never touched I2C either."
KICAD = "I haven't used KiCad before."
DODGE = "I mostly did the power stage."
UM = "Um, not sure, idk."
PLAIN = "I measured it with a scope."
FINDINGS = {
    SPI: [finding("r1", "unknown", "never used SPI")],
    I2C: [finding("r2", "unknown", "never touched I2C")],
    KICAD: [finding("r3", "unknown", "haven't used KiCad")],
}
ANSWERED = {DODGE: {"result": "no", "evidence_quote": "mostly did the power stage"},
            UM: {"result": "no", "evidence_quote": "not sure"}}


class Model:
    """A stub for ai.generate_text. The plan, the gap check and the live reply can each be made to misbehave:
    "ok", "junk" (not JSON), "error" (a non-transient provider error), "slow" (past any timeout) or "empty".
    The live reply is a digest of its prompt, so two runs give the same reply only if they sent the same prompt."""

    def __init__(self, findings=None, answered=None, plan=PLAN, planner="ok", assessor="ok", live="ok"):
        self.findings, self.answered, self.plan = findings or {}, answered or {}, plan
        self.mode = {"plan": planner, "assessor": assessor, "live": live}
        self.plan_prompts, self.assessor_prompts, self.turn_prompts = [], [], []

    async def __call__(self, prompt, system=None):
        if '"findings"' in prompt:
            kind, log = "assessor", self.assessor_prompts
        elif '"project"' in prompt:
            kind, log = "plan", self.plan_prompts
        else:
            kind, log = "live", self.turn_prompts
        log.append(prompt)
        mode = self.mode[kind]
        if mode == "slow":
            await asyncio.sleep(5)
        if mode == "error":
            raise ai.AIError("Gemini error 401: bad key")
        if mode == "empty":
            return ""
        if mode == "junk":
            return "this is { not json"
        if kind == "assessor":
            said = prompt.split("<answer>\n", 1)[1].split("\n</answer>", 1)[0]
            out = {"findings": self.findings.get(said, [])}
            if said in self.answered:
                out["answered"] = self.answered[said]
            return json.dumps(out)
        if kind == "plan":
            return json.dumps(self.plan)
        return f"Which {zlib.crc32(prompt.encode()) % 100000} part?"


def run(coro):
    return asyncio.run(coro)


def begin(monkeypatch, model, strict=True):
    patch_model(monkeypatch, model)
    return run(hw.start("posting", "resume", strict=strict))


def step(state, text):
    return run(hw.answer(state, text))


def tight(monkeypatch):
    """Short time limits, so a "slow" stub times out in a blink."""
    for name in ("TASK_TIMEOUT_SECONDS", "LIVE_TURN_TIMEOUT_SECONDS", "ASSESSOR_TIMEOUT_SECONDS"):
        monkeypatch.setattr(config, name, 0.1)


def seeded(monkeypatch, n):
    monkeypatch.setattr(interviewer, "_rng", random.Random(n))


# ---- start ----

def test_start_gives_the_plan_the_opening_and_a_state_that_survives_json(monkeypatch):
    r = begin(monkeypatch, Model())
    s = r["state"]
    assert r["opening"] == PLAN["questions"][0] == s["last_interviewer_text"]
    assert r["plan"]["requirements"] == REQS and r["degraded"] is False
    assert (s["phase"], s["turn"], s["strict"]) == ("interview", 0, True)
    assert s["turns"] == [{"role": "interviewer", "text": r["opening"], "turn": 0, "shape": None}]
    assert json.loads(json.dumps(r)) == r  # every value is a plain JSON type, nothing turns into a list or a string


@pytest.mark.parametrize("planner", ["junk", "error", "slow", "empty"])
def test_start_degrades_to_generic_questions_when_the_plan_call_fails(monkeypatch, planner):
    tight(monkeypatch)
    r = begin(monkeypatch, Model(planner=planner))
    assert r["degraded"] is True and r["plan"]["requirements"] == [] and r["plan"]["topics"] == []
    assert r["opening"] in ALL_FALLBACKS and len(r["plan"]["questions"]) == 5


def test_start_degrades_when_the_plan_has_no_usable_question(monkeypatch):
    too_long = dict(PLAN, questions=["word " * 40])
    r = begin(monkeypatch, Model(plan=too_long))
    assert r["degraded"] is True and r["opening"] in ALL_FALLBACKS


def test_a_degraded_plan_still_runs_and_a_gap_on_an_unknown_skill_is_not_counted(monkeypatch):
    r = begin(monkeypatch, Model(FINDINGS, planner="junk"))
    t = step(r["state"], SPI)  # the model claims a gap on r1, but this plan has no skills
    assert t["meter"]["score"] == 0 and t["findings"] == [] and t["reply"]


# ---- answer: the model misbehaves ----

@pytest.mark.parametrize("mode", ["junk", "error", "slow"])
def test_a_failed_gap_check_costs_nothing_and_says_so(monkeypatch, mode):
    tight(monkeypatch)
    state = begin(monkeypatch, Model(FINDINGS, assessor=mode))["state"]
    for _ in range(4):  # four admitted gaps would end a strict interview if they counted
        t = step(state, SPI)
        state = t["state"]
    assert t["meter"]["score"] == 0 and t["meter"]["checked"] is False and t["findings"] == []
    assert t["ended_early"] is False and t["phase"] == "interview"
    assert t["source"] == "model" and t["degraded"] is False  # the reply was fine, only the check failed


@pytest.mark.parametrize("mode", ["slow", "error", "empty"])
def test_a_failed_reply_asks_the_planned_question_and_the_gap_still_counts(monkeypatch, mode):
    tight(monkeypatch)
    state = begin(monkeypatch, Model(FINDINGS, live=mode))["state"]
    t = step(state, SPI)
    assert t["source"] == "fallback" and t["degraded"] is True and t["reply"] == PLAN["questions"][1]
    assert t["state"]["degraded_turns"] == 1
    assert t["meter"]["score"] == config.PENALTY_REQUIRED_UNKNOWN and t["meter"]["checked"] is True


def test_with_every_model_call_failing_the_planned_questions_come_in_order_and_no_score_appears(monkeypatch):
    tight(monkeypatch)
    state = begin(monkeypatch, Model(FINDINGS, answered=ANSWERED, assessor="junk", live="error"))["state"]
    asked = [state["last_interviewer_text"]]
    for _ in range(5):
        t = step(state, SPI)
        state = t["state"]
        asked.append(t["reply"])
        assert t["source"] == "fallback" and t["meter"]["score"] == 0 and t["meter"]["unanswered"] == 0
    assert asked == PLAN["questions"][:6]
    last = step(state, DODGE)  # the sixth answer uses the plan up
    assert last["done"] is True and last["phase"] == "walkthrough" and last["reply"] in interviewer.HANDOFFS
    assert last["meter"]["score"] == 0 and last["ended_early"] is False
    assert last["state"]["degraded_turns"] == 5


async def boom(*args, **kwargs):
    raise RuntimeError("a bug, not a model error")


def test_a_bug_in_the_reply_degrades_to_the_planned_question_and_the_gap_still_counts(monkeypatch):
    state = begin(monkeypatch, Model(FINDINGS))["state"]
    monkeypatch.setattr(interviewer, "next_question", boom)
    t = step(state, SPI)
    assert t["source"] == "fallback" and t["degraded"] is True and t["reply"] == PLAN["questions"][1]
    assert t["meter"]["score"] == config.PENALTY_REQUIRED_UNKNOWN


def test_a_bug_in_the_gap_check_means_nothing_is_counted(monkeypatch):
    state = begin(monkeypatch, Model(FINDINGS))["state"]
    monkeypatch.setattr(assessor, "assess", boom)
    t = step(state, SPI)
    assert t["meter"]["score"] == 0 and t["meter"]["checked"] is False and t["source"] == "model"


# ---- answer: the meter ----

def test_admitting_a_gap_on_a_required_skill_moves_the_meter_and_the_next_line_wraps_up(monkeypatch):
    model = Model(FINDINGS)
    state = begin(monkeypatch, model)["state"]
    t = step(state, SPI)
    assert t["meter"] == {"score": config.PENALTY_REQUIRED_UNKNOWN, "threshold": config.FAIL_THRESHOLD,
                          "level": "wrapping_up", "unanswered": 0, "checked": True}
    assert t["findings"] == [finding("r1", "unknown", "never used SPI")]
    assert t["state"]["meter_state"]["items"] == {"r1": "unknown"}
    assert t["state"]["meter_findings"] == [{**finding("r1", "unknown", "never used SPI"), "turn": 1}]
    assert t["ended_early"] is False and t["done"] is False
    step(t["state"], PLAIN)
    assert interviewer.WRAP_UP_NOTE in model.turn_prompts[-1]
    assert interviewer.WRAP_UP_NOTE not in model.turn_prompts[0]


def test_a_gap_on_a_preferred_skill_barely_moves_it_and_adds_no_pressure(monkeypatch):
    model = Model(FINDINGS)
    t = step(begin(monkeypatch, model)["state"], KICAD)
    assert t["meter"]["score"] == config.PENALTY_PREFERRED_UNKNOWN and t["meter"]["level"] == "ok"
    step(t["state"], PLAIN)
    assert all(interviewer.WRAP_UP_NOTE not in p for p in model.turn_prompts)


def test_a_made_up_quote_costs_the_candidate_nothing(monkeypatch):
    said = "I know SPI and I2C well."
    liar = {said: [finding("r1", "unknown", "I have no idea about SPI"), finding("r2", "unknown", "I cannot do I2C")]}
    t = step(begin(monkeypatch, Model(liar))["state"], said)
    assert t["meter"]["score"] == 0 and t["findings"] == [] and t["ended_early"] is False


def test_ignoring_the_question_counts_every_time_and_three_end_a_strict_interview(monkeypatch):
    model = Model(answered=ANSWERED)
    state = begin(monkeypatch, model)["state"]
    opening = state["last_interviewer_text"]
    one = step(state, DODGE)
    assert f"<question>\n{opening}\n</question>" in model.assessor_prompts[0]
    assert one["meter"]["score"] == config.PENALTY_NON_ANSWER and one["meter"]["unanswered"] == 1
    assert one["state"]["meter_findings"] == [{"kind": "no_answer", "turn": 1, "question": opening,
                                               "evidence_quote": "mostly did the power stage"}]
    two = step(one["state"], UM)
    assert two["meter"]["level"] == "wrapping_up" and two["ended_early"] is False
    three = step(two["state"], DODGE)
    assert three["ended_early"] is True and three["reply"] in interviewer.CLOSINGS
    assert [g["result"] for g in three["state"]["end_gaps"]] == ["no_answer"] * 3
    assert three["state"]["end_gaps"][0]["text"].startswith("did not answer: ")


@pytest.mark.parametrize("verdict", [
    {"result": "yes", "evidence_quote": "mostly did the power stage"},
    {"result": "partly", "evidence_quote": "mostly did the power stage"},
    {"result": "no", "evidence_quote": "something the candidate never said"},
    {"result": "no", "evidence_quote": ""},
])
def test_only_a_verified_no_counts_as_a_skipped_question(monkeypatch, verdict):
    t = step(begin(monkeypatch, Model(answered={DODGE: verdict}))["state"], DODGE)
    assert t["meter"]["score"] == 0 and t["meter"]["unanswered"] == 0


def test_a_stated_gap_is_not_also_counted_as_a_skipped_question(monkeypatch):
    said = {SPI: {"result": "no", "evidence_quote": "never used SPI"}}
    t = step(begin(monkeypatch, Model(FINDINGS, answered=said))["state"], SPI)
    assert t["meter"]["score"] == config.PENALTY_REQUIRED_UNKNOWN and t["meter"]["unanswered"] == 0


def test_the_same_gap_repeated_does_not_stack(monkeypatch):
    state = begin(monkeypatch, Model(FINDINGS))["state"]
    for _ in range(3):
        t = step(state, SPI)
        state = t["state"]
    assert t["meter"]["score"] == config.PENALTY_REQUIRED_UNKNOWN and t["ended_early"] is False


def test_without_skills_only_skipped_questions_count(monkeypatch):
    plan = {k: v for k, v in PLAN.items() if k != "requirements"}
    state = begin(monkeypatch, Model(FINDINGS, ANSWERED, plan=plan))["state"]
    assert step(state, SPI)["meter"]["score"] == 0
    assert step(state, DODGE)["meter"]["score"] == config.PENALTY_NON_ANSWER


# ---- answer: the end ----

def test_a_strict_interview_ends_after_two_required_gaps_and_refuses_more_answers(monkeypatch):
    state = begin(monkeypatch, Model(FINDINGS))["state"]
    t1 = step(state, SPI)
    t2 = step(t1["state"], I2C)
    assert t2["done"] and t2["ended_early"] and t2["phase"] == "debrief" and t2["source"] == "scripted"
    assert t2["reply"] in interviewer.CLOSINGS and t2["meter"]["level"] == "ended" and t2["shape"] is None
    s = t2["state"]
    assert s["ended_early"] is True and s["end_reason"] == "requirement_gaps"
    assert {(g["requirement_id"], g["level"], g["evidence_quote"]) for g in s["end_gaps"]} == {
        ("r1", "required", "never used SPI"), ("r2", "required", "never touched I2C")}
    before = copy.deepcopy(s)
    with pytest.raises(hw.InterviewEnded):
        step(s, "wait, can I try again?")
    assert s == before
    d = hw.debrief(s)
    assert d["status"] == "ended_early" and d["end_reason"] == "requirement_gaps"
    assert [(g["requirement_id"], g["evidence_quote"]) for g in d["gaps"]] == [
        ("r1", "never used SPI"), ("r2", "never touched I2C")]
    json.dumps(d)


def test_a_non_strict_interview_never_ends_but_still_wraps_up(monkeypatch):
    state = begin(monkeypatch, Model(FINDINGS), strict=False)["state"]
    step_one = step(state, SPI)
    t = step(step_one["state"], I2C)
    assert t["ended_early"] is False and t["meter"]["level"] == "wrapping_up" and t["phase"] == "interview"
    assert step(t["state"], "still here")["reply"]


def test_one_answer_admitting_every_gap_cannot_end_an_interview(monkeypatch):
    everything = "I have never used SPI, never touched I2C, never opened KiCad and never seen Altium."
    allgaps = {everything: [finding("r1", "unknown", "never used SPI"), finding("r2", "unknown", "never touched I2C"),
                            finding("r3", "unknown", "never opened KiCad"), finding("r4", "unknown", "never seen Altium")]}
    t = step(begin(monkeypatch, Model(allgaps))["state"], everything)
    assert t["meter"]["score"] == config.MAX_PENALTY_PER_ANSWER and t["ended_early"] is False
    assert len(t["findings"]) == 4


def test_when_the_plan_is_used_up_the_interview_hands_off_then_answers_get_the_placeholder(monkeypatch):
    state = begin(monkeypatch, Model())["state"]
    for i in range(interviewer.MAX_ANSWERS):
        t = step(state, PLAIN)
        state = t["state"]
        assert t["done"] is (i == interviewer.MAX_ANSWERS - 1)
    assert t["phase"] == "walkthrough" and t["reply"] in interviewer.HANDOFFS and t["source"] == "scripted"
    assert t["ended_early"] is False
    kept = copy.deepcopy(state["turns"])
    later = step(state, "I'd probe the node after the resistor.")
    assert later["done"] is False and later["source"] == "scripted" and later["meter"] is None
    assert later["reply"] in interviewer.WALKTHROUGH_PLACEHOLDERS and later["reply"] != state["last_interviewer_text"]
    assert later["phase"] == "walkthrough" and later["turn"] == interviewer.MAX_ANSWERS + 1
    assert later["state"]["turns"] == kept  # nothing grows once the interview part is over
    assert hw.debrief(later["state"])["status"] == "interview_finished"


def test_on_the_fake_provider_there_is_no_meter_and_the_plan_is_generic():
    r = run(hw.start("posting", "resume"))
    assert r["degraded"] is True and r["opening"] in ALL_FALLBACKS
    state, asked = r["state"], [r["opening"]]
    questions = r["plan"]["questions"]
    for i in range(1, len(questions)):
        t = step(state, PLAIN)
        state = t["state"]
        assert t["source"] == "fake" and t["meter"] is None and t["reply"] == questions[i] and not t["done"]
    last = step(state, PLAIN)  # the plan is used up
    assert last["done"] is True and last["phase"] == "walkthrough" and last["reply"] in interviewer.HANDOFFS
    d = hw.debrief(last["state"])
    assert d["meter"] is None and d["gaps"] == [] and d["status"] == "interview_finished"


# ---- bad input and damaged state ----

@pytest.mark.parametrize("text", ["", "   ", "\n\t", None, "x" * (hw.MAX_ANSWER_CHARS + 1)])
def test_an_empty_or_oversized_answer_is_refused_before_any_model_call(monkeypatch, text):
    model = Model(FINDINGS)
    state = begin(monkeypatch, model)["state"]
    before = copy.deepcopy(state)
    with pytest.raises(hw.BadAnswer):
        step(state, text)
    assert state == before and model.turn_prompts == [] and model.assessor_prompts == []


def test_an_answer_of_exactly_the_limit_is_accepted_and_trimmed(monkeypatch):
    state = begin(monkeypatch, Model())["state"]
    t = step(state, "  " + "x" * hw.MAX_ANSWER_CHARS + "  ")
    assert t["state"]["turns"][-2] == {"role": "candidate", "text": "x" * hw.MAX_ANSWER_CHARS, "turn": 1, "shape": None}


@pytest.mark.parametrize("damage", [
    lambda s: s.pop("plan"), lambda s: s.pop("meter_state"), lambda s: s.pop("turns"),
    lambda s: s.update(version=2), lambda s: s.update(phase="done"),
    lambda s: s.update(turn=-1), lambda s: s.update(turn="1"), lambda s: s.update(turn=True),
    lambda s: s.update(strict="yes"), lambda s: s.update(turns="none"),
    lambda s: s["meter_state"]["items"].update(r1="maybe"),
    lambda s: s["turns"].append({"role": "bot", "text": "x"}),
    lambda s: s["turns"].append({"role": "candidate"}),
    lambda s: s["plan"].update(questions="Q0?"), lambda s: s["plan"].update(questions=[1, 2]),
])
def test_a_damaged_state_is_refused_before_anything_runs(monkeypatch, damage):
    model = Model(FINDINGS)
    state = begin(monkeypatch, model)["state"]
    damage(state)
    with pytest.raises(hw.InvalidState):
        step(state, SPI)
    with pytest.raises(hw.InvalidState):
        hw.debrief(state)
    assert model.turn_prompts == [] and model.assessor_prompts == []


@pytest.mark.parametrize("junk", [None, [], "state", 7, {}, {"version": 1}])
def test_something_that_is_not_a_state_is_refused(junk):
    with pytest.raises(hw.InvalidState):
        step(junk, SPI)
    with pytest.raises(hw.InvalidState):
        hw.debrief(junk)


def test_answer_does_not_change_the_state_it_is_given(monkeypatch):
    state = begin(monkeypatch, Model(FINDINGS))["state"]
    before = copy.deepcopy(state)
    t = step(state, SPI)
    assert state == before and t["state"] is not state and t["state"]["plan"] is not state["plan"]
    again = step(state, SPI)  # the same stale state again: same turn number, so a caller can spot the clash
    assert again["turn"] == t["turn"] == 1


def test_two_answers_on_one_state_do_not_see_each_other(monkeypatch):
    state = begin(monkeypatch, Model(FINDINGS))["state"]

    async def both():
        return await asyncio.gather(hw.answer(state, SPI), hw.answer(state, KICAD))
    a, b = run(both())
    assert a["turn"] == b["turn"] == 1
    assert a["state"]["meter_state"]["items"] == {"r1": "unknown"} and b["state"]["meter_state"]["items"] == {"r3": "unknown"}


def test_state_through_json_at_every_step_gives_the_same_interview(monkeypatch):
    said = [SPI, PLAIN, I2C]

    def play(roundtrip):
        state = begin(monkeypatch, Model(FINDINGS))["state"]
        out = []
        for i, text in enumerate(said):
            seeded(monkeypatch, i)
            t = step(state, text)
            json.dumps(t)  # the whole result is plain JSON, not only the state
            out.append({k: v for k, v in t.items() if k != "state"})
            state = json.loads(json.dumps(t["state"])) if roundtrip else t["state"]
        return out, state
    straight, loaded = play(False), play(True)
    assert straight == loaded
    assert loaded[1]["phase"] == "debrief"  # it did reach the end, so the round trip covered the closing too
    assert json.loads(json.dumps(loaded[1])) == loaded[1]


def test_nothing_is_stored_and_the_limit_matches_the_legacy_path(monkeypatch):
    state = begin(monkeypatch, Model(FINDINGS))["state"]
    state = step(step(state, SPI)["state"], I2C)["state"]
    hw.debrief(state)
    assert not store._records and not store._events
    assert hw.MAX_ANSWER_CHARS == service.MAX_ANSWER_CHARS


def test_the_end_gap_list_matches_the_legacy_helper():
    items = {"r1": "unknown", "r2": "partial", "r3": "knows", "r9": "unknown"}
    findings = [finding("r1", "unknown", "never used SPI"), finding("r2", "partial", "a little I2C"),
                {"kind": "no_answer", "turn": 2, "question": "Which rail?", "evidence_quote": "idk"}]
    assert hw._end_gaps(REQS, items, findings) == service._gap_list(REQS, items, findings)


# ---- the same answers through the legacy path ----

CASES = {
    "two required gaps end it": (dict(findings=FINDINGS), [SPI, I2C, PLAIN], True),
    "three skipped questions end it": (dict(answered=ANSWERED), [DODGE, UM, DODGE, PLAIN], True),
    "a stated gap and a preferred gap": (dict(findings=FINDINGS, answered=ANSWERED), [KICAD, SPI, DODGE], True),
    "plan used up, then the placeholder": (dict(), [PLAIN] * 7, True),
    "non strict": (dict(findings=FINDINGS), [SPI, I2C, KICAD, PLAIN], False),
    "gap check returns junk": (dict(findings=FINDINGS, assessor="junk"), [SPI, I2C], True),
    "gap check times out": (dict(findings=FINDINGS, assessor="slow"), [SPI, PLAIN], True),
    "live reply times out": (dict(findings=FINDINGS, live="slow"), [SPI, I2C, PLAIN], True),
    "live reply errors": (dict(findings=FINDINGS, live="error"), [SPI, PLAIN], True),
    "plan call returns junk": (dict(findings=FINDINGS, planner="junk"), [SPI, PLAIN, DODGE], True),
    "fake provider": (None, [PLAIN] * 6, True),
}


def run_legacy(monkeypatch, said, strict):
    store._records.clear()
    store._events.clear()

    async def go():
        seeded(monkeypatch, 100)
        plan = await service.create_plan("posting", "resume", None)
        sid = (await service.create_session(plan["plan_id"], "u", True, strict=strict))["id"]
        steps = []
        for i, text in enumerate(said):
            seeded(monkeypatch, 101 + i)
            try:
                steps.append(await service.handle_answer(sid, text))
            except service.BadRequest:
                steps.append("refused")
        data = (await service.get_session(sid))["data"]
        return plan, steps, data, await service._interview_turns(sid), await service.build_debrief(sid)
    return run(go())


def run_new(monkeypatch, said, strict):
    async def go():
        seeded(monkeypatch, 100)
        started = await hw.start("posting", "resume", strict=strict)
        state, steps = started["state"], []
        for i, text in enumerate(said):
            seeded(monkeypatch, 101 + i)
            try:
                t = await hw.answer(state, text)
            except hw.InterviewEnded:
                steps.append("refused")
                continue
            state = json.loads(json.dumps(t["state"]))  # stored and loaded between every call, like a JSONB column
            steps.append(t)
        return started, steps, state
    return run(go())


@pytest.mark.parametrize("case", CASES)
def test_same_answers_give_the_same_interview_as_the_legacy_handle_answer(monkeypatch, case):
    kwargs, said, strict = CASES[case]
    if kwargs is not None:
        tight_needed = "slow" in kwargs.values()
        if tight_needed:
            tight(monkeypatch)
        legacy_model, new_model = Model(**kwargs), Model(**kwargs)
    else:
        legacy_model = new_model = None
    if legacy_model:
        patch_model(monkeypatch, legacy_model)
    plan, legacy_steps, data, legacy_turns, legacy_debrief = run_legacy(monkeypatch, said, strict)
    if new_model:
        patch_model(monkeypatch, new_model)
    started, new_steps, state = run_new(monkeypatch, said, strict)

    for key in ("project", "topics", "questions", "requirements", "degraded"):
        assert started["plan"][key] == plan[key], key
    assert started["opening"] == plan["questions"][0]
    assert len(legacy_steps) == len(new_steps)
    for old, new in zip(legacy_steps, new_steps):
        if old == "refused" or new == "refused":
            assert old == new == "refused"
            continue
        assert new["reply"] == old["next_question"]
        for key in ("turn", "done", "ended_early", "degraded", "source", "meter"):
            assert new[key] == old[key], key
    assert state["phase"] == data["state"]
    for key in ("turn", "meter_state", "meter_findings", "ended_early", "last_interviewer_text", "degraded_turns"):
        assert state[key] == data[key], key
    assert state["end_reason"] == data.get("end_reason") and state["end_gaps"] == data.get("end_gaps", [])
    assert legacy_turns[:len(state["turns"])] == state["turns"]
    walkthrough_answers = sum(1 for s in new_steps if s != "refused" and s["phase"] == "walkthrough" and not s["done"])
    assert len(legacy_turns) - len(state["turns"]) == 2 * walkthrough_answers  # the legacy path also stores those
    assert {k: v for k, v in legacy_debrief.items() if k != "session_id"} == hw.debrief(state)
    if legacy_model:
        assert new_model.plan_prompts == legacy_model.plan_prompts
        assert new_model.assessor_prompts == legacy_model.assessor_prompts
        assert new_model.turn_prompts == legacy_model.turn_prompts
    # the debrief really is debrief.build, not a second implementation
    assert hw.debrief(state) == debrief.build({**state, "state": state["phase"]}, state["plan"])
