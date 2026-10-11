import json
import math
from datetime import datetime
from typing import Literal, Any
from pydantic import BaseModel, Field, ConfigDict, model_validator

class Intake(BaseModel):
    user_id: str = Field(min_length=1, max_length=100)
    name: str = Field(default='Joshua', max_length=80)
    role: str = Field(min_length=1, max_length=200)
    companies: list[str] = Field(max_length=20)
    struggles: list[str] = Field(max_length=20)
    question: str = Field(max_length=10000)
    link: str = Field(default='', max_length=2000)
    source_ids: list[str] = Field(default_factory=list, max_length=10)

class Skill(BaseModel):
    id: str
    domain: str
    name: str
    score: int | None
    target: int
    estimate: bool = False

class TrackFocus(BaseModel):
    """A checked retest waiting on this track: its next run uses the changed scenario for this gap."""
    gap: str
    lesson_title: str | None = None
    session_id: str | None = None
    evidence_seq: list[int] = Field(default_factory=list)

class Track(BaseModel):
    id: str
    domain: str
    title: str
    summary: str
    layer: int
    ready: bool
    reason: str | None = None
    recommended: bool = False
    priority_reason: str | None = None
    next_focus: TrackFocus | None = None

class Plan(BaseModel):
    id: str
    intake: Intake
    primary_domain: str
    skills: list[Skill]
    tracks: list[Track]
    source: str
    foundations: list[dict[str,str]] = Field(default_factory=list)

class Start(BaseModel):
    track_id: str
    consent: bool

class HistoryEntry(BaseModel):
    id: str
    title: str
    status: str
    step: int
    created_at: datetime
    ended_at: datetime | None=None

class History(BaseModel):
    latest_plan_id: str | None=None
    sessions: list[HistoryEntry]=Field(default_factory=list)
    next_cursor: str | None=None

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

class LabAction(BaseModel):
    model_config = ConfigDict(extra='forbid')
    request_id: str = Field(pattern=r'^[a-zA-Z0-9_-]{16,100}$')
    revision: int = Field(ge=0)
    step: int = Field(ge=0,le=9)
    kind: Literal['command','edit','part','browser']
    text: str = Field(min_length=1,max_length=10000)

    @model_validator(mode='after')
    def bounded_action(self):
        limit=6000 if self.kind=='edit' else 500
        if len(self.text)>limit:raise ValueError('Simulator action is too long')
        return self

class Point(BaseModel):
    x: float = Field(ge=0, le=900, allow_inf_nan=False)
    y: float = Field(ge=0, le=540, allow_inf_nan=False)
    pressure: float = Field(default=.5, ge=0, le=1)

class Stroke(BaseModel):
    id: str = Field(min_length=1, max_length=100)
    kind: Literal['path','rect','arrow','text']
    points: list[Point] = Field(min_length=1, max_length=10000)
    label: str = Field(default='', max_length=200)

# Excalidraw element types a candidate can draw. Images, frames and embeds are
# disabled in the editor and refused here.
BOARD_TYPES = {'rectangle','diamond','ellipse','arrow','line','freedraw','text'}
LINEAR_TYPES = {'arrow','line','freedraw'}

def _finite(value, limit=1e6):
    return isinstance(value,(int,float)) and not isinstance(value,bool) and math.isfinite(value) and abs(value)<=limit

