"""Resume ATS review and job tailoring.

Gemini rates the resume in the role of an applicant tracking system. Everything
it returns is checked here before it is saved: the score is computed in code,
quotes must be verbatim, and a suggestion that adds a number or a skill the
resume does not contain is dropped. No real ATS is run. See docs/RESUME_ATS.md.

Results live in source_documents.extracted (no table of their own):
  job posting row: extracted['requirements'] = [JobRequirement, ...]
  resume row:      extracted['ats'] = {'general': AtsReview, 'jobs': {job_source_id: AtsReview}}
A source document is immutable, so a saved review never goes stale. Applying
suggestions creates a NEW resume source; the original is never changed.
"""
from .models import (AtsApply, AtsCategoryDraft, AtsCoverage, AtsEvidenceDraft, AtsFacts, AtsReview,
                     AtsSuggestion, AtsSuggestionDraft, JobRequirement, JobScanDraft, SourceDocument, WorkItem)

RUBRIC_VERSION = 'ats-v1'
CATEGORIES = ('format', 'sections', 'keywords', 'impact', 'clarity')
MAX_JOB_REVIEWS = 5  # tailored reviews kept per resume, newest first


def resume_facts(body: str) -> AtsFacts:
    """Deterministic facts: word count, email and phone present, section headings detected."""
    raise NotImplementedError


def validate_requirements(draft: JobScanDraft, posting: str) -> list[JobRequirement]:
    """Keep a requirement only if its quote is in the posting and its term is in that quote. Drop duplicates by term."""
    raise NotImplementedError


def coverage(requirements: list[JobRequirement], resume_body: str, evidence: list[AtsEvidenceDraft]) -> list[AtsCoverage]:
    """One row per requirement. mentioned is a literal case-insensitive match of term in the resume.
    resume_quote is kept only if it is verbatim resume text. status: found (mentioned), evidence
    (not mentioned, valid resume_quote), else missing."""
    raise NotImplementedError


def guard_suggestions(drafts: list[AtsSuggestionDraft], resume_body: str, covered: list[AtsCoverage]) -> tuple[list[AtsSuggestion], int]:
    """Return (accepted, rejected_count). A draft is dropped when: original is not in the resume exactly
    once; it overlaps an accepted suggestion; replacement equals original; replacement contains a number
    absent from the resume; replacement contains the term of a coverage row whose mentioned is False;
    or replacement is longer than 2*len(original)+200. Ids are 0..n-1 in accepted order."""
    raise NotImplementedError


def score(categories: list[AtsCategoryDraft], tailoring: bool) -> tuple[int, dict[str, int]]:
    """(score 0-100, weights). round(100*sum(w*rating)/(4*sum(w))). Weights are 1 each; keywords is 2
    when tailoring. Raises ValueError unless the five CATEGORIES appear exactly once each."""
    raise NotImplementedError


def apply_suggestions(body: str, suggestions: list[AtsSuggestion], ids: list[int]) -> str:
    """Apply the chosen suggestions right to left by saved offset. Raises ValueError on an unknown or
    repeated id, or if body[start:end] no longer equals original."""
    raise NotImplementedError


async def enqueue_scan(source_id: str) -> WorkItem:
    """Queue a job_scan for a job_posting source (422 for any other kind)."""
    raise NotImplementedError


async def scan(row) -> dict:
    """job_scan handler (called by jobs.handle). Publishes extracted['requirements']."""
    raise NotImplementedError


async def enqueue_review(resume_id: str, job_id: str | None) -> WorkItem:
    """Queue an ats_review for a resume source (422 for any other kind). With job_id: the job must be a
    job_posting of the SAME user (422 otherwise) and already scanned (409 otherwise)."""
    raise NotImplementedError


async def review(row) -> dict:
    """ats_review handler (called by jobs.handle). Publishes extracted['ats']."""
    raise NotImplementedError


async def read_review(resume_id: str, job_id: str | None) -> AtsReview | None:
    """The saved general review, or the saved review tailored to job_id. None if there is none."""
    raise NotImplementedError


async def apply(resume_id: str, body: AtsApply) -> SourceDocument:
    """Create a new resume source from the saved review's chosen suggestions. 409 if no review is saved."""
    raise NotImplementedError
