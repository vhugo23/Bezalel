"""PrepCrew HTTP routes, all under /api. Shapes: schemas.py. Contract: contracts/api.md."""
from fastapi import APIRouter, BackgroundTasks, HTTPException, Query

from app.core import voice
from app.core.sse import sse_response
from app.modules.prepcrew import service
from app.modules.prepcrew.schemas import (
    DeleteResponse, EndSessionResponse, LessonResponse, MasteryResponse, MetricsResponse,
    PlanRequest, PlanResponse, ProbeEvent, ProbeRequest, ReportResponse, RetestRequest,
    SessionStartRequest, SessionStartResponse, SkillsResponse, TurnRequest, TurnResponse,
)

router = APIRouter(prefix="/api", tags=["prepcrew"])


def _http(e: Exception) -> HTTPException:
    if isinstance(e, service.NotFound):
        return HTTPException(status_code=404, detail=str(e))
    if isinstance(e, service.BadRequest):
        return HTTPException(status_code=400, detail=str(e))
    if isinstance(e, service.NotImplementedYet):
        return HTTPException(status_code=501, detail=str(e))
    raise e


def _session_response(rec: dict, voice_token: str | None = None) -> SessionStartResponse:
    d = rec["data"]
    opening = d.get("last_interviewer_text") if d["kind"] == "interview" else None
    return SessionStartResponse(session_id=rec["id"], kind=d["kind"], pair_code=d["pair_code"],
                                voice_token=voice_token, strict=d.get("strict", True), state=d["state"],
                                opening=opening)


@router.post("/plans", response_model=PlanResponse)
async def create_plan(body: PlanRequest):
    p = await service.create_plan(body.job_posting, body.resume, body.user_id)
    return PlanResponse(plan_id=p["plan_id"], topics=p["topics"], questions=p["questions"],
                        scenario_ids=p["scenario_ids"], project=p["project"], requirements=p["requirements"],
                        degraded=p["degraded"])


@router.post("/sessions", response_model=SessionStartResponse)
async def start_session(body: SessionStartRequest):
    try:
        rec = await service.create_session(body.plan_id, body.user_id, body.consent, strict=body.strict)
    except (service.NotFound, service.BadRequest) as e:
        raise _http(e)
    return _session_response(rec, await voice.mint_token())


@router.post("/sessions/{session_id}/turns", response_model=TurnResponse)
async def take_turn(session_id: str, body: TurnRequest):
    """Typed fallback. The voice path uses WS /ws/voice/{session_id}."""
    try:
        r = await service.handle_answer(session_id, body.answer)
    except (service.NotFound, service.BadRequest) as e:
        raise _http(e)
    return TurnResponse(answer_id=r["answer_id"], next_question=r["next_question"], done=r["done"],
                        degraded=r["degraded"], source=r["source"], ended_early=r["ended_early"], meter=r["meter"])


@router.post("/sessions/{session_id}/probe", response_model=ProbeEvent)
async def probe(session_id: str, body: ProbeRequest):
    """Fallback and tests. The live path is WS /ws/board/{session_id}."""
    try:
        return await service.record_probe(session_id, body.action, body.node, body.scenario_id)
    except (service.NotFound, service.BadRequest, service.NotImplementedYet) as e:
        raise _http(e)


@router.post("/sessions/{session_id}/end", response_model=EndSessionResponse)
async def end_session(session_id: str, background: BackgroundTasks):
    """Returns immediately. Progress and results arrive on GET /api/sessions/{id}/events (SSE)."""
    try:
        if await service.start_grading(session_id):
            background.add_task(service.run_grading, session_id)
    except service.NotFound as e:
        raise _http(e)
    return EndSessionResponse(status="grading", session_id=session_id,
                              events_url=f"/api/sessions/{session_id}/events")


@router.get("/sessions/{session_id}/events")
async def session_events(session_id: str):
    """Server-Sent Events: evaluator_started, evaluator_done, evaluator_failed, grading_complete.
    Replays events that already happened, and closes after grading_complete."""
    try:
        await service.get_session(session_id)
    except service.NotFound as e:
        raise _http(e)
    return sse_response(service.channel(session_id), stop_on={"grading_complete"})


@router.get("/sessions/{session_id}/report", response_model=ReportResponse)
async def report(session_id: str):
    try:
        d = (await service.get_session(session_id))["data"]
    except service.NotFound as e:
        raise _http(e)
    return ReportResponse(session_id=session_id, status=d.get("status", "not_ended"),
                          results=d.get("results", []), skill_flags=d.get("skill_flags", []))


@router.delete("/sessions/{session_id}", response_model=DeleteResponse)
async def delete_session(session_id: str):
    """Consent: removes every stored row for this session."""
    try:
        n = await service.delete_session(session_id)
    except service.NotFound as e:
        raise _http(e)
    return DeleteResponse(session_id=session_id, deleted_rows=n)


@router.get("/skills", response_model=SkillsResponse)
async def skills(user_id: str | None = None):
    return SkillsResponse(user_id=user_id, nodes=await service.skills(user_id))


@router.get("/lessons/{skill_id}", response_model=LessonResponse)
async def get_lesson(skill_id: str):
    try:
        d = await service.lesson(skill_id)
    except service.NotFound as e:
        raise _http(e)
    return LessonResponse(skill_id=skill_id, body=d.get("body", ""), ai_generated=d.get("ai_generated", True))


@router.post("/retests", response_model=SessionStartResponse)
async def create_retest(body: RetestRequest):
    try:
        rec = await service.create_retest(body.session_id, body.skill_ids)
    except (service.NotFound, service.BadRequest) as e:
        raise _http(e)
    return _session_response(rec, await voice.mint_token())


@router.get("/mastery", response_model=MasteryResponse)
async def mastery(user_id: str = Query(...)):
    return MasteryResponse(user_id=user_id, series=await service.mastery_series(user_id))


@router.get("/metrics/{session_id}", response_model=MetricsResponse)
async def metrics(session_id: str):
    """Measured values only. Fields stay null until something was measured."""
    try:
        return await service.metrics(session_id)
    except service.NotFound as e:
        raise _http(e)
