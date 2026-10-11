from datetime import datetime
from typing import Literal, Any
from pydantic import BaseModel, Field, ConfigDict

class Intake(BaseModel):
    user_id: str = Field(min_length=1, max_length=100)
    name: str = Field(default='Joshua', max_length=80)
    role: str = Field(min_length=1, max_length=200)
    companies: list[str] = Field(max_length=20)
    struggles: list[str] = Field(max_length=20)
    question: str = Field(max_length=10000)
    link: str = Field(default='', max_length=2000)

class Skill(BaseModel):
    id: str
    domain: str
    name: str
    score: int | None
    target: int
    estimate: bool = False

class Track(BaseModel):
    id: str
    domain: str
    title: str
    summary: str
    layer: int
    ready: bool
    reason: str | None = None
    reason_session_id: str | None = None
    reason_evidence_seq: list[int] = Field(default_factory=list)

class Plan(BaseModel):
    id: str
    intake: Intake
    primary_domain: str
    skills: list[Skill]
    tracks: list[Track]
    source: str

class Start(BaseModel):
    track_id: str
    consent: bool

class EventInput(BaseModel):
    kind: Literal['turn','stroke','step','note','interrupted']
    step: int = Field(default=0, ge=0, le=10)
    payload: dict[str, Any] = Field(default_factory=dict)

class Event(BaseModel):
    session_id: str
    seq: int
    kind: str
    actor: str
    step: int | None
    payload: dict[str, Any]
    ts: datetime

class SessionStep(BaseModel):
    idx: int = Field(ge=0, le=9)
    title: str = Field(min_length=1, max_length=160)
    surface: Literal['voice','whiteboard','star','terminal','editor','schematic','browser','pi3d'] = 'voice'
    task: str = Field(min_length=1, max_length=2000)
    config: dict[str, Any] = Field(default_factory=dict)
    hints: list[str] = Field(default_factory=list, max_length=5)
    success: dict[str, Any] = Field(default_factory=dict)
    rubric_ids: list[str] = Field(default_factory=list)

class Session(BaseModel):
    id: str
    track_id: str
    title: str
    status: str
    step: int
    opening: str
    demo: bool
    events: list[Event]
    board_review: 'BoardResult | None' = None
    domain: str = 'sw'
    engine_id: str = 'conceptual'
    steps: list[SessionStep] = Field(default_factory=list)
    paused: bool = False
    engine_state: dict[str, Any] = Field(default_factory=dict)

class PauseInput(BaseModel):
    paused: bool

class TurnInput(BaseModel):
    text: str = Field(min_length=1, max_length=5000)
    step: int = Field(ge=0, le=10)
    board: bool = False

class Reply(BaseModel):
    text: str = Field(max_length=900)
    action: Literal['continue','advance','look','finish','listen'] = 'continue'

class ReplyAck(BaseModel):
    seq: int = Field(gt=0)

class TurnResult(BaseModel):
    events: list[Event]
    source: str

class Point(BaseModel):
    x: float = Field(ge=0, le=900, allow_inf_nan=False)
    y: float = Field(ge=0, le=540, allow_inf_nan=False)
    pressure: float = Field(default=.5, ge=0, le=1)

class Stroke(BaseModel):
    id: str = Field(min_length=1, max_length=100)
    kind: Literal['path','rect','arrow','text']
    points: list[Point] = Field(min_length=1, max_length=10000)
    label: str = Field(default='', max_length=200)

class Mark(BaseModel):
    model_config = ConfigDict(extra='forbid')
    kind: Literal['circle','arrow','underline','highlight','sticky','cross','check']
    severity: Literal['good','info','probe','problem']
    speech: str = Field(min_length=1, max_length=500)
    target: str

class Critique(BaseModel):
    marks: list[Mark] = Field(max_length=4)

class BoardInput(BaseModel):
    strokes: list[Stroke] = Field(min_length=1, max_length=1000)
    png: str = Field(max_length=6000000)

class Annotation(Mark):
    id: str
    geometry: dict[str, float]
    target_seq: int
    event_seq: int

class BoardResult(BaseModel):
    annotations: list[Annotation]
    source: str
    artifact_id: str

class ClaimDraft(BaseModel):
    text: str = Field(max_length=600)
    polarity: Literal['strength','gap','neutral']
    evidence_seq: list[int] = Field(max_length=20)
    # Exact quotes make the deterministic checker stronger than existence-only checking.
    quotes: list[str] = Field(default_factory=list, max_length=20)
    skill_id: str = 'sw.system_design'
    rule: Literal['quoted_turn','board_explanation','drawing','question'] = 'quoted_turn'

class CheckedClaim(ClaimDraft):
    id: str
    evaluator: str
    check_status: str
    check_reason: str

class Report(BaseModel):
    session_id: str
    status: str
    claims: list[CheckedClaim]
    evaluators: list[dict[str, Any]]
    demo: bool
    overall: int | None = None
    scores: list['SkillScore'] = Field(default_factory=list)
    next_gap: 'GapSummary | None' = None
    partial: bool = False
    rubric_version: str | None = None

class Metrics(BaseModel):
    rows: list[dict[str, Any]]
    hypertables: list[str]
    aggregates: list[str]
    mastery: list[dict[str, Any]] = Field(default_factory=list)

class Health(BaseModel):
    status: str
    schema_version: str
    demo: bool
    voice_ready: bool
    test_environment: bool = False

class PairResult(BaseModel):
    code: str
    session_id: str
    expires_at: datetime

class RetestInput(BaseModel):
    session_id: str

class Lesson(BaseModel):
    id: str | None = None
    title: str = 'Your next practice'
    body: str
    reason: str
    evidence_seq: list[int]
    skill_id: str | None = None
    claim_id: str | None = None
    ai_generated: bool = False
    practice: str = ''
    retest_ready: bool = False

class CriterionDraft(BaseModel):
    model_config = ConfigDict(extra='forbid')
    id: str
    score: int | None = Field(default=None, ge=0, le=4)
    claims: list[ClaimDraft] = Field(default_factory=list, max_length=2)

class RubricEvaluation(BaseModel):
    criteria: list[CriterionDraft] = Field(max_length=8)

class EvidenceDecision(BaseModel):
    index: int = Field(ge=0)
    supported: bool
    reason: str = Field(min_length=1, max_length=300)

class EvidenceReview(BaseModel):
    decisions: list[EvidenceDecision] = Field(max_length=16)

class SkillScore(BaseModel):
    skill_id: str
    name: str
    score: int = Field(ge=0, le=100)
    previous: int | None = None
    delta: int | None = None
    previous_session_id: str | None = None
    previous_evidence_seq: list[int] = Field(default_factory=list)
    claim_ids: list[str]

class GapSummary(BaseModel):
    id: str
    skill_id: str
    text: str
    evidence_seq: list[int]

class LessonDraft(BaseModel):
    title: str = Field(min_length=1,max_length=160)
    explanation: str = Field(min_length=80,max_length=6000)
    practice: str = Field(min_length=20,max_length=2000)
    retest_prompt: str = Field(min_length=40,max_length=2000)
    expectations: list[str] = Field(min_length=1,max_length=4)

class LessonReview(BaseModel):
    supported: bool
    reason: str = Field(min_length=1,max_length=500)

class WorkItem(BaseModel):
    id: str
    kind: str
    subject_id: str
    status: Literal['queued','running','succeeded','failed','cancelled']
    stage: str
    result: dict[str, Any] | None = None
    error: str | None = None
    attempts: int
    created_at: datetime
    updated_at: datetime
    finished_at: datetime | None = None
