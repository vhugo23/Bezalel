from pydantic import BaseModel


class PlanRequest(BaseModel):
    job_posting: str
    resume: str


class PlanResponse(BaseModel):
    plan_id: str
    topics: list[str]
    questions: list[str]


class SessionStartRequest(BaseModel):
    plan_id: str


class SessionStartResponse(BaseModel):
    session_id: str
    voice_token: str | None = None


class TurnRequest(BaseModel):
    answer: str


class TurnResponse(BaseModel):
    next_question: str


class ProbeRequest(BaseModel):
    node: str


class ProbeResponse(BaseModel):
    node: str
    reading: str


class EvaluatorResult(BaseModel):
    evaluator: str
    topic_id: str
    score: float
    evidence: str
    duration_ms: int


class EndSessionResponse(BaseModel):
    session_id: str
    results: list[EvaluatorResult]
    gaps: list[str]


class ReportResponse(BaseModel):
    session_id: str
    results: list[EvaluatorResult]
    gaps: list[str]


class LessonResponse(BaseModel):
    topic: str
    body: str
    ai_generated: bool = True


class RetestRequest(BaseModel):
    topics: list[str]


class RetestResponse(BaseModel):
    retest_id: str
    topics: list[str]


class SeasonResponse(BaseModel):
    mastery: list[dict]
    applications: list[dict]
