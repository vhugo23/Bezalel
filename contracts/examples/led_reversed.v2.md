# led_reversed.v2.json

`led_reversed.json` (the v1 netlist example) written as a v2 scenario: the layout of `contracts/e2e-two-step.json`, read by `backend/app/v2/engine.py` (steps) and `rubrics.py` (rubric). It is data only. Nothing loads it yet. `backend/tests/test_led_reversed_v2.py` runs it through `engine.parse_steps` and `rubrics.load` and compares it with the originals.

## Kept as it was
The prompt (word for word), the title (used as the step title), the two hints in `fault.hint_ladder` (now the step's `hints`, which the v2 hint button serves in order), parts, nets, ground net, fault type and part, both sets of expected voltages. The four criteria keep their ids and wording from `debug_process_rubric.json`.

## The v2 format cannot express
- **Probes.** v2 events are `turn`, `stroke`, `step`, `note`, `interrupted`. There is no probe event, no schematic screen in `frontend/` (the `schematic` surface exists in the type and nothing draws it), and no code behind the `dc_solver` engine row. The step is therefore `voice`. If the candidate asks what a meter reads, the interviewer model has the readings in the spec and can say them.
- **Evidence from the probe log.** v2 evidence rules are `question`, `quoted_turn`, `board_explanation`, `drawing`. The first three legacy criteria had `uses_probe_log: true`. Here all four are judged only from what the candidate says they would do (`quoted_turn`), which is a weaker test.
- **Per-criterion score anchors.** The legacy rubric had 0 to 2 anchors per criterion. v2 uses one shared 0 to 4 anchor table (`rubrics.ANCHORS`). The anchors are not carried.
- **Expected voltages as a check.** They sit in `circuit` as plain data. Nothing in v2 compares them with anything.
- **Layout.** The schematic and breadboard coordinates are left out. No screen would use them and every turn sends the whole spec to the model.

## My choices (check these)
- One step, `min_turns` 2 (the same as the existing voice steps in `engine.LEGACY_STEPS`). The task text, "Walk through how you would debug the dark LED.", is mine.
- Skill ids: the legacy ids (`circuits1.*`) are not in the v2 `skills` table, and `claims.skill_id` has a foreign key to it. I used `hw.power_rails` for the supply criterion and `hw.circuit_probing` for the other three. The mapping is a guess.
- One evaluator group, "Debug process", so one grading call. Rubric version `debug-process-draft-v0`. `status: draft` and `reviewed_by: null` are copied in from the legacy rubric; `rubrics.load` ignores them. No person has reviewed this rubric.
- The second hint refers to "the reading at n2", which a voice-only candidate does not have until the interviewer gives it.

## Assumptions (also listed in the file under `assumptions`, with JSON pointers)
- The 2.0 V LED forward drop is an assumption (also said in `contracts/README.md`). It is `/circuit/parts/2/value` and, as the healthy reading, `/circuit/expected_voltages/healthy/n2`.
- The faulted 5.0 V at n2 assumes a reversed LED passes no current. That reasoning is mine, not in the source file. Reverse leakage was not modelled or measured.

## Making it runnable takes changes outside this file
- `v2/service.create_plan` inserts a scenario only for `sw.sysdesign`. `hw.circuit_debug` stays `proposed`, and `start()` refuses a track that is not `ready` with a passed scenario. Loading this file means inserting a ready track, a scenario row (`spec` = this file, `rubric` = its `rubric` key) and a `scenario_steps` row, as `backend/scripts/e2e.py` does for the two-step fixture.
- `respond()` and the evaluator send the whole `spec` to the model, including `circuit.fault`. The interviewer prompt says not to grade, but nothing stops it from naming the fault. A person should read a few real turns before this is shown.
