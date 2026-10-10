from fastapi import APIRouter

from app.core import voice
from app.modules.prepcrew.schemas import (
    PlanRequest, PlanResponse,
    SessionStartRequest, SessionStartResponse,
    TurnRequest, TurnResponse,
    ProbeRequest, ProbeResponse,
    EndSessionResponse, ReportResponse,
    LessonResponse, RetestRequest, RetestResponse, SeasonResponse,
)

router = APIRouter(prefix="/api", tags=["prepcrew"])


@router.post("/plans", response_model=PlanResponse)
async def create_plan(body: PlanRequest):
    # TODO: core.ai.generate_json extracts required skills from body.job_posting and body.resume
    # TODO: map skills to topic graph nodes (topic_graph.py); persist with core.store.create_record("plan", ...)
    return PlanResponse(plan_id="TODO", topics=[], questions=[])


@router.post("/sessions", response_model=SessionStartResponse)
async def start_session(body: SessionStartRequest):
    # TODO: core.store.create_record("session", ...)
    return SessionStartResponse(session_id="TODO", voice_token=await voice.mint_token())


@router.post("/sessions/{session_id}/turns", response_model=TurnResponse)
async def take_turn(session_id: str, body: TurnRequest):
    # TODO: store the answer, core.memory.recall(...), core.ai.generate_text for the next question
    # Keep this path fast: no grading during the live interview
    return TurnResponse(next_question="TODO")


@router.post("/sessions/{session_id}/probe", response_model=ProbeResponse)
async def probe(session_id: str, body: ProbeRequest):
    # TODO: simulator.probe(...) and log the probe order with core.store.add_event
    return ProbeResponse(node=body.node, reading="TODO")


@router.post("/sessions/{session_id}/end", response_model=EndSessionResponse)
async def end_session(session_id: str):
    # TODO: load transcript + probe log, evaluators.evaluate_session(...), write core.store.add_event rows
    return EndSessionResponse(session_id=session_id, results=[], gaps=[])


@router.get("/sessions/{session_id}/report", response_model=ReportResponse)
async def report(session_id: str):
    # TODO: read scores and gaps back from the store
    return ReportResponse(session_id=session_id, results=[], gaps=[])


@router.get("/lessons/{topic}", response_model=LessonResponse)
async def get_lesson(topic: str):
    # TODO: return the cached lesson for this topic (pre-generate all of them before the demo)
    return LessonResponse(topic=topic, body="TODO", ai_generated=True)


@router.post("/retests", response_model=RetestResponse)
async def queue_retest(body: RetestRequest):
    # TODO: queue a retest on the flagged topics
    return RetestResponse(retest_id="TODO", topics=body.topics)


@router.get("/season", response_model=SeasonResponse)
async def season():
    # TODO: mastery over time per topic (core.store.list_events) + application tracker
    return SeasonResponse(mastery=[], applications=[])
