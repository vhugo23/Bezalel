# Teammate feature: Behavioral STAR drill

**Ownership:** Joshua requested an independent feature handoff. josh-agent relinquishes `comm.star` to the teammate. This replaces the earlier deployment/CI handoff. Start from current `main`; the required generic session, event log, scenario-specific grading and audited model-call interfaces already exist. The feature does not require the unfinished Pi, circuit, whiteboard, account or deployment work.

## What the candidate can do

Open the catalog's **Behavioral: tell me about a time** track, choose a real experience, tell Dana their story by voice or text, see a live Situation / Task / Action / Result guide, answer a focused follow-up, and receive STAR/ownership/impact coaching whose claims cite actual candidate turn sequences. Keep the existing visible conversation and voice controls. The root `prototype.html` is the visual reference; reuse its light card/indigo style.

The guide must distinguish supplied narrative from missing context. Ask about missing outcomes or individual actions; never fabricate an experience, personal contribution or numerical result. Missing material is unassessed until there is evidence to grade. No memory UI.

## Files reserved for you

- `backend/app/v2/behavioral.py` and `backend/app/v2/behavioral_models.py`
- `frontend/src/components/StarGuide.tsx` and `StarGuide.test.tsx`
- `contracts/behavioral/`
- `backend/tests/test_v2_behavioral.py`
- `frontend/e2e/behavioral.spec.ts`
- `docs/BEHAVIORAL_STAR.md`

I will avoid those files. Do not concurrently edit central `service.py`, `routes.py`, `jobs.py`, `learning.py`, `planning.py`, `models.py`, `Session.tsx`, dependency manifests or migrations. Send the small integration patch/contract with the handoff; I will wire it into the active app. Existing schema already has `star_stories` and `session_stories` if needed; a story-bank management feature is separate from this drill. Stay within your own file set and coordinate anything else.

## Integration contracts

1. Supply a scenario definition for template `comm.star`, engine `behavioral`, with ordered contiguous `steps` from index 0. Use `star` and `voice` surfaces, task/hints/success settings and a scenario-specific rubric. `engine.parse_steps`, `rubrics.load`, `rubrics.dump` and the existing two-step acceptance fixture show the supported format. Use existing skills `comm.star_structure`, `comm.ownership`, `comm.quantifying_impact`, `comm.followups`. Keep prompt/expectations and criterion step restrictions consistent.
2. Expose an async builder in `behavioral.py` taking explicit user/track/context inputs and returning validated scenario content, rubric, validity report and model job IDs. Use `app.v2.generation.generate` for **every** model call, including independent prompt/rubric review. I will attach this builder to the persisted generation queue and atomic publication path. Do not add unaudited SDK calls or publish an unchecked scenario.
3. Expose a live-guide analyzer taking a session ID and candidate events, returning structured S/T/A/R findings. Every finding must include exact candidate quotes and their `session_events.seq`; validate session, candidate actor, turn kind, quote substring and source sequence before returning. Include the audited analysis job ID. I will persist returned findings as system `analysis` events and wire scheduling with bounded/coalesced calls. Avoid calling a model on every partial audio chunk.
4. `StarGuide.tsx` should accept existing typed `Event[]` and render validated `analysis` findings with their source turn numbers, plus neutral prompts for missing sections. Keep interviewer output separate from candidate evidence. The central session shell owns audio/transcript; your component does not open a second microphone or voice socket. Define/export the exact props so I can mount it for `surface==='star'`.
5. Grading uses the existing `RubricEvaluation`/claim/evidence framework. Supply the practice rubric; do not implement a second score pipeline or infer numerical ability from guide completion. Use `quoted_turn` for narrative evidence and preserve same-skill retest compatibility. I retain generalizing central lesson/retest plumbing beyond rate-limiters, and will use your scenario/rubric requirements there.

This split leaves the feature implementation independent and gives us a small, explicit integration seam. You can implement/test the builder, guide, rubric and evidence validation now against synthetic fixtures; I own their registration and the final combined app run.

## Acceptance

- Fresh or already saved transcript yields only exact, cited S/T/A/R excerpts. Unknown sequence, interviewer quote, fabricated impact and cross-session evidence are rejected.
- A real candidate narrative appears in the guide; missing Result prompts clarification rather than inventing a metric. Reload reconstructs the guide from saved events.
- Reviewed scenario/rubric passes the existing validators; malformed or unsupported review output prevents publication. Every provider call is audited.
- Scenario-specific grading produces only evidence-supported claims for its declared skills. Clearly label synthetic/recorded tests and soft conceptual/model review; human grading calibration is still pending.
- Add meaningful adapter/component tests and a browser journey ready to run after registration. No paid-provider loops or real candidate data in tests.

## Handoff back

Provide branch/commit or PR, exact test results, exported function/component signatures and the small central integration changes needed. Joshua authorized iterative pull/verify/push, but follow the repo mailbox identity and STOP rules. Do not spawn another agent or claim a hosted/human-tested result that you did not verify.
