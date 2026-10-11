"""Backup model (retry.with_backup, used by the plan call, the live turn and the gap check). When the primary model is
busy or times out after its one retry, the same call is tried once on the model named in GEMINI_BACKUP_MODEL.
These tests try to break that: both models failing, a timeout, bad JSON from the backup, a blank setting (it must make
exactly the old calls), the time limit, and the quote rules on a backup answer. The model is a stub, so no keys and no
network are needed."""
import asyncio
import json
import random
import time

import pytest

from app import config
from app.core import ai, store
from app.modules.prepcrew import assessor, interviewer, retry, service
from app.modules.prepcrew import hardware_interview as hw
from tests.test_interview import ALL_FALLBACKS, client, patch_model
from tests.test_threshold import PLAN, REQS, finding

PRIMARY_NAME, BACKUP_NAME = "gemini-primary-test", "gemini-backup-test"
BACKUP_PLAN = dict(PLAN, project="backup project", questions=[f"B{i}?" for i in range(6)])
SPI = "Honestly I have never used SPI."
LIVE_PLAN = {"project": "motor board", "questions": ["Q0?", "Q1?", "Q2?"]}
TURNS = [{"role": "interviewer", "text": "Q0?", "turn": 0, "shape": None},
         {"role": "candidate", "text": "I put a scope on the 5V rail.", "turn": 1, "shape": None}]


class Model:
    """A stub for ai.generate_text that tells the primary from the backup by the llm_model argument.
    primary and backup are a behaviour, or a dict from kind ("plan", "assessor", "live") to a behaviour:
    "ok", "busy" (503), "timeout" (never answers), "401" (a non-transient error), "junk" (not JSON), "empty"."""

    def __init__(self, primary="ok", backup="ok", findings=None, backup_findings=None, answered=None,
                 backup_answered=None, plan=PLAN, backup_plan=BACKUP_PLAN):
        self.mode = {"primary": primary, "backup": backup}
        self.findings = {"primary": findings or {}, "backup": backup_findings if backup_findings is not None else findings or {}}
        self.answered = {"primary": answered or {}, "backup": backup_answered if backup_answered is not None else answered or {}}
        self.plans = {"primary": plan, "backup": backup_plan}
        self.calls = []

    async def __call__(self, prompt, system=None, **kwargs):
        who = "backup" if kwargs.get("llm_model") else "primary"
        kind = "assessor" if '"findings"' in prompt else "plan" if '"project"' in prompt else "live"
        self.calls.append({"who": who, "kind": kind, "system": system, "kwargs": dict(kwargs), "prompt": prompt,
                           "at": asyncio.get_running_loop().time()})
        mode = self.mode[who]
        mode = mode.get(kind, "ok") if isinstance(mode, dict) else mode
        if mode == "timeout":
            await asyncio.Event().wait()  # until the caller's time limit cancels it
        if mode == "busy":
            raise ai.AIError("Gemini error 503: high demand")
        if mode == "401":
            raise ai.AIError("Gemini error 401: bad key")
        if mode == "empty":
            return ""
        if mode == "junk":
            return "this is { not json"
        if kind == "assessor":
            said = prompt.split("<answer>\n", 1)[1].split("\n</answer>", 1)[0]
            out = {"findings": self.findings[who].get(said, [])}
            if said in self.answered[who]:
                out["answered"] = self.answered[who][said]
            return json.dumps(out)
        if kind == "plan":
            return json.dumps(self.plans[who])
        return f"Which {who} part?"

    def seen(self, who=None, kind=None):
        return [c for c in self.calls if (who is None or c["who"] == who) and (kind is None or c["kind"] == kind)]


def run(coro):
    return asyncio.run(coro)


def live_turn():
    return run(interviewer.next_question(LIVE_PLAN, TURNS, random.Random(1)))


def gap_check(text=SPI):
    return run(assessor.assess(REQS, text, "Which part?"))


def plan_call():
    return run(interviewer.build_plan("posting", "resume"))


SITES = {"live": ("live", live_turn), "gap_check": ("assessor", gap_check), "plan": ("plan", plan_call)}


@pytest.fixture(autouse=True)
def names(monkeypatch):
    """A known primary name, and no backup unless a test asks for one (a real .env may set it)."""
    monkeypatch.delenv(retry.BACKUP_ENV, raising=False)
    monkeypatch.setattr(config, "GEMINI_MODEL", PRIMARY_NAME)
    monkeypatch.setattr(interviewer, "_rng", random.Random(5))


