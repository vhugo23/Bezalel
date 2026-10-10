# Contracts

Shared shapes for all lanes. Nothing here is wired into the app yet. These files are the target, and the
backend gets updated to match them (or these change, in which case say so in the commit).

| File | Owner lane | What it fixes |
|---|---|---|
| `netlist.schema.json` | Circuit | Scenario files: parts, nets, planted fault, solver fallback voltages, layout |
| `probe_event.schema.json` | Circuit, Backend | One user action on the circuit, ordered by server `seq` |
| `rubric.schema.json` | Content | What evaluators grade. `status: reviewed` only after a real human review |
| `evaluator_output.schema.json` | Backend | Per criterion score, verbatim quote, character span |
| `db.sql` | Backend | Two hypertables and the daily mastery continuous aggregate. Unverified syntax |
| `api.md` | Backend, Frontend | Routes, SSE events, evaluator pipeline rules |
| `ws_messages.md` | Voice, Circuit | Voice and board WebSocket messages |
| `env.additions.md` | Everyone | Env vars the current `.env.example` is missing |
| `check_contracts.py` | Everyone | Validates the examples and shows the quote check |
| `examples/` | Everyone | One scenario, one rubric (draft), probe events, a transcript, an evaluator output |

Check the examples:

    pip install jsonschema
    python check_contracts.py

The examples are shape examples, not content. The rubric is a draft that no one has reviewed.
The LED forward drop of 2.0 V in `led_reversed.json` is an assumption for the example.

## Overlap with the existing backend

`backend/sql/prepcrew.sql` has an `evaluations` table (one row per evaluator and topic). `db.sql` has
`answer_scores` (one row per criterion). Pick one source of truth for scores before wiring the chart.
Proposed: `answer_scores` feeds the chart and `evaluations` can be dropped.
