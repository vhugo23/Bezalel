"""Debrief and resources. The library is checked for integrity, matching is checked for wrong matches, and the debrief
is checked to contain only quotes the candidate said and links that are in the library. Model stubbed."""
import asyncio
import re

import pytest

from app import config
from app.modules.prepcrew import debrief, humanness, meter, resources
from tests.test_threshold import (DODGE, I2C, KICAD, PLAN, REQS, SPI, Script, answer, client, dodges, finding, gaps,
                                  start)

LIBRARY_URLS = {r["url"] for r in resources.library()}


# ---- the library ----

def test_library_entries_are_complete_and_unique():
    lib = resources.library()
    assert len(lib) >= 20
    assert len({r["id"] for r in lib}) == len(lib) and len({r["url"] for r in lib}) == len(lib)
    for r in lib:
        assert r["url"].startswith("https://") and r["title"].strip() and r["why"].strip() and r["source"].strip()
        assert r["kind"] in ("tutorial", "video", "docs", "reference") and r["level"] in ("beginner", "intermediate")
        assert r["keys"] and all(k == k.lower() and k.strip() == k for k in r["keys"])
        assert r["verified_on"] == resources.VERIFIED_ON


def test_nothing_is_marked_reviewed_until_a_person_does_it():
    assert all(r["reviewed"] is False for r in resources.library())


# ---- matching ----

@pytest.mark.parametrize("text,expected_first", [
    ("I2C", "sf-i2c"), ("SPI", "sf-spi"), ("UART", "sf-serial"), ("oscilloscopes and multimeters", None),
    ("KiCad or Altium", "kicad-docs"), ("MOSFET gate drivers", "ti-gate-driver"),
    ("version control for hardware", "pro-git"), ("digital logic", "et-logic-gates"),
    ("reading schematics and datasheets", None),
])
def test_matches_the_right_resource(text, expected_first):
    got = resources.match(text)
    assert got, text
    if expected_first:
        assert got[0]["id"] == expected_first


def test_buck_converters_and_emi_match_both_the_explainer_and_the_app_note():
    assert {r["id"] for r in resources.match("buck converters")} == {"wiki-buck", "ti-buck-appnote"}
    assert {r["id"] for r in resources.match("EMI basics")} == {"wiki-emc", "ti-pcb-emi"}


def test_c_or_cpp_gets_c_resources_and_the_cpp_one_first_for_cpp():
    got = [r["id"] for r in resources.match("C or C++", limit=3)]
    assert set(got) == {"beej-c", "learn-c", "learncpp"}
    assert resources.match("C++ templates")[0]["id"] == "learncpp"


@pytest.mark.parametrize("text", ["spice simulation", "gitlab runners", "quantum widgets", "Altium", "", "cpu cache",
                                  "the spirit of teamwork"])
def test_wrong_matches_are_not_made(text):
    assert resources.match(text) == []


def test_whole_words_only_and_limit_and_shape():
    assert [r["id"] for r in resources.match("SPI and I2C and UART", limit=1)] and len(resources.match("SPI and I2C and UART", limit=1)) == 1
    for r in resources.match("SPI"):
        assert "keys" not in r and r["reviewed"] is False and r["url"] in LIBRARY_URLS


def test_search_hint_is_a_search_term_not_a_link():
    hint = resources.search_hint("Altium")
    assert hint == 'Search for: "Altium tutorial for beginners"' and "http" not in hint


# ---- the builder ----

def session_data(items, findings, **extra):
    state = {**meter.new_state(), "items": items}
    return {"state": "debrief", "meter_state": state, "meter_findings": findings, "strict": True, **extra}


def test_builder_orders_gaps_worst_first_and_lists_strengths(monkeypatch):
    monkeypatch.setattr(config, "LLM_PROVIDER", "gemini")
    items = {"r3": "unknown", "r1": "partial", "r2": "knows", "r4": "unknown"}
    found = [{"requirement_id": "r1", "result": "partial", "evidence_quote": "only a little SPI", "turn": 2},
             {"requirement_id": "r2", "result": "knows", "evidence_quote": "used I2C on the board", "turn": 1},
             {"requirement_id": "r3", "result": "unknown", "evidence_quote": "never used KiCad", "turn": 3},
             {"requirement_id": "r4", "result": "unknown", "evidence_quote": "no idea about Altium", "turn": 3},
             {"kind": "no_answer", "turn": 4, "question": "How did you size the capacitor?", "evidence_quote": "I mostly did the power stage"}]
    out = debrief.build(session_data(items, found, ended_early=True, end_reason="requirement_gaps"), {"requirements": REQS})
    assert [(g["title"], g["result"]) for g in out["gaps"]] == [
        ("SPI", "partial"), ("KiCad", "unknown"), ("Altium", "unknown"), ("Didn't answer: How did you size the capacitor?", "no_answer")]
    assert [s["title"] for s in out["strengths"]] == ["I2C"] and out["strengths"][0]["evidence_quote"] == "used I2C on the board"
    assert out["status"] == "ended_early" and out["end_reason"] == "requirement_gaps"
    spi, kicad, altium, unanswered = out["gaps"]
    assert spi["resources"][0]["id"] == "sf-spi" and spi["search_hint"] is None
    assert kicad["resources"][0]["id"] == "kicad-docs"
    assert altium["resources"] == [] and altium["search_hint"] == 'Search for: "Altium tutorial for beginners"'
    assert unanswered["tip"] and unanswered["resources"][0]["id"] in {"sf-capacitors", "wiki-buck", "ti-buck-appnote"}
    assert out["library_reviewed"] is False and "a person has not reviewed them yet" in out["resources_note"]


