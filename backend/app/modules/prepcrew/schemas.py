"""Request/response shapes. Source of truth for the frontend is /openapi.json (generated from these).
Shapes follow contracts/api.md, contracts/probe_event.schema.json and contracts/evaluator_output.schema.json."""
from typing import Literal

from pydantic import BaseModel, Field


class Requirement(BaseModel):
    id: str
    text: str
    level: Literal["required", "preferred"]


class MeterState(BaseModel):
    score: float
    threshold: float
    level: Literal["ok", "wrapping_up", "ended"]
    unanswered: int = Field(default=0, description="Questions the candidate ignored so far.")
    checked: bool = Field(default=True, description="False when the check could not run for the latest answer (model error or timeout), so nothing was judged.")


# ---- plans ----
class PlanRequest(BaseModel):
    job_posting: str = Field(min_length=1, max_length=20000)
    resume: str = Field(min_length=1, max_length=20000)
    user_id: str | None = None


class PlanResponse(BaseModel):
    plan_id: str
    topics: list[str]
    questions: list[str]
    scenario_ids: list[str]
    project: str = ""
    requirements: list[Requirement] = Field(default_factory=list, description="Skills from the posting. Empty means the patience meter is off.")
    degraded: bool = Field(default=False, description="True when the model plan failed and generic questions were used.")


# ---- sessions ----
SessionKind = Literal["interview", "retest"]
SessionState = Literal["intake", "interview", "walkthrough", "drill", "debrief", "lesson", "retest"]


class SessionStartRequest(BaseModel):
    plan_id: str
    user_id: str
    consent: bool = Field(description="Must be true. Sessions without consent are rejected.")
    strict: bool = Field(default=True, description="False: the patience meter wraps the interview up but never ends it. For demos and testers.")


class SessionStartResponse(BaseModel):
    session_id: str
    kind: SessionKind
    pair_code: str = Field(description="Short code the iPad enters to join /ws/board/{session_id}.")
    voice_token: str | None = None
    strict: bool = True
    state: SessionState = "intake"
    opening: str | None = Field(default=None, description="First interviewer question, interview sessions only.")


class TurnRequest(BaseModel):
    answer: str = Field(max_length=5000)


class TurnResponse(BaseModel):
    answer_id: str
    next_question: str
    done: bool = Field(default=False, description="True on the turn that ends the interview part; the walkthrough follows.")
    degraded: bool = Field(default=False, description="True when the model failed and a planned question was used.")
    source: str = Field(default="model", description="model | fallback | fake | scripted. Only 'model' was written by the live model.")
    ended_early: bool = Field(default=False, description="True when the patience meter ended the interview. The session is then in debrief.")
    meter: MeterState | None = Field(default=None, description="Null only when no real model is in use (fake provider).")


# ---- probe events (contracts/probe_event.schema.json) ----
ProbeAction = Literal["probe_voltage", "probe_continuity", "swap_part", "isolate_section", "power_cycle"]


class ProbeRequest(BaseModel):
    """Client sends the action only. seq, value and t are always set by the server."""
    action: ProbeAction = "probe_voltage"
    node: str | None = None
    scenario_id: str | None = Field(default=None, description="Defaults to the session's current scenario.")


class ProbeEvent(BaseModel):
    event_id: str
    seq: int
    t: str
    session_id: str
    scenario_id: str
    action: ProbeAction
    node: str | None = None
    value: float | None = None
    unit: Literal["V", "ohm", "none"] = "none"


# ---- grading (contracts/evaluator_output.schema.json) ----
class EndSessionResponse(BaseModel):
    status: Literal["grading"]
    session_id: str
    events_url: str


class CriterionResult(BaseModel):
    id: str
    score: int = Field(ge=0)
    evidence_quote: str
    evidence_span: list[int] = Field(min_length=2, max_length=2)
    rationale: str = Field(max_length=600)


class EvaluatorOutput(BaseModel):
    answer_id: str
    rubric_id: str
    criteria: list[CriterionResult] = Field(min_length=1)
    skill_flags: list[str]
    confidence: float = Field(ge=0, le=1)
    needs_review: bool = False


class ReportResponse(BaseModel):
    session_id: str
    status: Literal["not_ended", "grading", "graded"]
    results: list[EvaluatorOutput]
    skill_flags: list[str]


# ---- curriculum ----
class SkillNode(BaseModel):
    skill_id: str
    title: str
    prerequisites: list[str]
    mastery: float | None = Field(default=None, description="0..1, null when never graded")


class SkillsResponse(BaseModel):
    user_id: str | None
    nodes: list[SkillNode]


class LessonResponse(BaseModel):
    skill_id: str
    body: str
    ai_generated: bool = True


class RetestRequest(BaseModel):
    session_id: str
    skill_ids: list[str]


class MasteryPoint(BaseModel):
    day: str
    mastery: float
    n: int


class MasterySeries(BaseModel):
    skill_id: str
    points: list[MasteryPoint]


class MasteryResponse(BaseModel):
    user_id: str
    series: list[MasterySeries]


# ---- metrics (measured values only) ----
class MetricsResponse(BaseModel):
    session_id: str
    stt_ms: float | None = None
    llm_first_token_ms: float | None = None
    tts_first_audio_ms: float | None = None
    turn_total_ms: float | None = None
    evaluator_fleet_ms: float | None = None
    samples: int = 0


class DeleteResponse(BaseModel):
    session_id: str
    deleted_rows: int
