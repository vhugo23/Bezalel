# Human attention needed

Agents append here when they are blocked and cannot safely continue, or when a thread hit the reply limit.
A person reads this first. Add new items at the bottom, one block each, never edit another agent's block.
When you resolve an item, add a line starting `RESOLVED:` under it with the date. Do not delete anything.

Block format:

```
## 2026-10-10T23:30:00Z from hugo-agent, needs: <which human>
What is stuck, in two lines. Link the mailbox message filename and the branch.
What I will do meanwhile.
```

---

## 2026-10-11T05:50:00Z from trey-agent, needs: all four humans (Trey, Josh, Shamah, Hugo)
Nobody has chosen the demo app or the cut list, and submission is due 17:00Z today. The React app on `/api/v2` only runs a software rate-limiter session (hardware tracks are seeded `proposed`); the legacy voice interviewer has the hardware interview, meter and debrief but no real UI and no debug walkthrough. Nothing is deployed, and the Devpost video, description, team names and license have no owner. Detail: `mailbox/REVIEW.md` (05:38Z) and `josh-agent/inbox/20261011-053700_from-trey-agent_scope-versus-deadline.md`.
Also needs a human: confirm Gemini instead of Opus for grading, and fill in the lanes table in `mailbox/README.md`.
Meanwhile trey-agent keeps lane 1 on the legacy path and changes nothing in `backend/app/v2` or `frontend/`.
