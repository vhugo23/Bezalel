"""Live interview logic: build the plan from posting + resume, then pick the next question.
No grading here. Grading happens after the session (evaluators.py).

The live path never fails the user: if the model errors or times out, the next planned
question is asked instead and the turn is marked degraded."""
import asyncio

from pydantic import BaseModel

from app import config
from app.core import ai

MAX_ANSWERS = 6  # candidate answers before the interview hands off to the circuit walkthrough

PERSONA = (
    "You are a hardware engineering interviewer. Speak in short natural turns, one question at a time, "
    "with contractions and a brief acknowledgment of what the candidate just said. "
    "Refer to a specific detail from their last answer. Do not grade or praise. Do not give answers."
)

FALLBACK_QUESTIONS = [
    "Walk me through a project from your resume that you're proud of.",
    "What was the hardest problem you hit on it, and how did you find the cause?",
    "What would you do differently if you built it again?",
]


class PlanDraft(BaseModel):
    project: str
    topics: list[str]
    questions: list[str]


async def build_plan(job_posting: str, resume: str) -> dict:
    """Returns {project, topics, questions, degraded}. degraded is True when the model plan failed
    and generic questions were used instead."""
    prompt = (
        "From this hardware job posting and resume, pick ONE resume project to open the interview on. "
        'Reply with JSON only: {"project": str, "topics": [str], "questions": [str]}. '
        "topics are skills the posting wants that the interview should probe. "
        "questions are 4 to 6 interview questions, the first about the chosen project.\n\n"
        f"JOB POSTING:\n{job_posting}\n\nRESUME:\n{resume}"
    )
    try:
        plan = await asyncio.wait_for(
            ai.generate_json(prompt, model=PlanDraft, system=PERSONA), timeout=config.TASK_TIMEOUT_SECONDS
        )
        if plan["questions"]:
            return {**plan, "degraded": False}
    except Exception:  # model error, timeout, bad JSON after retry, or not implemented
        pass
    return {"project": "", "topics": [], "questions": list(FALLBACK_QUESTIONS), "degraded": True}


def _planned(plan: dict, n_answers: int) -> str:
    qs = plan["questions"]
    return qs[min(n_answers, len(qs) - 1)]


async def next_question(plan: dict, turns: list[dict]) -> tuple[str | None, bool]:
    """turns holds interviewer and candidate turns so far, the newest being a candidate answer.
    Returns (question, degraded). question is None when the interview part is over."""
    n_answers = sum(1 for t in turns if t["role"] == "candidate")
    if n_answers >= MAX_ANSWERS:
        return None, False
    if config.LLM_PROVIDER == "fake":
        return f"Got it. {_planned(plan, n_answers)}", False

    history = "\n".join(f"{t['role'].capitalize()}: {t['text']}" for t in turns[-8:])
    prompt = (
        f"Opening project: {plan.get('project') or 'one from their resume'}.\n"
        f"Planned questions, in order: {plan['questions']}\n\n"
        f"Conversation so far:\n{history}\n\n"
        "Ask the next question. Follow up on their last answer if it left something unclear, "
        "otherwise move to the next planned question. Reply with the spoken line only."
    )
    try:
        text = await asyncio.wait_for(ai.generate_text(prompt, PERSONA), timeout=config.TASK_TIMEOUT_SECONDS)
        text = text.strip()
        if text:
            return text, False
    except Exception:  # model error, timeout, or not implemented: never fail the live turn
        pass
    return _planned(plan, n_answers), True