class BoardElement(BaseModel):
    """One saved version of an Excalidraw element. A later version of the same id
    replaces it; `isDeleted` versions remove it from the board."""
    model_config = ConfigDict(extra='forbid')
    id: str = Field(pattern=r'^[A-Za-z0-9_-]{1,100}$')
    version: int = Field(ge=1, le=2_000_000_000)
    element: dict[str, Any]

    @model_validator(mode='after')
    def bounded_element(self):
        e=self.element
        if e.get('id')!=self.id or e.get('version')!=self.version:raise ValueError('Element id and version must match the element')
        if e.get('type') not in BOARD_TYPES:raise ValueError('Unsupported board element')
        if not isinstance(e.get('isDeleted'),bool):raise ValueError('Element deletion state is required')
        if not all(_finite(e.get(k)) for k in ('x','y','width','height','angle')) or e['width']<0 or e['height']<0:raise ValueError('Invalid element geometry')
        if e.get('customData') is not None:raise ValueError('Custom element data is not accepted')
        if e.get('link') is not None and not (isinstance(e['link'],str) and len(e['link'])<=500 and e['link'].startswith(('https://','http://'))):raise ValueError('Invalid element link')
        if e.get('containerId') is not None and not (isinstance(e['containerId'],str) and len(e['containerId'])<=100):raise ValueError('Invalid text container')
        if e['type'] in LINEAR_TYPES:
            points=e.get('points')
            if not isinstance(points,list) or not 1<=len(points)<=10000 or not all(isinstance(p,list) and len(p)==2 and _finite(p[0]) and _finite(p[1]) for p in points):raise ValueError('Invalid element points')
        if e['type']=='text' and not (isinstance(e.get('text'),str) and len(e['text'])<=2000 and len(str(e.get('originalText','')))<=2000):raise ValueError('Invalid element text')
        if len(json.dumps(e,separators=(',',':')))>300_000:raise ValueError('Element is too large')
        return self

    @property
    def deleted(self)->bool:return self.element['isDeleted']

    def bounds(self):
        e=self.element
        if e['type'] in LINEAR_TYPES:
            xs=[e['x']+p[0] for p in e['points']];ys=[e['y']+p[1] for p in e['points']]
            return min(xs),min(ys),max(xs),max(ys)
        x,y,w,h,a=e['x'],e['y'],e['width'],e['height'],e['angle']
        if not a:return x,y,x+w,y+h
        cx,cy=x+w/2,y+h/2
        corners=[(cx+dx*math.cos(a)-dy*math.sin(a),cy+dx*math.sin(a)+dy*math.cos(a)) for dx in (-w/2,w/2) for dy in (-h/2,h/2)]
        return min(c[0] for c in corners),min(c[1] for c in corners),max(c[0] for c in corners),max(c[1] for c in corners)

class BoardElementsInput(BaseModel):
    step: int = Field(ge=0, le=9)
    elements: list[BoardElement] = Field(min_length=1, max_length=200)

class Mark(BaseModel):
    model_config = ConfigDict(extra='forbid')
    kind: Literal['circle','arrow','underline','highlight','sticky','cross','check']
    severity: Literal['good','info','probe','problem']
    speech: str = Field(min_length=1, max_length=500)
    target: str

class Critique(BaseModel):
    marks: list[Mark] = Field(max_length=4)

class BoardInput(BaseModel):
    elements: list[BoardElement] = Field(min_length=1, max_length=2000)
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
    stroke_ids: list[str] = Field(default_factory=list)

class ClaimDraft(BaseModel):
    text: str = Field(max_length=600)
    polarity: Literal['strength','gap','neutral']
    evidence_seq: list[int] = Field(max_length=20)
    # Exact quotes make the deterministic checker stronger than existence-only checking.
    quotes: list[str] = Field(default_factory=list, max_length=20)
    skill_id: str = 'sw.system_design'
    rule: Literal['quoted_turn','board_explanation','drawing','question','tool_action'] = 'quoted_turn'

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
    validation_label: str = 'Model-reviewed conceptual exercise; no deterministic correctness guarantee'

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

SourceKind = Literal['resume','repo','job_posting','notes','other']

class SourceInput(BaseModel):
    user_id: str = Field(min_length=1,max_length=100)
    kind: SourceKind = 'notes'
    title: str = Field(min_length=1,max_length=160)
    body: str = Field(min_length=10,max_length=60000)

class SourceLinkInput(BaseModel):
    user_id: str = Field(min_length=1,max_length=100)
    url: str = Field(min_length=1,max_length=2000)

class SourceFactDraft(BaseModel):
    model_config = ConfigDict(extra='forbid')
    category: Literal['project','technology','question','requirement','experience','other']
    quote: str = Field(min_length=5,max_length=1000)

class SourceExtraction(BaseModel):
    model_config = ConfigDict(extra='forbid')
    facts: list[SourceFactDraft] = Field(max_length=12)

class SourceDocument(BaseModel):
    id: str
    user_id: str
    kind: str
    title: str
    body: str
    extracted: dict[str, Any]
    created_at: datetime

class SourceConfirmation(BaseModel):
    # Select only from the source's locally validated quotes, never new AI facts.
    fact_indices: list[int] = Field(max_length=12)

class SourceList(BaseModel):
    sources: list[SourceDocument]

class PlanPriority(BaseModel):
    model_config = ConfigDict(extra='forbid')
    template_id: str
    reason: str = Field(min_length=10,max_length=300)

