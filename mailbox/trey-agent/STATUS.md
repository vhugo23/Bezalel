updated: 2026-10-11T16:17:14Z
branch: resume-ats (new, from main c5d6046, will be a pull request). Also quit-lesson (pushed, f7cfe92, not yet a pull request).
doing: resume ATS review and job tailoring, asked for by Trey. New Resume page, Gemini review with a score computed in code, checked suggestions the user can apply, job posting scan and tailoring, PDF export.
next: independent review, docs/RESUME_ATS.md, pull request
blocked_on: nothing
touching: backend/app/v2/{routes,models,jobs,generation}.py; backend/requirements.txt; frontend/src/{main.tsx,styles.css}; frontend/src/components/{Shell,SourceManager}.tsx; frontend/src/api/client.ts; frontend/openapi.json and generated frontend/src/api/{types,schemas}.ts. New files: backend/app/v2/{resume,resume_pdf}.py, frontend/src/pages/Resume.tsx.