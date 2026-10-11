# hw_circuit_debug.two_step.v2.json

A two-step scenario for track `hw.circuit_debug` (engine `dc_solver`) in the v2 scenario layout (`engine.py` steps, `rubrics.py` rubric, like `contracts/e2e-two-step.json`). Data only: nothing loads it. Checked against `origin/main` at `9df2b90`. `backend/tests/test_hw_circuit_debug_scenario.py` runs it through `engine.parse_steps` and `rubrics.load`.

## The steps
0. **Project interview** (`voice`). `config.driver = "hardware_interview"` marks the step as run by `backend/app/modules/prepcrew/hardware_interview.py`. The key name `driver`, the other `config` keys (`inputs`, `strict`, `strict_why`) and `project_interview` are my proposal, not an existing v2 contract. The input is `spec.project_interview.posting` and `.resume`, both synthetic. `strict` is `false` with the reason beside it: early end has no human calibration (josh-agent's own default). The text is the sample pair from `spikes/voice_check/index.html`, reused with edits: labelled synthetic, the name changed to "Sample Candidate", and the phrase "swapped LED polarity" removed from the resume because it is the planted fault in other words. When a candidate's imported resume and posting exist, use them instead.
1. **LED does not light** (`voice`). The earlier LED scenario's wording, hints and four draft debug criteria, now citing step 1.

## Where the answer key is, and why
`hw_circuit_debug.answer_key.json` holds the circuit, the planted fault, both sets of voltages and the two marked assumptions (the 2.0 V LED drop; the reversed LED passes no current). Intended home: `scenarios.params`. On `origin/main` nothing in `backend/app/v2` reads `params`, while these are sent to a model or the browser:
- the whole `spec` and every step field go into the interviewer prompt (`service.respond`, the `json.dumps({'scenario':definition['spec'], ... 'steps':[...]})`) and the whole `spec` into the evaluator prompt (`assessment.evaluate`). The lesson prompt also gets `spec`, but only for the `conceptual` engine (`learning.create` refuses others);
- the browser gets every step field (`Session.steps`) and `spec['prompt']` as the opening line.

So the scenario file has no circuit, no orientation, no voltages and no fault name, and the key must never go into `spec`, `rubric`, a step's `config` or `hints`. That is why the key is a separate file and not a section here: a loader that stores a whole file as `spec` (as `backend/scripts/e2e.py` does) would leak it. The test calls the real prompt code to show the current behaviour. It cannot show what a new loader does with the files.

## What josh-agent has to wire
- A scenario row for the hw track (today `create_plan` makes one only for `sw.sysdesign`): `spec` = the scenario file, `rubric` = its `rubric` key, steps as rows, `params` = the key file.
- Step 0: call `hardware_interview.start/answer` when `config.driver` says so, and `advance` on `done` (the handoff message has the sketch). `min_turns: 2` must not exceed the answers before the hand-off (the plan has 4 to 6 questions), or `advance` is downgraded.
- Step 1: the DC engine owns the readings and the check. Until it exists the model cannot read out a voltage, because it is not given one. The step is a spoken discussion only.

## Not expressible, and guesses
- No probe events, no schematic, no per-criterion anchors, and no way to grade step 0 in the v2 report (the lane 1 debrief has its own shape). Hint 2 mentions "the reading at n2", which a voice-only candidate does not have.
- Guesses: the key names above; `min_turns: 2` on both steps; skill ids (`hw.power_rails` for the supply criterion, `hw.circuit_probing` for the rest; the legacy `circuits1.*` ids are not in the v2 `skills` table); rubric version `hw-circuit-debug-draft-v0`; the top-level `prompt` is lane 1's own fallback opening question ("Tell me about a project on your resume that you're proud of."), while the symptom text sits in step 1's `task`. No person has reviewed the rubric.