class RateLimiterRequirements(BaseModel):
    model_config = ConfigDict(extra='forbid')
    requests_per_second: int = Field(ge=1,le=10000000)
    identity: str = Field(min_length=3,max_length=100)
    bursts: bool
    availability: Literal['preferred','strict']
    accuracy: str = Field(min_length=3,max_length=200)

class DesignScenarioDraft(BaseModel):
    model_config = ConfigDict(extra='forbid')
    prompt: str = Field(min_length=40,max_length=2000)
    requirements: RateLimiterRequirements

class PlanDraft(BaseModel):
    model_config = ConfigDict(extra='forbid')
    primary_domain: Literal['infra','hw','sw','comm']
    priorities: list[PlanPriority] = Field(min_length=1,max_length=20)
    system_design: DesignScenarioDraft

# Resume ATS review and job tailoring. See docs/RESUME_ATS.md.
AtsCategory = Literal['format','sections','keywords','impact','clarity']
RequirementLevel = Literal['required','preferred']

class JobRequirementDraft(BaseModel):
    model_config = ConfigDict(extra='forbid')
    quote: str = Field(min_length=5,max_length=400)
    term: str = Field(min_length=1,max_length=40)
    level: RequirementLevel

class JobScanDraft(BaseModel):
    model_config = ConfigDict(extra='forbid')
    requirements: list[JobRequirementDraft] = Field(max_length=20)

class JobRequirement(BaseModel):
    # Saved only after quote and term were found verbatim in the posting.
    quote: str
    term: str
    level: RequirementLevel

class AtsFindingDraft(BaseModel):
    model_config = ConfigDict(extra='forbid')
    issue: str = Field(min_length=5,max_length=300)
    quote: str | None = Field(default=None,max_length=400)

class AtsCategoryDraft(BaseModel):
    model_config = ConfigDict(extra='forbid')
    id: AtsCategory
    rating: int = Field(ge=0,le=4)
    findings: list[AtsFindingDraft] = Field(max_length=4)

class AtsSuggestionDraft(BaseModel):
    model_config = ConfigDict(extra='forbid')
    category: AtsCategory
    original: str = Field(min_length=5,max_length=600)
    replacement: str = Field(min_length=1,max_length=800)
    reason: str = Field(min_length=5,max_length=300)

class AtsEvidenceDraft(BaseModel):
    model_config = ConfigDict(extra='forbid')
    term: str = Field(min_length=1,max_length=40)
    resume_quote: str | None = Field(default=None,max_length=400)

class AtsDraft(BaseModel):
    model_config = ConfigDict(extra='forbid')
    categories: list[AtsCategoryDraft] = Field(min_length=5,max_length=5)
    suggestions: list[AtsSuggestionDraft] = Field(max_length=12)
    evidence: list[AtsEvidenceDraft] = Field(default_factory=list,max_length=20)

class AtsFinding(BaseModel):
    issue: str
    quote: str | None = None  # kept only when it is verbatim resume text

class AtsCategoryResult(BaseModel):
    id: AtsCategory
    rating: int = Field(ge=0,le=4)
    weight: int
    findings: list[AtsFinding]

class AtsSuggestion(BaseModel):
    id: int
    category: AtsCategory
    original: str
    replacement: str
    reason: str
    start: int  # offsets into the resume body, computed locally
    end: int

class AtsCoverage(BaseModel):
    quote: str
    term: str
    level: RequirementLevel
    mentioned: bool  # literal, case-insensitive match of term in the resume
    resume_quote: str | None = None
    status: Literal['found','evidence','missing']

class AtsFacts(BaseModel):
    words: int
    email: bool
    phone: bool
    sections: list[str]

class AtsReview(BaseModel):
    resume_id: str
    job_id: str | None = None
    job_title: str | None = None
    score: int | None = Field(default=None,ge=0,le=100)  # computed in code; None for a recorded example
    categories: list[AtsCategoryResult]
    facts: AtsFacts
    suggestions: list[AtsSuggestion]
    rejected: int  # suggestions dropped by the local guards
    coverage: list[AtsCoverage] = Field(default_factory=list)
    provider: str
    rubric_version: str
    source_job_id: str
    created_at: datetime

class AtsRequest(BaseModel):
    job_id: str | None = Field(default=None,min_length=1,max_length=100)

class AtsApply(BaseModel):
    job_id: str | None = Field(default=None,min_length=1,max_length=100)
    suggestion_ids: list[int] = Field(min_length=1,max_length=12)