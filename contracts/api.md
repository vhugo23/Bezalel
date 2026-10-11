# HTTP API

Status: proposed. "Today" is what `backend/app/modules/prepcrew/routes.py` has now (all stubs returning `"TODO"`).
Routes keep the existing `/api` prefix. The brief's sketch had no prefix, so `/api/sessions/{id}/end` replaces `/sessions/{id}/end`.

| Route | Today | Change proposed |
|---|---|---|
| `POST /api/plans` | built | Request fields 1 to 20000 chars. Response has `project`, `degraded` (true when generic questions were used). Still to add: `scenario_ids`. |
| `POST /api/sessions` | built | Request needs `user_id` and `consent: true` (400 if false). Response has `pair_code`, `state` and `opening` (first question, interview sessions only). |
| `POST /api/sessions/{id}/turns` | built | Typed path, also the fallback for voice. Answer max 5000 chars, blank is 400. After the interview part ends the route keeps storing answers (the walkthrough is spoken too) and replies with a scripted line until the walkthrough interviewer exists. Response: `next_question`, `answer_id`, `done`, `degraded`, `source`. `source` is `model`, `fallback` (model failed, planned question used), `fake` (fake provider), or `scripted`. After `done`, the session is in `walkthrough`. Runs in one process only, see below. |
| `POST /api/sessions/{id}/probe` | exists, `{node}` only | Replace with the board WebSocket. Keep the POST for tests and as a fallback. Response is a probe event. |
| `POST /api/sessions/{id}/end` | exists | Returns immediately with `{"status": "grading"}`. Results arrive over SSE. |
| `GET /api/sessions/{id}/events` | missing | SSE, event types below. |
| `GET /api/sessions/{id}/report` | exists | Results use the new evaluator shape, grouped by criterion. |
| `GET /api/skills` | missing | Skill graph slice: nodes, prerequisites, current mastery for `user_id`. |
| `GET /api/lessons/{skill_id}` | exists as `{topic}` | Rename the path param to `skill_id`. Response keeps `ai_generated`. |
| `POST /api/retests` | exists | Request adds `session_id`. Response is a new session with `kind: retest`. |
| `GET /api/mastery?user_id=` | missing | Reads `mastery_daily`. Series per skill. |
| `GET /api/metrics/{session_id}` | missing | Stage latencies and evaluator completion time, measured values only. Empty fields when nothing was measured. |
| `DELETE /api/sessions/{id}` | missing | Deletes all rows for a tester session, in every table. Required for consent. |

## SSE: `GET /api/sessions/{id}/events`

| event | data |
|---|---|
| `evaluator_started` | `{"answer_id", "rubric_id"}` |
| `evaluator_done` | `{"answer_id", "rubric_id", "duration_ms", "needs_review"}` |
| `evaluator_failed` | `{"answer_id", "rubric_id", "reason"}` where reason is `timeout`, `bad_json`, or `quote_mismatch` |
| `grading_complete` | `{"session_id", "total_ms"}` |

## Evaluator pipeline contract

1. One call per answer per rubric, run through `core.jobs.fan_out` with a semaphore. Concurrency limit comes from config, not code.
2. The model gets the transcript, the rubric, and for `uses_probe_log` criteria the ordered probe events.
3. Output must pass `evaluator_output.schema.json`. `core.ai.generate_json` retries once with the error text. Second failure: store `needs_review: true`, emit `evaluator_failed` with `bad_json`.
4. Quote check (reference code in `contracts/check_contracts.py`): `transcript[start:end] == evidence_quote` for every criterion, and scores within `0..score_max`. One mismatch rejects the whole result, retry once, then `needs_review: true` with `quote_mismatch`.
5. Passing results write one `answer_scores` row per criterion with `score / score_max`. Results with `needs_review` are stored but excluded from the mastery aggregate.
6. Reported durations are measured with `perf_counter`. Nothing is estimated.

## Live interview notes

- Live turns time out after `LIVE_TURN_TIMEOUT_SECONDS` (default 5). Background work uses `TASK_TIMEOUT_SECONDS`.
- Per-session locking is in process memory. Run a single uvicorn worker until turns are stored with a row lock or a version check.
- `/api/plans` and the turns route are not behind `x-api-key`. The browser calls them, so a key would ship in the page. Add a rate limit at deploy.
- `DELETE /api/sessions/{id}` removes the session, its events and its interview transcript. The plan record (resume and posting text) is only removed if `delete_linked` is extended to it. Check before the first tester session.

## Patience meter (fail threshold)

- `POST /api/plans` returns `requirements: [{id, text, level}]`, `level` is `required` or `preferred`, read from the posting's wording. An unclear level counts as `preferred`. Empty means the meter is off and the interview never ends early.
- `POST /api/sessions` takes `strict` (default `true`). With `strict: false` the meter still wraps the interview up but never ends it, for demos and testers.
- `POST /api/sessions/{id}/turns` returns `meter: {score, threshold, level}` (`ok`, `wrapping_up`, `ended`; null when off) and `ended_early`. When the meter ends the interview, `next_question` is a fixed closing line (`source: "scripted"`), `done` and `ended_early` are true, and the session moves to `debrief`. Further answers get 400 ("the interview has ended"). Grading and the report still work.
- How it works: a separate model call checks each answer against the posting's skills, in parallel with the reply, so it adds cost and no waiting time. A gap only counts if the quoted words appear in the answer word for word. Failures of any kind mean no penalty. Each skill counts once at its worst result. One answer adds at most 0.6, so ending takes at least two answers. The "wrap up" push reaches the interviewer one turn after the meter crosses it.
- Starting values, chosen by hand and not validated (`config.py`): threshold 1.0, wrap up at 0.5, required unknown 0.6 / partial 0.25, preferred unknown 0.15 / partial 0.05.
- The session stores `meter_state`, `meter_findings` (every finding with its quote and turn), and after an early end `ended_early`, `end_reason: "requirement_gaps"` and `end_gaps` (skill, level, result, the candidate's own words) for the debrief.
- Only the project interview is covered. Failing the circuit walkthrough is graded, not ended.