@pytest.fixture
def backup_on(monkeypatch):
    monkeypatch.setenv(retry.BACKUP_ENV, BACKUP_NAME)


@pytest.fixture
def quick(monkeypatch):
    """Retry pauses take no time. Returns the pauses that were asked for."""
    asked, real = [], asyncio.sleep

    async def fast(seconds, *args, **kwargs):
        asked.append(seconds)
        await real(0)
    monkeypatch.setattr(retry.asyncio, "sleep", fast)
    return asked


def limits(monkeypatch, seconds):
    for name in ("LIVE_TURN_TIMEOUT_SECONDS", "ASSESSOR_TIMEOUT_SECONDS", "TASK_TIMEOUT_SECONDS"):
        monkeypatch.setattr(config, name, seconds)


# ---- the setting ----

@pytest.mark.parametrize("value", [None, "", "   ", PRIMARY_NAME, "models/" + PRIMARY_NAME])
def test_a_blank_missing_or_same_as_primary_setting_means_no_backup(monkeypatch, value):
    if value is not None:
        monkeypatch.setenv(retry.BACKUP_ENV, value)
    assert retry.backup_model() == ""


def test_the_setting_is_trimmed_and_read_each_time(monkeypatch):
    monkeypatch.setenv(retry.BACKUP_ENV, "  " + BACKUP_NAME + " ")
    assert retry.backup_model() == BACKUP_NAME
    monkeypatch.setenv(retry.BACKUP_ENV, "models/" + BACKUP_NAME)
    assert retry.backup_model() == BACKUP_NAME


# ---- the primary is busy, the backup answers ----

def test_busy_primary_then_backup_writes_the_live_turn(backup_on, quick, monkeypatch):
    model = Model(primary="busy")
    patch_model(monkeypatch, model)
    reply = live_turn()
    assert (reply.text, reply.source, reply.backup_model) == ("Which backup part?", "model_backup", BACKUP_NAME)
    assert [c["who"] for c in model.calls] == ["primary", "primary", "backup"]  # the primary's one retry, then the backup
    assert model.calls[2]["kwargs"] == {"llm_model": BACKUP_NAME}
    assert model.calls[0]["kwargs"] == model.calls[1]["kwargs"] == {}
    assert model.calls[2]["prompt"] == model.calls[0]["prompt"] and model.calls[2]["system"] == model.calls[0]["system"]
    assert quick == [0.3]


def test_busy_primary_then_backup_does_the_gap_check_and_the_plan(backup_on, quick, monkeypatch):
    said = {SPI: [finding("r1", "unknown", "never used SPI")]}
    model = Model(primary="busy", findings=said)
    patch_model(monkeypatch, model)
    got = gap_check()
    assert got.ok is True and got.backup_model == BACKUP_NAME
    assert [(f["requirement_id"], f["result"]) for f in got.findings] == [("r1", "unknown")]
    assert model.seen("backup", "assessor")[0]["system"] == assessor.ASSESSOR_SYSTEM
    plan = plan_call()
    assert plan["degraded"] is False and plan["backup_model"] == BACKUP_NAME
    assert plan["questions"] == BACKUP_PLAN["questions"] and plan["project"] == "backup project"
    assert quick == [0.3, 1.0]  # the plan's pause is longer, as before


@pytest.mark.parametrize("code", ["error 429", "error 500", "error 502", "error 504"])
def test_every_busy_code_the_retry_knows_reaches_the_backup(backup_on, quick, monkeypatch, code):
    async def stub(prompt, system=None, **kwargs):
        if kwargs.get("llm_model"):
            return "Which backup part?"
        raise ai.AIError(f"Gemini {code}: try later")
    patch_model(monkeypatch, stub)
    assert live_turn().source == "model_backup"


def test_the_backup_is_tried_once_and_with_no_retry_of_its_own(backup_on, quick, monkeypatch):
    model = Model(primary="busy", backup="busy")
    patch_model(monkeypatch, model)
    for site in SITES.values():
        site[1]()
    for kind in ("live", "assessor", "plan"):
        assert [c["who"] for c in model.seen(kind=kind)] == ["primary", "primary", "backup"]


# ---- the primary times out ----

