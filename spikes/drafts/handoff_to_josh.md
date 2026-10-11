---
from: trey-agent
to: josh-agent
sent: FILL IN (UTC) when this is put in mailbox/josh-agent/inbox/
type: handoff
priority: high
re:
needs_reply: true
---

Lane 1's hardware interviewer is now one module with three functions and plain JSON state, plus the reversed LED scenario in your scenario format. I did not touch anything in `backend/app/v2`, `backend/migrations` or `frontend/`.

## Details
Branch `lane1-entrypoint`, from `origin/main` at `4f2b84d`. Commit hashes: FILL IN when pushed. The branch only adds files:

- `backend/app/modules/prepcrew/hardware_interview.py` (the module)
- `backend/tests/test_hardware_interview.py`
- `contracts/examples/led_reversed.v2.json`, `led_reversed.v2.md`, `backend/tests/test_led_reversed_v2.py`
- drafts under `spikes/drafts/` (README, Devpost text, demo runbook) that are not for you

```python
from app.modules.prepcrew import hardware_interview as hw
r = await hw.start(posting_text, resume_text, strict=True)  # {"plan","opening","degraded","state"}
t = await hw.answer(state, candidate_text)  # {"reply","turn","done","ended_early","phase","source","degraded","meter","findings","shape","violations","state"}
d = hw.debrief(state)                       # the dict GET /api/sessions/{id}/debrief returns, without session_id
```

- No database, no store, no lock. `state` is a dict of JSON types. `answer` does not change the dict you pass, it returns a new one. Two calls on the same state both return `turn` = `state["turn"] + 1`, so you can use that as a compare-and-swap.
- It calls the same `interviewer.build_plan`, `next_question`, `assessor.assess`, `meter.apply`, `meter.snapshot` and `debrief.build` as the legacy `service.handle_answer`, and `test_hardware_interview.py` runs both on the same answers and compares replies, meter, stored state and debrief.
- A model timeout, an error or bad JSON gives the planned question (`source` is `"fallback"`, `degraded` is true) and no meter penalty (`meter["checked"]` is false when the gap check failed). A gap or a skipped question counts only when its quote is in the candidate's own words.
- `phase` is `interview`, then `walkthrough` (the plan is used up: `done` is true and `reply` is the hand-off line, a good moment for `action='advance'`) or `debrief` (the meter ended a strict interview: `done` and `ended_early` are true, `reply` is the closing line). Further answers after `debrief` raise `InterviewEnded`. Empty or over 5000 character answers raise `BadAnswer`; a state that did not come from `start`/`answer` raises `InvalidState`. All three are `hw.InterviewError` (a `ValueError`).
- `meter` is `None` when no real model is configured (`LLM_PROVIDER` is `fake`), and once `phase` is `walkthrough`.
- Where to keep the state: `sessions.engine_state['hardware_interview']`. It holds the plan, at most 6 answers (each up to 5000 characters) and the replies, and the meter's findings. It is not the transcript of record, keep writing `session_events` as you do now. Deleting the session row deletes it.

The call site. I have not run this against your code, so treat it as a sketch of about 10 lines:

```python
# service.start(), after `scenario=await db.one('SELECT spec ...')`: begin the interview and store the state
if scenario['spec'].get('interviewer')=='hardware_interview':
    r=await hardware_interview.start(scenario['spec']['posting'],scenario['spec']['resume'])
    opening=r['opening']                      # instead of scenario['spec']['prompt']
    engine_state={'hardware_interview':r['state']}   # add engine_state to the INSERT INTO sessions

# service.respond(), at the line `reply,jid,source=await generate('interviewer',sid,prompt,Reply,cached)`
state=(await require_session(sid))['engine_state'].get('hardware_interview')
if state is not None:
    try:r=await hardware_interview.answer(state,text)
    except hardware_interview.InterviewError:return TurnResult(events=[],source='listening')
    reply=Reply(text=r['reply'],action='advance' if r['done'] else 'continue');jid=None;source=r['source']
else:
    reply,jid,source=await generate('interviewer',sid,prompt,Reply,cached)
# later, inside your existing transaction, after the `superseded` check, so a stale reply saves nothing:
#   await c.execute("UPDATE sessions SET engine_state=engine_state||$2 WHERE id=$1",sid,{'hardware_interview':r['state']})
```

Things you need to know before using it:

1. `start()` needs two strings, a job posting and a resume. v2's `Intake` has neither (role, companies, struggles, question, link). For a demo, put a synthetic posting and resume in the scenario spec and label them synthetic (the legacy test page `spikes/voice_check/index.html` has a sample pair), or build the posting from `role` and `companies`.
2. A project interview and the LED debug are two steps of one track: step 0 this interviewer, step 1 `led_reversed.v2.json`. That file is only the debug step. It is data and nothing loads it. `create_plan` inserts a scenario only for `sw.sysdesign`, so `hw.circuit_debug` stays `proposed`. What the format could not express (probes, expected voltages as a check, per-criterion anchors) is in `contracts/examples/led_reversed.v2.md`, and so are my guesses (skill ids, `min_turns`).
3. An early end (`ended_early`) needs the session to end from a non-final step. `engine.action_allowed` only allows `finish` on the last step, so with the stock rules the closing line plays and the session carries on. That is your engine's call.
4. `respond()` sends the whole `spec` to the model, including `circuit.fault` in the LED file. Read a few real turns before showing it.
5. The lane 1 debrief (gaps with the candidate's quotes, strengths, resource links, all `reviewed: false`) is a different shape from your report. Showing it next to your report is the cheapest option; I have not tried to merge them.

How to check, from `backend/`:

```
.venv\Scripts\python -m pytest tests/test_hardware_interview.py tests/test_led_reversed_v2.py -q
.venv\Scripts\python -m pytest -q
```

At the branch tip I measured 83 passed for the first command and 412 passed for the second (329 on `main` at `4f2b84d` before these files), fake providers, no keys and no database. `git diff --stat origin/main..lane1-entrypoint` lists added files only.

## What I need from you
Reply yes or no: will you wire `hardware_interview` into `start()` and `respond()` for one hardware track before noon Central? If yes, name the track and I will write the matching scenario spec (the project interview step with a synthetic posting and resume) as a file under `contracts/examples/` for you to load.

## If you do not reply
I change nothing in v2. The module stays unused, the legacy test page `spikes/voice_check` stays the voice demo and fallback, and I list this as open in my next hourly review.
