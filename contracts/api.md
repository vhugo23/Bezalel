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
| `grading_complete` | `{"session_id", "total_ms"}`. Sent after the report is saved, so fetching the report right away is safe. |

## Evaluator pipeline contract

1. One call per answer per rubric, run through `core.jobs.fan_out` with a semaphore. Concurrency limit comes from config, not code.
2. The model gets the transcript, the rubric, and for `uses_probe_log` criteria the ordered probe events.
3. Output must pass `evaluator_output.schema.json`. `core.ai.generate_json` retries once with the error text. Second failure: store `needs_review: true`, emit `evaluator_failed` with `bad_json`.
4. Quote check (reference code in `contracts/check_contracts.py`): `transcript[start:end] == evidence_quote` for every criterion, and scores within `0..score_max`. One mismatch rejects the whole result, retry once, then `needs_review: true` with `quote_mismatch`.
5. Passing results write one `answer_scores` row per criterion with `score / score_max`. Results with `needs_review` are stored but excluded from the mastery aggregate.
   Built: `backend/sql/timeseries.sql` creates `answer_scores`, `probe_events` and `mastery_daily` (real-time), and `GET /api/mastery` reads the aggregate.
7. Criteria with `uses_probe_log` may cite probe steps as evidence in `evidence_probe_seqs` (seq numbers from this session's probe log) instead of a quote. Cited steps must exist in the log, and only process criteria may cite them.
6. Reported durations are measured with `perf_counter`. Nothing is estimated.

## Live interview notes

- Live turns time out after `LIVE_TURN_TIMEOUT_SECONDS` (default 5). Background work uses `TASK_TIMEOUT_SECONDS`.
- Per-session locking is in process memory. Run a single uvicorn worker until turns are stored with a row lock or a version check.
- `/api/plans` and the turns route are not behind `x-api-key`. The browser calls them, so a key would ship in the page. Add a rate limit at deploy.
- `DELETE /api/sessions/{id}` removes the session, its events and its interview transcript, and the plan (resume and posting text) once no other session, such as a retest, still uses it.

## Patience meter (fail threshold)

- `POST /api/plans` returns `requirements: [{id, text, level}]`, `level` is `required` or `preferred`, read from the posting's wording. An unclear level counts as `preferred`. Empty means the meter is off and the interview never ends early.
- `POST /api/sessions` takes `strict` (default `true`). With `strict: false` the meter still wraps the interview up but never ends it, for demos and testers.
- `POST /api/sessions/{id}/turns` returns `meter: {score, threshold, level, unanswered, checked}` (`level` is `ok`, `wrapping_up` or `ended`; the whole object is null only when no real model is in use) and `ended_early`. `checked` is false when the check could not run for that answer (model error or timeout), so nothing was judged and the score did not move. When the meter ends the interview, `next_question` is a fixed closing line (`source: "scripted"`), `done` and `ended_early` are true, and the session moves to `debrief`. Further answers get 400 ("the interview has ended"). Grading and the report still work.
- How it works: a separate model call checks each answer against the posting's skills, in parallel with the reply, so it adds cost and no waiting time. A gap only counts if the quoted words appear in the answer word for word. Failures of any kind mean no penalty. Each skill counts once at its worst result. One answer adds at most 0.6, so ending takes at least two answers. The "wrap up" push reaches the interviewer one turn after the meter crosses it.
- Starting values, chosen by hand and not validated (`config.py`): threshold 1.0, wrap up at 0.5, required unknown 0.6 / partial 0.25, preferred unknown 0.15 / partial 0.05.
- The session stores `meter_state`, `meter_findings` (every finding with its quote and turn), and after an early end `ended_early`, `end_reason: "requirement_gaps"` and `end_gaps` (skill, level, result, the candidate's own words) for the debrief.
- Only the project interview is covered. Failing the circuit walkthrough is graded, not ended.

Two things move the meter:
- **A stated gap on a skill from the posting** (see above).
- **An answer that ignores the interviewer's last question**: it dodges, changes the subject, says only that they do not know or cannot say, or is empty or nonsense. Asking a clarifying question back is not one. It counts every time (each question is new), 0.35 each by default, so the second one starts the wrap-up and the third ends a strict interview. An answer that admits a skill gap ("I've never used SPI") is penalized as that gap and not also as a non-answer. Like a skill gap, it only counts when the model's quote of the candidate's own words appears in the answer word for word.
- The meter works even when the posting yielded no skills, because non-answers do not depend on them. After an early end, `end_gaps` lists unanswered questions as `{result: "no_answer", text: "did not answer: <question>", evidence_quote}`.

## Debrief (end of the interview)

`GET /api/sessions/{id}/debrief` returns what stood out and where to learn each gap. It works at any point (before the
end it describes what is known so far) and for any session that has a plan. The voice socket sends `debrief_ready`
right after `state: debrief` when the patience meter ends an interview, so the frontend can fetch and show it.

- `status`: `in_progress`, `interview_finished` or `ended_early`. Also `ended_early`, `end_reason`, `meter`.
- `summary`: a plain template built from the findings ("This interview ended early. Here is what stood out: you said you haven't used SPI and UART; one question didn't get an answer. You did show you know I2C."). No model writes it.
- `gaps`: worst first (required unknown, required partial, preferred unknown, preferred partial, then unanswered questions). Each has `kind` (`skill` or `unanswered`), `title`, `level`, `result` (`unknown`, `partial`, `no_answer`), `evidence_quote` (the candidate's own words, checked to appear in their answer), `turn`, `resources`, `search_hint` and `tip`.
- `strengths`: skills they showed they know, with their own words.
- `resources`: up to two links per gap from a short hand-picked library (`data/resources.json`, 24 entries). Each was opened and its content read on `verified_on`, and carries a `why` taken from the page and sometimes a `caveat`. **`reviewed` is false for all of them until a person reviews the links.** `library_reviewed` and `resources_note` say so. A skill with no match gets a `search_hint` (a search term, never a link). The model never writes a link.
- Matching is by whole words in the skill text or the unanswered question, so "SPI" does not match "spice".
- Not yet linked to the skill graph (`topics.json` is empty), so there is no lesson link or retest yet.
- Keep the links alive: `spikes/check_resource_links.py` re-checks every URL.

## Memory across sessions (Backboard)

- `POST /api/plans` response adds `memories: [str]` and `POST /api/sessions` adds `recalled: [str]`. Empty on a user's first session.
- Saved after grading from the debrief (skill gaps with the candidate's verified quote, strengths), at most 8 per session.
- `DELETE /api/sessions/{id}` also deletes that session's memories from Backboard.
- Not yet used by the interviewer: `interviewer.build_plan` should take the memories so the opening can follow up on last time.