def test_a_primary_that_times_out_hands_over_to_the_backup_inside_the_limit(backup_on, monkeypatch):
    limits(monkeypatch, 1.0)
    model = Model(primary="timeout")
    patch_model(monkeypatch, model)
    started = time.perf_counter()
    reply = live_turn()
    elapsed = time.perf_counter() - started
    assert reply.source == "model_backup" and reply.text == "Which backup part?"
    assert [c["who"] for c in model.calls] == ["primary", "backup"]  # a timeout is not retried on the primary
    assert 0.5 <= model.calls[1]["at"] - model.calls[0]["at"] <= 0.8  # the primary was cut at 0.6 of the limit
    assert elapsed < 1.0


@pytest.mark.parametrize("site", SITES)
def test_a_primary_timeout_then_a_backup_answer_at_every_call_site(backup_on, monkeypatch, site):
    limits(monkeypatch, 1.0)
    kind, call = SITES[site]
    model = Model(primary={kind: "timeout"})
    patch_model(monkeypatch, model)
    got = call()
    assert [c["who"] for c in model.seen(kind=kind)] == ["primary", "backup"]
    if site == "live":
        assert got.source == "model_backup"
    elif site == "gap_check":
        assert got.ok is True and got.backup_model == BACKUP_NAME
    else:
        assert got["degraded"] is False and got["backup_model"] == BACKUP_NAME


# ---- both fail: today's path ----

def test_both_models_busy_gives_the_planned_question_and_counts_nothing(backup_on, quick, monkeypatch):
    model = Model(primary="busy", backup="busy", findings={SPI: [finding("r1", "unknown", "never used SPI")]})
    patch_model(monkeypatch, model)
    reply = live_turn()
    assert reply.source == "fallback" and reply.text == LIVE_PLAN["questions"][1] and reply.backup_model is None
    assert gap_check() == assessor.Assessment(ok=False)
    plan = plan_call()
    assert plan["degraded"] is True and plan["requirements"] == [] and "backup_model" not in plan
    assert plan["questions"][0] in ALL_FALLBACKS


def test_primary_busy_and_backup_timing_out_stays_inside_the_limit(backup_on, quick, monkeypatch):
    limits(monkeypatch, 1.0)
    model = Model(primary="busy", backup="timeout")
    patch_model(monkeypatch, model)
    started = time.perf_counter()
    reply = live_turn()
    assert reply.source == "fallback" and time.perf_counter() - started < 1.0 + 0.3


@pytest.mark.parametrize("backup", ["401", "empty"])
def test_a_backup_that_fails_or_says_nothing_gives_the_planned_question(backup_on, quick, monkeypatch, backup):
    model = Model(primary="busy", backup=backup)
    patch_model(monkeypatch, model)
    reply = live_turn()  # nothing is made up: the planned question is asked
    assert reply.source == "fallback" and reply.text == LIVE_PLAN["questions"][1] and reply.backup_model is None


@pytest.mark.parametrize("backup", ["junk", "401", "empty"])
def test_a_bad_backup_answer_to_the_gap_check_or_plan_degrades_like_a_bad_primary_answer(
        backup_on, quick, monkeypatch, backup):
    said = {SPI: [finding("r1", "unknown", "never used SPI")]}
    model = Model(primary="busy", backup=backup, findings=said)
    patch_model(monkeypatch, model)
    assert gap_check() == assessor.Assessment(ok=False)  # no findings, no penalty, nothing invented
    plan = plan_call()
    assert plan["degraded"] is True and plan["requirements"] == [] and "backup_model" not in plan
    assert all(c["kwargs"] == {"llm_model": BACKUP_NAME} for c in model.seen("backup"))


def test_bad_json_from_the_backup_is_retried_on_the_backup_not_the_primary(backup_on, quick, monkeypatch):
    model = Model(primary="busy", backup="junk")
    patch_model(monkeypatch, model)
    assert gap_check() == assessor.Assessment(ok=False)
    # two primary calls (busy, retried) then ai.generate_json's own one retry for bad JSON, on the backup
    assert [c["who"] for c in model.calls] == ["primary", "primary", "backup", "backup"]


# ---- only a busy provider or a timeout reaches the backup ----

@pytest.mark.parametrize("primary", ["401", "empty"])
def test_other_failures_keep_todays_path_and_never_call_the_backup(backup_on, quick, monkeypatch, primary):
    model = Model(primary=primary)
    patch_model(monkeypatch, model)
    reply = live_turn()
    got = gap_check()
    plan = plan_call()
    assert model.seen("backup") == []
    assert reply.source == "fallback"
    assert got == assessor.Assessment(ok=False)
    assert plan["degraded"] is True