def test_summary_reads_plainly_and_passes_the_humanness_checker(monkeypatch):
    items = {"r1": "unknown", "r2": "unknown", "r3": "partial", "r4": "knows"}
    found = [{"kind": "no_answer", "turn": 2, "question": "Q?", "evidence_quote": "um"},
             {"kind": "no_answer", "turn": 3, "question": "Q2?", "evidence_quote": "idk"}]
    summary = debrief.build(session_data(items, found, ended_early=True), {"requirements": REQS})["summary"]
    assert summary == ("This interview ended early. Here is what stood out: you said you haven't used SPI and I2C; "
                       "you have only limited experience with KiCad; 2 questions didn't get an answer. "
                       "You did show you know Altium.")
    assert humanness.check(summary) == []


def test_summary_when_nothing_stood_out():
    out = debrief.build(session_data({}, []), {"requirements": REQS})
    assert out["summary"] == "Nothing you said stood out as a gap." and out["gaps"] == [] and out["strengths"] == []
    assert out["status"] == "interview_finished"


def test_one_unanswered_question_is_singular():
    found = [{"kind": "no_answer", "turn": 2, "question": "Q?", "evidence_quote": "um"}]
    assert "one question didn't get an answer" in debrief.build(session_data({}, found), {"requirements": []})["summary"]


def test_a_requirement_the_plan_no_longer_has_is_skipped_not_a_crash():
    out = debrief.build(session_data({"r99": "unknown"}, []), {"requirements": REQS})
    assert out["gaps"] == []


# ---- the endpoint and the voice socket ----

def play_to_the_end(monkeypatch):
    script = Script(findings=gaps(), answered=dodges(DODGE))
    _, sid = start(monkeypatch, script)
    said = []
    for text in (DODGE, SPI, I2C):
        said.append(text)
        r = answer(sid, text).json()
    assert r["ended_early"] is True
    return sid, said


def test_endpoint_returns_the_debrief_with_real_quotes_and_known_links(monkeypatch):
    sid, said = play_to_the_end(monkeypatch)
    r = client.get(f"/api/sessions/{sid}/debrief")
    assert r.status_code == 200
    out = r.json()
    assert out["session_id"] == sid and out["status"] == "ended_early" and out["ended_early"] is True
    titles = [g["title"] for g in out["gaps"]]
    assert titles[:2] == ["SPI", "I2C"] and titles[2].startswith("Didn't answer: ")
    everything_said = " ".join(said).lower()
    for g in out["gaps"]:
        assert re.sub(r"[^\w\s']", " ", g["evidence_quote"].lower()).split() and \
            " ".join(re.sub(r"[^\w\s']", " ", g["evidence_quote"].lower()).split()) in \
            " ".join(re.sub(r"[^\w\s']", " ", everything_said).split())
        assert all(res["url"] in LIBRARY_URLS and res["reviewed"] is False for res in g["resources"])
    assert out["gaps"][0]["resources"][0]["url"] == "https://learn.sparkfun.com/tutorials/serial-peripheral-interface-spi"
    assert out["meter"]["level"] == "ended" and out["library_reviewed"] is False
    assert humanness.check(out["summary"]) == []


def test_debrief_works_before_the_end_and_for_a_session_with_no_gaps(monkeypatch):
    _, sid = start(monkeypatch, Script())
    out = client.get(f"/api/sessions/{sid}/debrief").json()
    assert out["status"] == "in_progress" and out["gaps"] == [] and out["summary"] == "Nothing you said stood out as a gap."


def test_debrief_on_the_fake_provider_has_no_meter():
    plan_id = client.post("/api/plans", json={"job_posting": "j", "resume": "r"}).json()["plan_id"]
    sid = client.post("/api/sessions", json={"plan_id": plan_id, "user_id": "u", "consent": True}).json()["session_id"]
    out = client.get(f"/api/sessions/{sid}/debrief").json()
    assert out["meter"] is None and out["gaps"] == []


def test_unknown_session_and_deleted_session_have_no_debrief(monkeypatch):
    assert client.get("/api/sessions/nope/debrief").status_code == 404
    sid, _ = play_to_the_end(monkeypatch)
    assert client.delete(f"/api/sessions/{sid}").status_code == 200
    assert client.get(f"/api/sessions/{sid}/debrief").status_code == 404


def test_the_voice_socket_says_when_the_debrief_is_ready(monkeypatch):
    _, sid = start(monkeypatch, Script(findings=gaps()))
    from tests.test_voice_out import connect, recv_until
    with connect(sid) as ws:
        ws.send_json({"type": "text_answer", "text": SPI})
        first = recv_until(ws, "tts_done")
        assert not any(isinstance(m, dict) and m["type"] == "debrief_ready" for m in first)  # not ended yet
        ws.send_json({"type": "text_answer", "text": I2C})
        second = recv_until(ws, "tts_done")
    types = [m["type"] for m in second if isinstance(m, dict)]
    assert types.index("state") < types.index("debrief_ready") < types.index("tts_done")
    ready = next(m for m in second if isinstance(m, dict) and m["type"] == "debrief_ready")
    assert ready["session_id"] == sid
