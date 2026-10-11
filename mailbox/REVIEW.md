# Mailbox review

Written by a scheduled review in Trey's Claude Code session, about every hour while that session is open.
Newest review first. This file reports, it does not give orders. Judged against `CONTEXT.md` and the lanes in `mailbox/README.md`.

---

## 2026-10-11T07:35Z, at commit b0a9038

**Verdict: josh-agent is on task for what Joshua asked of it and has been cooperative. No drift to correct. The open risk is unchanged: the hardware demo is not joined up and nobody has chosen the demo.**

### What I looked at
- `mailbox/STOP`: not present. Inboxes: all empty. `mailbox/HUMAN.md`: Trey confirmed Gemini for grading and said the cut list and demo choice are coming.
- Live sessions on Trey's machine: none besides this one.
- `git fetch --all`: `main` current. Open pull requests: #11 and #12 (both already on `main` through #13) and #14.
- Commits since the last review: 9 code commits by Joshua Eworo, 15 by Trey (lane 1, merged through #13), and mailbox commits.
- Tests on `main` at this commit: backend `pytest` 526 passed (stubbed models, database forced off). Frontend `npm test` 16 passed, `npm run build` succeeded, Node 24.20. First time the frontend was run on this machine.
- `STATUS.md`: josh-agent 07:19Z. hugo-agent and shamah-agent still "not yet".

### josh-agent
- Answered every trey-agent message that asked for a reply (four) within minutes, each with a concrete decision.
- Fixed the `.env` path regression (`c891d23`) the review before this one reported.
- Landed scenario-driven sessions, recoverable lessons, intake sources, generated plans, memory, and whiteboard review safety with QR pairing and reconnect (`df324f1`).
- Checked in `df324f1` by reading: the QR library is in `package.json`, no `crypto.randomUUID` call is left in `frontend/src`, and `docs/WHITEBOARD_DEVICES.md` gives the LAN steps and says no physical iPad test was done. I did not run its browser journeys.
- Agreed to wire lane 1's `hardware_interview` and the two-step scenario into `hw.circuit_debug`, non-strict by default, and to keep the planted fault out of prompts. Not started; it is on Pi and engine work first and promises nothing for noon.
- Handed the Behavioral STAR drill to "Joshua's teammate" with reserved files. No agent has claimed it.
- Still pushes code straight to `main`, on Joshua's instruction. Still no cut list.
- Stayed out of lane 1 files.

### trey-agent (for the other agents' reference)
Entry point, backup model and two-step hardware scenario are on `main`. Circuit symbol stamps are in pull request #14, a library with no tool button. Trey has paused further lane 1 work; this review continues.

### hugo-agent, shamah-agent
No commits, no mailbox activity. Nothing to judge.

### For a human to decide
1. Which app is the demo, and what is cut. Still the most important open item.
2. Who owns the submission: video, screenshots, team names, license, and applying the README draft in `spikes/drafts/`.
3. Who takes the STAR drill, if anyone.
4. Someone has to try pairing on a real iPad.

### Messages sent
None this hour. Nothing needed correcting.

### Limits of this review
- I read file lists, the device notes and a few diffs. I did not read all of josh-agent's 9 commits.
- Passing tests use stubbed models and no database. josh-agent's Tiger Data, browser and live-provider checks are its own reports.

---

## 2026-10-11T05:38Z, at commit b1d5939

**Verdict: one agent active (josh-agent), working hard but drifting from the deadline. One regression. Two messages sent.**

### What I looked at
- `mailbox/STOP`: not present. `mailbox/HUMAN.md`: no blocks.
- Live sessions on Trey's machine: none besides this one. The other agents are only visible through git.
- `git fetch --all`: `main` was already current. No new branches, no open pull requests (#1 to #8 all merged).
- Commits since the last review: 3, all Joshua Eworo. 9399673 is code (73 files, about 15,000 lines). a28db29 and b1d5939 are his STATUS updates.
- `STATUS.md`: josh-agent updated (05:24Z). hugo-agent and shamah-agent still "not yet".
- Tests at this commit: `pytest` in `backend/`, 321 passed, after installing the four new packages in `requirements.txt`. This matches the number in Josh's commit message. Frontend tests not run here (no Node on this machine).
- Key-shaped strings in the added lines: none found. Only `.env.example` files were added, with blank values.

### josh-agent
Built a React frontend (`frontend/`), a second backend path (`backend/app/v2`, `/api/v2`), Alembic migrations and a product roadmap (`docs/IMPLEMENTATION_ROADMAP.md`).
- **Scope against the deadline.** The roadmap has 11 phases and 12 tracks. STATUS says "implementing all roadmap slices iteratively", next "generic sessions". Submission is due noon Central today. Asked for a cut list.
- **Regression.** `backend/app/config.py` now reads `.env` from the repo root, not `backend/.env`. On this machine the backend starts with no keys and falls back to fake providers without an error. Asked for a fix.
- **Process.** Code went straight to `main` with no pull request. His lane is still unassigned, and the commit changed shared files (`main.py`, `config.py`, `conftest.py`, `README.md`, `.gitignore`).
- **Direction.** The React app uses only `/api/v2`, which has its own voice loop. The lane 1 work from pull requests #4 to #7 (patience meter, assessor, debrief, humanlike persona) is not reachable from it. The one working v2 session is a software rate-limiter design; the brief is hardware and embedded.
- Did not touch lane 1 files.

### hugo-agent, shamah-agent
No commits, no mailbox activity. Nothing to judge.

### For a human to decide
1. **Which app is the demo:** the React app on `/api/v2`, or the legacy voice interviewer. Today they do not share the interviewer, meter or debrief.
2. **What gets cut** from the roadmap before noon.
3. Still open from the last review: confirm Opus to Gemini for grading, and fill in the lanes table (shamah has done backend and data, josh frontend and v2).

### Messages sent
- `josh-agent/inbox/20261011-053600_from-trey-agent_env-path-change.md`
- `josh-agent/inbox/20261011-053700_from-trey-agent_scope-versus-deadline.md`

### Limits of this review
- I read the file list, the diffs to shared files and the roadmap. I did not read all of `backend/app/v2` or the frontend source.
- "321 passed" uses fake providers and no database. Josh's live Gemini and Tiger checks are his claims; I did not repeat them.

---

## 2026-10-11T04:58Z, at commit fe2293f

**Verdict: on track. No serious drift. Three things for a human to confirm.**

### What I looked at
- `mailbox/STOP`: not present.
- `mailbox/HUMAN.md`: no blocks.
- All four `STATUS.md` files: none updated yet ("not yet").
- Inboxes: all empty. No agent has sent a message.
- Commits in the last hour: 2, both by Trey, both mailbox setup (465f5cc, fe2293f). No code.
- Because this is the first review, I also read the 9 commits from the 3 hours before that, all by shamahamichoh.
- Tests on this commit: `pytest` in `backend/`, 254 passed, run at review time.
- Open pull requests: none.

### What the earlier commits did
All backend and data work: Tiger time-series tables, Backboard memory across sessions, a database fix for a fresh install, removal of unused endpoints, templates and the OpenAI provider, and a change of the grading model.
None of them touched the lane 1 files (`interviewer.py`, `assessor.py`, `meter.py`, `debrief.py`, `core/voice.py`, `spikes/`).
`.mcp.json` was added. It holds one documentation URL and no keys.

### For a human to confirm
1. **Grading moved from Opus to Gemini** (commit 0ede90a). The README now says evaluators use Gemini through `EVALUATOR_MODEL`, and `ANTHROPIC_API_KEY` is gone from the key list. The original brief and `CONTEXT.md` (items 9 and "next steps" 4) both name Opus for grading. This looks deliberate, but it changes the plan, so someone should say it is the agreed direction.
2. **The lanes table is probably wrong.** `mailbox/README.md` gives lane 3 (backend and data) to hugo-agent. That was an assumption. The commit history shows shamahamichoh doing the backend and data work (14 commits) and Hugo with 1 commit. Agents use this table to decide whose files they may edit, so it should be corrected before any agent relies on it.
3. **`CONTEXT.md` is out of date.** It lists memory for session two and the Tiger time-series tables as not built, and says the backend never ran against a real Postgres. Memory and the time-series tables are now in the repo. I did not check whether the new Tiger smoke test has been run against a real database.

### What a human should do
- Confirm or reverse the Opus to Gemini change.
- Fill in the lanes table for all four agents.
- Ask the owner of `CONTEXT.md` (trey-agent) to refresh the "not built" and "next steps" sections.

### Limits of this review
- No agent has used the mailbox yet, so there was no agent behaviour to judge. This review covers human commits only.
- I read commit messages, file lists and the README diff. I did not read every changed line of the 9 earlier commits.
- "254 passed" says the tests pass. It does not say the new memory and time-series code works against real services.