def test_bad_json_from_the_primary_is_not_a_busy_provider(backup_on, quick, monkeypatch):
    model = Model(primary="junk")
    patch_model(monkeypatch, model)
    assert gap_check() == assessor.Assessment(ok=False) and plan_call()["degraded"] is True
    assert model.seen("backup") == []


def test_a_successful_primary_is_never_followed_by_a_backup_call(backup_on, monkeypatch):
    model = Model(findings={SPI: [finding("r1", "unknown", "never used SPI")]})
    patch_model(monkeypatch, model)
    reply, got, plan = live_turn(), gap_check(), plan_call()
    assert reply.source == "model" and reply.backup_model is None
    assert got.backup_model is None and "backup_model" not in plan
    assert model.seen("backup") == []


def test_the_fake_provider_never_reaches_a_backup(backup_on):
    assert config.LLM_PROVIDER == "fake"
    reply = live_turn()
    assert reply.source == "fake" and gap_check() == assessor.Assessment() and plan_call()["degraded"] is True


# ---- blank means exactly today's behaviour ----

def outcome(site, got):
    if site == "live":
        return (got.text, got.source, got.shape, got.violations, got.backup_model)
    return got


BLANK_CASES = [(site, mode) for site in SITES for mode in ("ok", "busy", "timeout", "401", "empty", "junk")
               if not (site == "live" and mode == "junk")]  # a live turn is plain text, there is no JSON to be bad


@pytest.mark.parametrize("site,mode", BLANK_CASES)
def test_a_blank_setting_makes_exactly_the_old_calls_and_gives_the_old_result(monkeypatch, quick, site, mode):
    limits(monkeypatch, 0.1)
    kind, call = SITES[site]

    def one(value):
        quick.clear()
        if value is None:
            monkeypatch.delenv(retry.BACKUP_ENV, raising=False)
        else:
            monkeypatch.setenv(retry.BACKUP_ENV, value)
        monkeypatch.setattr(interviewer, "_rng", random.Random(5))
        model = Model(primary={kind: mode}, backup="ok")
        patch_model(monkeypatch, model)
        got = call()
        return (outcome(site, got), [(c["who"], c["kind"], c["system"], c["kwargs"], c["prompt"]) for c in model.calls],
                list(quick))
    expected = one(None)
    assert all(c[0] == "primary" and c[3] == {} for c in expected[1])  # no llm_model argument ever
    for value in ("", "   ", PRIMARY_NAME, "models/" + PRIMARY_NAME):
        assert one(value) == expected, repr(value)


def test_the_old_calls_literally_with_no_backup_set(monkeypatch, quick):
    limits(monkeypatch, 5.0)
    model = Model(primary="busy")
    patch_model(monkeypatch, model)
    reply = live_turn()
    assert reply.source == "fallback"
    assert [(c["who"], c["kwargs"]) for c in model.calls] == [("primary", {}), ("primary", {})] and quick == [0.3]
    model = Model(primary="401")
    patch_model(monkeypatch, model)
    live_turn(), gap_check(), plan_call()
    assert [(c["kind"], c["kwargs"]) for c in model.calls] == [("live", {}), ("assessor", {}), ("plan", {})]


# ---- time ----

@pytest.mark.parametrize("site", SITES)
def test_primary_and_backup_share_one_limit_when_both_hang(backup_on, monkeypatch, site):
    limit, kind, call = 0.6, *SITES[site]
    limits(monkeypatch, limit)
    model = Model(primary="timeout", backup="timeout")
    patch_model(monkeypatch, model)
    started = time.perf_counter()
    call()
    with_backup = time.perf_counter() - started
    assert [c["who"] for c in model.seen(kind=kind)] == ["primary", "backup"]
    offset = model.calls[1]["at"] - model.calls[0]["at"]
    assert limit * retry.PRIMARY_SHARE - 0.07 <= offset <= limit * retry.PRIMARY_SHARE + 0.25  # the primary's share
    monkeypatch.delenv(retry.BACKUP_ENV)  # the same hang with no backup: today's worst case is the limit
    started = time.perf_counter()
    call()
    without = time.perf_counter() - started
    assert without >= limit - 0.05
    assert with_backup <= without + 0.3  # a backup adds at most this much to today's worst case: nothing but jitter
    assert with_backup <= limit + 0.3


