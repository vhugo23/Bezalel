from pydantic import BaseModel, Field


class PlanRequest(BaseModel):
    job_posting: str = Field(min_length=1, max_length=20000)
    resume: str = Field(min_length=1, max_length=20000)


class PlanResponse(BaseModel):
    plan_id: str
    project: str = ""
    topics: list[str]
    questions: list[str]
    degraded: bool = False  # True when the model plan failed and generic questions were used


class SessionStartRequest(BaseModel):
    plan_id: str
    user_id: str | None = None


class SessionStartResponse(BaseModel):
    session_id: str
    state: str = "interview"
    opening: str = ""
    voice_token: str | None = None


class TurnRequest(BaseModel):
    answer: str = Field(max_length=5000)


class TurnResponse(BaseModel):
    next_question: str
    answer_id: str = ""
    done: bool = False  # True when the interview part is over and the walkthrough starts
    degraded: bool = False  # True when the model failed and the planned question was used
    source: str = "model"  # model | fallback | fake. Only "model" was written by the live model


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
