"""The circuit symbol stamps (frontend/src/lib/circuitSymbols.ts) must make strokes the server accepts. The sample
file is made by the TypeScript library: regenerate it with `cd frontend && node scripts/circuit-stamps-sample.mjs`.
A frontend test (circuitSymbols.sample.test.ts) fails when the file is stale, so what is checked here is real output.
This is a drawing aid: nothing here, or in the library, checks a circuit electrically."""
import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from app.v2.models import BoardInput, Stroke

SAMPLE = Path(__file__).resolve().parents[2] / "contracts/examples/circuit_stamps.sample.json"


def strokes():
    return json.loads(SAMPLE.read_text(encoding="utf-8"))["strokes"]


def test_every_sample_stroke_is_a_valid_server_stroke():
    raw = strokes()
    assert len(raw) > 30
    for s in raw:
        stroke = Stroke.model_validate(s)
        # the server compares a saved stroke with the board's copy, so a round trip must change nothing
        assert Stroke.model_validate(stroke.model_dump()) == stroke
        assert stroke.model_dump() == s
    assert len({s["id"] for s in raw}) == len(raw)
    assert {s["kind"] for s in raw} == {"path", "arrow", "text"}


def test_the_sample_is_accepted_as_a_board_snapshot():
    BoardInput.model_validate({"strokes": strokes(), "png": "x"})


def test_the_sample_shows_what_a_model_reading_the_stroke_list_gets():
    labels = {s["label"] for s in strokes()}
    assert {"resistor R1 330Ω", "LED D1 [anode side]", "LED D1 [cathode side]", "DC supply V1 5 V [positive plate]", "wire"} <= labels
    texts = {s["label"] for s in strokes() if s["kind"] == "text"}
    assert {"R1 330Ω", "D1", "V1 5 V", "GND", "+"} <= texts
    assert max(len(s["label"]) for s in strokes()) <= 200


def test_the_server_would_refuse_what_the_library_must_never_make():
    good = strokes()[0]
    for broken in (
        {**good, "points": []},
        {**good, "points": [{"x": 901, "y": 1}]},
        {**good, "points": [{"x": 1, "y": -0.5}]},
        {**good, "points": [{"x": float("nan"), "y": 1}]},
        {**good, "id": ""},
        {**good, "id": "x" * 101},
        {**good, "label": "x" * 201},
        {**good, "kind": "circle"},
    ):
        with pytest.raises(ValidationError):
            Stroke.model_validate(broken)