def test_a_primary_that_fails_early_leaves_the_backup_almost_the_whole_limit(backup_on, quick, monkeypatch):
    limits(monkeypatch, 1.0)
    model = Model(primary="busy", backup="timeout")
    patch_model(monkeypatch, model)
    started = time.perf_counter()
    live_turn()
    elapsed = time.perf_counter() - started
    backup_call = model.seen("backup")[0]
    assert backup_call["at"] - model.calls[0]["at"] < 0.2  # started soon after the primary's quick failures
    assert 0.9 <= elapsed <= 1.0 + 0.3  # and was allowed to run to the same overall limit, not past it


def test_each_call_site_splits_its_own_limit(backup_on, monkeypatch):
    live, gap, task = 0.5, 0.8, 1.2  # three different limits, so a call cannot quietly use another call's
    monkeypatch.setattr(config, "LIVE_TURN_TIMEOUT_SECONDS", live)
    monkeypatch.setattr(config, "ASSESSOR_TIMEOUT_SECONDS", gap)
    monkeypatch.setattr(config, "TASK_TIMEOUT_SECONDS", task)
    for site, limit in (("live", live), ("gap_check", gap), ("plan", task)):
        kind, call = SITES[site]
        model = Model(primary="timeout", backup="timeout")
        patch_model(monkeypatch, model)
        started = time.perf_counter()
        call()
        offset = model.calls[1]["at"] - model.calls[0]["at"]
        assert limit * retry.PRIMARY_SHARE - 0.07 <= offset <= limit * retry.PRIMARY_SHARE + 0.25, site
        assert time.perf_counter() - started <= limit + 0.3, site


def test_with_backup_returns_the_winner_and_raises_the_backups_error_when_both_fail(backup_on, quick):
    async def primary_ok(model):
        return "from " + (model or "primary")

    assert run(retry.with_backup(primary_ok, timeout=1.0)) == ("from primary", None)

    async def busy_then_backup(model):
        if model is None:
            raise ai.AIError("Gemini error 503: busy")
        return "from " + model
    assert run(retry.with_backup(busy_then_backup, timeout=1.0)) == ("from " + BACKUP_NAME, BACKUP_NAME)

    async def both_fail(model):
        raise ai.AIError("Gemini error 503: busy" if model is None else "Gemini error 429: also busy")
    with pytest.raises(ai.AIError, match="429") as raised:
        run(retry.with_backup(both_fail, timeout=1.0))
    assert "503" in str(raised.value.__cause__)  # the primary's error is kept as the cause


def test_the_split_is_a_share_of_whatever_the_limit_is(backup_on, monkeypatch):
    assert 0 < retry.PRIMARY_SHARE < 1
    limits(monkeypatch, 1.5)  # a different limit moves both halves of the split
    model = Model(primary="timeout", backup="timeout")
    patch_model(monkeypatch, model)
    started = time.perf_counter()
    plan_call()
    assert 1.5 * retry.PRIMARY_SHARE - 0.07 <= model.calls[1]["at"] - model.calls[0]["at"] <= 1.5 * retry.PRIMARY_SHARE + 0.25
    assert time.perf_counter() - started <= 1.5 + 0.3


# ---- the gap check keeps its quote rules on a backup answer ----

def test_a_backup_gap_check_counts_only_quotes_that_are_in_the_candidates_words(backup_on, quick, monkeypatch):
    backup_findings = {SPI: [finding("r1", "unknown", "never used SPI"),             # in the answer
                             finding("r2", "unknown", "I cannot do I2C"),            # not in the answer
                             finding("r3", "unknown", "never"),                      # one word
                             finding("r9", "unknown", "never used SPI")]}            # not a requirement
    model = Model(primary="busy", backup_findings=backup_findings,
                  backup_answered={SPI: {"result": "no", "evidence_quote": "never said this"}})
    patch_model(monkeypatch, model)
    got = gap_check()
    assert got.backup_model == BACKUP_NAME and got.ok is True
    assert [(f["requirement_id"], f["evidence_quote"]) for f in got.findings] == [("r1", "never used SPI")]
    assert got.no_answer is None  # a made-up "no" quote counts for nothing


