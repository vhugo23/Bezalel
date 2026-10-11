# Mailbox review

Written by a scheduled review in Trey's Claude Code session, about every 2 hours while that session is open.
Newest review first. This file reports, it does not give orders. Judged against `CONTEXT.md` and the lanes in `mailbox/README.md`.

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
