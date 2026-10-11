# Resume check and job tailoring

The Resume page (`/resume`) reviews a resume the way an applicant tracking system (ATS) screener might, suggests wording changes the user can apply, and can tailor the resume to a job posting.

**No real ATS is run.** The review is one Gemini call plus local checks. The UI says so next to the score.

## What the user can do

1. Add a resume at intake ("Add context") or later on the Resume page: pasted text, TXT, Markdown or a text PDF.
2. **Check my resume**: get a score out of 100, five category ratings with quoted findings, and suggested changes.
3. Tick the changes they want and **Apply selected**. This creates a new, revised resume. The original is never changed.
4. Copy the revised text, download it as Markdown, or download a plain PDF.
5. Add a job posting. It is scanned for requirements, then the page offers to tailor the resume to it.

## How the score is produced

Gemini rates five categories from 0 to 4: `format`, `sections`, `keywords`, `impact`, `clarity`. The score is then computed in code (`resume.score`):

    score = 100 × Σ weight × rating / (4 × Σ weight), rounded half up

Every weight is 1. When tailoring to a job, `keywords` has weight 2.

These weights are hand-picked and **have not been validated** against any real ATS or any hiring outcome. Treat the score as a rough guide to the review's own findings, not a prediction.

## What is checked before anything is shown

The model's output is treated as a draft. `backend/app/v2/resume.py` checks it:

| Model output | Local check | If it fails |
|---|---|---|
| A finding's quote | Must be verbatim resume text | The quote is removed, the finding stays |
| A job requirement | Its quote must be in the posting and its keyword must be a word of that quote | Dropped |
| "Mentioned" for a requirement | Not taken from the model: a literal keyword match against the resume. Case is ignored, except for a short capitalised name such as "Go" or "AI" | n/a |
| Evidence for a requirement | Must be verbatim resume text | Discarded |
| A suggested change | See below | Dropped and counted |

A suggested change is checked against the resume **as it would read after the edit**, not against the replacement text alone. It is dropped when:

- its original text is blank or not in the resume exactly once, or it overlaps or touches another accepted change;
- its replacement is the same as the original, far longer than it, or uses a character the resume does not (this stops look-alike letters and invisible characters);
- the edited resume would contain a **number** the resume does not have. A number is the whole token it is written in, so `5` → `15`, `0.5%` → `5%` and `12` → `12k` are all new numbers. The same years written as a range (`2021 - 2024` → `2021 to 2024`) are allowed;
- the edited resume would contain a new **name**: a new word that is capitalised mid-sentence, mixed-case, all capitals or alphanumeric, such as a tool, an employer, a job title or a degree. New ordinary words are allowed;
- when tailoring, the edited resume would mention a **requirement the resume lacks** more often than before, as a word or inside a variant (`Dockerized`, `MySQL`, `Golang`, `CAN-bus`).

When changes are applied, the chosen set is checked together once more, and refused if the combination adds any of the above.
The page shows how many suggestions were dropped.

## Missing skills are flagged, never added

If a posting asks for something the resume does not show, the coverage table marks it "Not on your resume" with a link to practise it. There is no control to add it, and the guard above stops a suggestion from slipping it in. Tailoring only rewords and reorders what the resume already says.

## Storage

No table of its own. Results live in `source_documents.extracted`:

- job posting row: `extracted.requirements`
- resume row: `extracted.ats.general`, and `extracted.ats.jobs[<job posting id>]` for tailored reviews (the five newest are kept)

Source documents are immutable, so a saved review never goes stale. A revised resume is a new source whose `extracted.origin` records the parent resume, the job and the applied change ids.

## Routes

All under `/api/v2/sources/{id}/`, so the existing ownership check applies.

| Route | Purpose |
|---|---|
| `POST …/scan` | Queue a requirements scan of a job posting |
| `POST …/ats` | Queue a review of a resume; `{job_id}` tailors it |
| `GET …/ats[?job_id=]` | The saved review, or `null` |
| `POST …/ats/apply` | Create a revised resume from chosen change ids |
| `GET …/pdf` | The resume as a plain PDF |

Scans and reviews run in the durable work queue (`jobs.py`, kinds `job_scan` and `ats_review`) and use `EVALUATOR_MODEL`.

## Limits

- The score is an AI estimate. Nothing here has been compared with a real ATS.
- The ratings come from the model, so the same resume can score differently on two runs. Two tailored runs on one synthetic resume and posting gave 79 and 67.
- The checks catch new numbers, new names and missing keywords. They cannot judge meaning: "Assisted with" rewritten as "Led", a claim added in ordinary lower-case words, a number spelled out, or a number that is elsewhere in the resume reused in a new place all pass. Every change is shown before and after, and the user chooses which to apply.
- A tool written in lower case ("docker") is an ordinary word to the name check. When tailoring, the requirement check still catches it if the posting asks for it.
- "AI matched other wording" in the coverage table means the model quoted real resume text as evidence. The quote is verified to be in the resume; whether it shows the skill is the model's judgment.
- An uploaded PDF is kept as extracted text only. The generated PDF uses a plain one-column template and will not look like the original.
- The bundled PDF font (DejaVu Sans) has no Chinese, Japanese or Korean glyphs; those characters print as `?`.
- Scanned or encrypted PDFs and job posting URLs are not supported. Paste the text.
- A posting that offers alternatives ("FreeRTOS or Zephyr") is scanned as one requirement per skill, so the one the candidate lacks is listed as missing.
- In recorded demo mode (`DEMO_MODE=true`) a review has no score, no ratings and no suggestions, a scan finds no requirements, and neither replaces a real result already saved.
- A posting with no requirements found cannot be tailored to; it can be scanned again.
- Resume and posting text are sent to Gemini and kept in `generation_jobs.request`, as source extraction already does.

## Checks

    # from backend/, database forced off
    python -c "import os,sys,pytest; os.environ['DATABASE_URL']=''; sys.exit(pytest.main(['-q','tests/test_v2_resume.py','tests/test_v2_resume_pdf.py']))"
    # from frontend/
    npm test
    # from the repo root: one paid Gemini check with a synthetic resume and posting, in a disposable
    # database schema that is dropped afterwards; never run by the normal tests
    PYTHONPATH=backend python backend/scripts/verify_live_ats.py --live

## Measured once (2026-10-11, one laptop, `gemini-3.5-flash-lite`, synthetic resume and posting)

Not a benchmark: one run of `verify_live_ats.py --live`.

| Call | Latency | Tokens in / out |
|---|---|---|
| `job_scan` | 3150 ms | 299 / 226 |
| `ats_review` (tailored) | 3206 ms | 1256 / 749 |

Gemini accepted both schemas on the first attempt. Six requirements were kept, three suggestions accepted and none rejected. Billed cost was not available from the response.

With `EVALUATOR_MODEL` unset the review falls back to `GEMINI_MODEL`. On this machine that was `gemini-3.8-flash`, and one scan with it failed after two attempts (about 83 s in total). Set `EVALUATOR_MODEL=gemini-3.5-flash-lite`.