def test_the_meter_ignores_a_made_up_backup_finding_and_counts_a_real_one(backup_on, quick, monkeypatch):
    liar = {SPI: [finding("r1", "unknown", "I have no idea about SPI")]}
    patch_model(monkeypatch, Model(primary="busy", backup_findings=liar))
    started = run(hw.start("posting", "resume"))
    t = run(hw.answer(started["state"], SPI))
    assert t["source"] == "model_backup" and t["meter"]["score"] == 0 and t["findings"] == []
    real = {SPI: [finding("r1", "unknown", "never used SPI")]}
    patch_model(monkeypatch, Model(primary="busy", backup_findings=real))
    t = run(hw.answer(started["state"], SPI))
    assert t["meter"]["score"] == config.PENALTY_REQUIRED_UNKNOWN and t["meter"]["checked"] is True


# ---- the rest of lane 1 picks it up without changes ----

def test_hardware_interview_picks_up_the_backup_without_changes(backup_on, quick, monkeypatch):
    real = {SPI: [finding("r1", "unknown", "never used SPI")]}
    model = Model(primary="busy", backup_findings=real)
    patch_model(monkeypatch, model)
    started = run(hw.start("posting", "resume"))
    assert started["degraded"] is False and started["plan"]["backup_model"] == BACKUP_NAME
    assert started["opening"] == BACKUP_PLAN["questions"][0]
    t = run(hw.answer(started["state"], SPI))
    assert t["source"] == "model_backup" and t["degraded"] is False and t["reply"] == "Which backup part?"
    assert t["meter"]["checked"] is True and t["meter"]["score"] == config.PENALTY_REQUIRED_UNKNOWN
    assert t["state"]["degraded_turns"] == 0  # a backup reply is not a degraded turn
    assert json.loads(json.dumps(t)) == t and json.loads(json.dumps(started)) == started


def test_the_legacy_service_and_the_turns_route_accept_the_new_source_value(backup_on, quick, monkeypatch):
    real = {SPI: [finding("r1", "unknown", "never used SPI")]}
    patch_model(monkeypatch, Model(primary="busy", backup_findings=real))
    plan = client.post("/api/plans", json={"job_posting": "j", "resume": "r", "user_id": "u"}).json()
    assert plan["degraded"] is False and plan["questions"] == BACKUP_PLAN["questions"]
    sid = client.post("/api/sessions", json={"plan_id": plan["plan_id"], "user_id": "u", "consent": True}).json()["session_id"]
    r = client.post(f"/api/sessions/{sid}/turns", json={"answer": SPI})
    assert r.status_code == 200
    body = r.json()
    assert body["source"] == "model_backup" and body["degraded"] is False
    assert body["meter"]["score"] == config.PENALTY_REQUIRED_UNKNOWN and body["next_question"] == "Which backup part?"
    stored = [e["data"] for e in run(store.list_events(sid, kind="interviewer"))]
    assert [e["source"] for e in sorted(stored, key=lambda d: d["turn"])] == ["plan", "model_backup"]
    assert run(service.get_session(sid))["data"]["degraded_turns"] == 0


def test_the_voice_socket_works_when_the_backup_wrote_the_reply(backup_on, quick, monkeypatch):
    from tests.test_voice_out import connect, recv_until
    patch_model(monkeypatch, Model(primary="busy", backup_findings={SPI: [finding("r1", "unknown", "never used SPI")]}))
    plan = client.post("/api/plans", json={"job_posting": "j", "resume": "r", "user_id": "u"}).json()
    sid = client.post("/api/sessions", json={"plan_id": plan["plan_id"], "user_id": "u", "consent": True}).json()["session_id"]
    with connect(sid) as ws:
        ws.send_json({"type": "text_answer", "text": SPI})
        got = recv_until(ws, "tts_done")
    types = [m["type"] for m in got if isinstance(m, dict)]
    assert "interviewer_text" in types and "meter" in types and "error" not in types
    assert next(m for m in got if isinstance(m, dict) and m["type"] == "interviewer_text")["text"] == "Which backup part?"
    assert next(m for m in got if isinstance(m, dict) and m["type"] == "meter")["score"] == config.PENALTY_REQUIRED_UNKNOWN


def test_the_plan_and_state_gain_no_new_key_unless_the_backup_wrote_them(monkeypatch):
    patch_model(monkeypatch, Model())
    started = run(hw.start("posting", "resume"))
    assert "backup_model" not in started["plan"] and "backup_model" not in json.dumps(started["state"])
    assert set(plan_call()) == {"project", "topics", "questions", "requirements", "degraded"}  # as before
