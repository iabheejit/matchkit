"""FastAPI main application for MatchKit."""
import logging
from contextlib import asynccontextmanager
from datetime import datetime
from typing import AsyncIterator, List, Optional

from fastapi import FastAPI, HTTPException, Depends, Query, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
from sqlalchemy.ext.asyncio import AsyncSession

from config.settings import settings
from db.session import get_session, engine
from db.base import Base
from db.repositories import (
    OrganizationRepository, MatchRepository, MemberRepository,
    FeedbackRepository, NudgeRepository,
)
from matching.recommendations import recommendation_engine
from email_service.sender import email_sender
from email_service.builder import email_builder
from api.auth import require_api_key
from utils.urls import get_profile_url
from api.schemas import (
    OrganizationResponse,
    OrganizationDetail,
    MatchListResponse,
    MatchResponse,
    MatchScoresResponse,
    MatchStatusUpdate,
    MatchStatusEnum,
    SchedulerStatusResponse,
    SendEmailRequest,
    EmailResultResponse,
    HealthResponse,
    # New schemas
    OnboardingStartResponse,
    OnboardingMessageRequest,
    OnboardingMessageResponse,
    OnboardingProfileResponse,
    ChatRoomResponse,
    ChatMessageResponse,
    ChatSendRequest,
    ChatRoomListResponse,
    ChatMessageListResponse,
    MatchFeedbackRequest,
    MatchFeedbackResponse,
    ProfileEnrichRequest,
    ProfileEnrichResponse,
    MatchExplanationResponse,
)

logger = logging.getLogger(__name__)


# ==================== Lifespan ====================

@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Application lifespan: startup and shutdown."""
    logger.info(f"Starting {settings.app_name} API...")

    # Create tables if they don't exist (use Alembic in production)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    logger.info("Database tables ensured")

    from scheduler.manager import scheduler_manager
    scheduler_manager.start()

    yield

    logger.info("Shutting down...")
    scheduler_manager.stop()
    await engine.dispose()


# ==================== App ====================

app = FastAPI(
    title=f"{settings.app_name} API",
    description=settings.app_tagline,
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allowed_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ==================== Helpers ====================

def _org_to_response(org) -> OrganizationResponse:
    """Convert an Organization model to an API response."""
    return OrganizationResponse(
        id=org.id,
        name=org.name,
        description=org.description,
        website=org.website,
        city=org.city,
        state=org.state,
        interests=org.interests or [],
        organization_size=org.organization_size,
        regions=org.regions or [],
        preferences=org.preferences or [],
        key_people=org.key_people,
        contact_email=org.contact_email,
        twitter=org.twitter,
        linkedin=org.linkedin,
        last_synced=org.last_synced,
    )


def _org_to_detail(org) -> OrganizationDetail:
    """Convert an Organization model to a detailed API response."""
    return OrganizationDetail(
        id=org.id,
        name=org.name,
        description=org.description,
        website=org.website,
        city=org.city,
        state=org.state,
        interests=org.interests or [],
        organization_size=org.organization_size,
        regions=org.regions or [],
        preferences=org.preferences or [],
        key_people=org.key_people,
        contact_email=org.contact_email,
        twitter=org.twitter,
        linkedin=org.linkedin,
        last_synced=org.last_synced,
        activities=org.activities,
        year_established=org.year_established,
        org_type=org.org_type,
        phone=org.phone,
        facebook=org.facebook,
        metadata_text=org.metadata_text,
        external_id=org.external_id,
        created_at=org.created_at,
        updated_at=org.updated_at,
    )


def _build_match_data_for_template(matches) -> list:
    """Build match data dicts for email templates from DB match objects."""
    match_data = []
    for m in matches:
        match_data.append({
            "org": {
                "name": m.target_org.name,
                "description": m.target_org.description,
                "interests": m.target_org.interests or [],
                "regions": m.target_org.regions or [],
                "website": m.target_org.website,
            },
            "score": m.overall_score,
            "embedding_sim": m.embedding_similarity,
            "interest_score": m.interest_score,
            "geo_score": m.geographic_score,
            "rationale": m.rationale,
            "profile_url": get_profile_url(m.target_org.name),
        })
    return match_data


def _match_to_response(match) -> MatchResponse:
    """Convert a Match model to an API response."""
    return MatchResponse(
        id=match.id,
        target_organization=_org_to_response(match.target_org),
        overall_score=match.overall_score,
        scores=MatchScoresResponse(
            embedding_similarity=match.embedding_similarity,
            interest_score=match.interest_score,
            geographic_score=match.geographic_score,
            size_score=match.size_score,
            preference_score=match.preference_score,
        ),
        rationale=match.rationale,
        match_type=match.match_type,
        status=MatchStatusEnum(match.status),
        created_at=match.created_at,
    )


# ==================== Health ====================

@app.get("/health", response_model=HealthResponse)
async def health_check(session: AsyncSession = Depends(get_session)):
    """Check API health and dependency status."""
    db_ok = False
    try:
        from sqlalchemy import text
        await session.execute(text("SELECT 1"))
        db_ok = True
    except Exception as e:
        logger.warning(f"Database health check failed: {e}")

    from scheduler.manager import scheduler_manager
    sched_running = scheduler_manager._is_running

    return HealthResponse(
        status="healthy" if db_ok else "degraded",
        timestamp=datetime.utcnow(),
        database_connected=db_ok,
        scheduler_running=sched_running,
        email_configured=email_sender.is_configured,
    )


# ==================== Organizations ====================

@app.get("/api/organizations", response_model=List[OrganizationResponse])
async def list_organizations(
    offset: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=500),
    session: AsyncSession = Depends(get_session),
    _: str = Depends(require_api_key),
):
    """List organizations with pagination."""
    repo = OrganizationRepository(session)
    orgs = await repo.list_all(offset=offset, limit=limit)
    return [_org_to_response(org) for org in orgs]


@app.get("/api/organizations/{org_id}", response_model=OrganizationDetail)
async def get_organization(
    org_id: int,
    session: AsyncSession = Depends(get_session),
    _: str = Depends(require_api_key),
):
    """Get organization details by ID."""
    repo = OrganizationRepository(session)
    org = await repo.get_by_id(org_id)
    if not org:
        raise HTTPException(status_code=404, detail="Organization not found")
    return _org_to_detail(org)


# ==================== Matches ====================

@app.get("/api/organizations/{org_id}/matches", response_model=MatchListResponse)
async def get_organization_matches(
    org_id: int,
    status: Optional[str] = None,
    offset: int = Query(0, ge=0),
    limit: int = Query(10, ge=1, le=100),
    session: AsyncSession = Depends(get_session),
    _: str = Depends(require_api_key),
):
    """Get matches for an organization."""
    org_repo = OrganizationRepository(session)
    org = await org_repo.get_by_id(org_id)
    if not org:
        raise HTTPException(status_code=404, detail="Organization not found")

    match_repo = MatchRepository(session)
    matches = await match_repo.get_matches_for_org(
        org_id=org_id, status=status, limit=limit, offset=offset
    )
    total = await match_repo.count_for_org(org_id=org_id, status=status)

    return MatchListResponse(
        organization_id=org_id,
        organization_name=org.name,
        matches=[_match_to_response(m) for m in matches],
        total_count=total,
    )


@app.post("/api/organizations/{org_id}/matches/generate")
async def generate_matches(
    org_id: int,
    top_n: int = Query(10, ge=1, le=50),
    session: AsyncSession = Depends(get_session),
    _: str = Depends(require_api_key),
):
    """Generate fresh matches for an organization."""
    org_repo = OrganizationRepository(session)
    org = await org_repo.get_by_id(org_id)
    if not org:
        raise HTTPException(status_code=404, detail="Organization not found")

    all_orgs = list(await org_repo.list_all(limit=10000))
    matches = recommendation_engine.generate_for_org(org, all_orgs, top_n=top_n)

    match_repo = MatchRepository(session)
    deleted = await match_repo.delete_for_org(org_id)
    if matches:
        await match_repo.create_many(matches)

    if org.embedding is not None:
        await org_repo.update(org)

    await session.commit()

    return {
        "organization_id": org_id,
        "matches_generated": len(matches),
        "old_matches_replaced": deleted,
    }


@app.patch("/api/matches/{match_id}/status")
async def update_match_status(
    match_id: int,
    update: MatchStatusUpdate,
    session: AsyncSession = Depends(get_session),
    _: str = Depends(require_api_key),
):
    """Update the status of a match."""
    repo = MatchRepository(session)
    match = await repo.update_status(match_id, update.status.value)
    if not match:
        raise HTTPException(status_code=404, detail="Match not found")

    await session.commit()
    return {"success": True, "match_id": match_id, "new_status": update.status}


# ==================== Scheduler ====================

@app.get("/api/scheduler/status", response_model=SchedulerStatusResponse)
async def get_scheduler_status(_: str = Depends(require_api_key)):
    """Get scheduler status and job info."""
    from scheduler.manager import scheduler_manager
    return scheduler_manager.get_job_status()


@app.post("/api/scheduler/trigger/{job_name}")
async def trigger_job(job_name: str, _: str = Depends(require_api_key)):
    """Manually trigger a scheduled job."""
    from scheduler.manager import scheduler_manager
    result = await scheduler_manager.trigger_job(job_name)
    if "error" in result:
        raise HTTPException(status_code=400, detail=result["error"])
    return result


@app.post("/api/scheduler/start")
async def start_scheduler(_: str = Depends(require_api_key)):
    from scheduler.manager import scheduler_manager
    scheduler_manager.start()
    return {"success": True, "message": "Scheduler started"}


@app.post("/api/scheduler/stop")
async def stop_scheduler(_: str = Depends(require_api_key)):
    from scheduler.manager import scheduler_manager
    scheduler_manager.stop()
    return {"success": True, "message": "Scheduler stopped"}


# ==================== Email ====================

@app.post("/api/email/send-test", response_model=EmailResultResponse)
async def send_test_email(
    request: SendEmailRequest,
    session: AsyncSession = Depends(get_session),
    _: str = Depends(require_api_key),
):
    """Send a test match digest email to a specific recipient."""
    org_repo = OrganizationRepository(session)
    org = await org_repo.get_by_id(request.organization_id)
    if not org:
        raise HTTPException(status_code=404, detail="Organization not found")

    match_repo = MatchRepository(session)
    matches = await match_repo.get_matches_for_org(org.id, limit=settings.max_matches_per_email)
    if not matches:
        raise HTTPException(status_code=400, detail="No matches available for this organization")

    match_data = _build_match_data_for_template(matches)

    result = email_sender.send_digest(
        to_email=request.recipient_email,
        recipient_org={"first_name": "Team", "org_name": org.name},
        matches=match_data,
    )

    return EmailResultResponse(
        success=result.success,
        recipient=result.recipient,
        message_id=result.message_id,
        error=result.error,
        sent_at=result.sent_at,
    )


# ==================== Preview ====================

@app.get("/api/email/preview/{org_id}", response_class=HTMLResponse)
async def preview_email_digest(
    org_id: int,
    session: AsyncSession = Depends(get_session),
):
    """Preview the digest email for an organization (HTML)."""
    org_repo = OrganizationRepository(session)
    org = await org_repo.get_by_id(org_id)
    if not org:
        raise HTTPException(status_code=404, detail="Organization not found")

    match_repo = MatchRepository(session)
    member_repo = MemberRepository(session)
    matches = await match_repo.get_matches_for_org(org.id, limit=settings.max_matches_per_email)

    match_data = _build_match_data_for_template(matches)

    primary = await member_repo.get_primary_for_org(org.id)
    if not primary:
        members = await member_repo.get_for_org(org.id)
        primary = members[0] if members else None

    recipient = {
        "first_name": primary.first_name if primary else "Team",
        "org_name": org.name,
    }

    digest = email_builder.build_digest(recipient_org=recipient, matches=match_data)
    return HTMLResponse(content=digest["html"])


# ==================== Onboarding (AI Conversational) ====================

@app.post("/api/onboarding/start", response_model=OnboardingStartResponse)
async def start_onboarding(session: AsyncSession = Depends(get_session)):
    """Start a new AI-driven conversational onboarding session."""
    from onboarding.engine import onboarding_engine

    onboarding = await onboarding_engine.start_session(session)
    await session.commit()

    first_message = onboarding.conversation[0]["content"] if onboarding.conversation else ""
    return OnboardingStartResponse(
        session_token=onboarding.session_token,
        message=first_message,
    )


@app.post(
    "/api/onboarding/{session_token}/message",
    response_model=OnboardingMessageResponse,
)
async def onboarding_message(
    session_token: str,
    request: OnboardingMessageRequest,
    session: AsyncSession = Depends(get_session),
):
    """Send a message in an onboarding conversation and get the AI's response."""
    from onboarding.engine import onboarding_engine

    onboarding = await onboarding_engine.get_session_by_token(session, session_token)
    if not onboarding:
        raise HTTPException(status_code=404, detail="Onboarding session not found")
    if onboarding.status != "in_progress":
        raise HTTPException(status_code=400, detail="Onboarding session already completed")

    response_text, is_complete = await onboarding_engine.process_message(
        session, onboarding, request.message
    )
    await session.commit()

    return OnboardingMessageResponse(
        response=response_text,
        is_complete=is_complete,
        step=onboarding.current_step,
    )


@app.post(
    "/api/onboarding/{session_token}/complete",
    response_model=OnboardingProfileResponse,
)
async def complete_onboarding(
    session_token: str,
    session: AsyncSession = Depends(get_session),
):
    """Finalize onboarding and create a profile from the conversation."""
    from onboarding.engine import onboarding_engine

    onboarding = await onboarding_engine.get_session_by_token(session, session_token)
    if not onboarding:
        raise HTTPException(status_code=404, detail="Onboarding session not found")
    if onboarding.status != "completed":
        raise HTTPException(status_code=400, detail="Onboarding conversation not yet complete")

    org = await onboarding_engine.create_profile_from_session(session, onboarding)
    if not org:
        raise HTTPException(status_code=500, detail="Failed to create profile")

    await session.commit()

    return OnboardingProfileResponse(
        organization_id=org.id,
        name=org.name,
        extracted_profile=onboarding.extracted_profile,
    )


# ==================== Chat (REST + WebSocket) ====================

@app.post("/api/chat/rooms/{match_id}", response_model=ChatRoomResponse)
async def create_or_get_chat_room(
    match_id: int,
    session: AsyncSession = Depends(get_session),
    _: str = Depends(require_api_key),
):
    """Get or create a chat room for a match (generates AI icebreaker)."""
    from chat.service import ChatService

    chat_service = ChatService(session)
    room = await chat_service.get_or_create_room(match_id)
    if not room:
        raise HTTPException(status_code=404, detail="Match not found")

    await session.commit()

    return ChatRoomResponse(
        id=room.id,
        match_id=room.match_id,
        org_a_id=room.org_a_id,
        org_b_id=room.org_b_id,
        org_a_name=room.org_a.name if room.org_a else None,
        org_b_name=room.org_b.name if room.org_b else None,
        icebreaker=room.icebreaker,
        status=room.status,
        created_at=room.created_at,
    )


@app.get("/api/chat/rooms", response_model=ChatRoomListResponse)
async def list_chat_rooms(
    org_id: int = Query(..., description="Organization ID to list rooms for"),
    session: AsyncSession = Depends(get_session),
    _: str = Depends(require_api_key),
):
    """List all chat rooms for an organization."""
    from chat.service import ChatService

    chat_service = ChatService(session)
    rooms = await chat_service.get_rooms_for_org(org_id)

    room_responses = []
    for room in rooms:
        unread = await chat_service.get_unread_count(room.id, org_id)
        room_responses.append(ChatRoomResponse(
            id=room.id,
            match_id=room.match_id,
            org_a_id=room.org_a_id,
            org_b_id=room.org_b_id,
            org_a_name=room.org_a.name if room.org_a else None,
            org_b_name=room.org_b.name if room.org_b else None,
            icebreaker=room.icebreaker,
            status=room.status,
            unread_count=unread,
            created_at=room.created_at,
        ))

    return ChatRoomListResponse(rooms=room_responses, total_count=len(room_responses))


@app.get("/api/chat/rooms/{room_id}/messages", response_model=ChatMessageListResponse)
async def get_chat_messages(
    room_id: int,
    limit: int = Query(50, ge=1, le=200),
    before_id: Optional[int] = None,
    session: AsyncSession = Depends(get_session),
    _: str = Depends(require_api_key),
):
    """Get message history for a chat room."""
    from chat.service import ChatService

    chat_service = ChatService(session)
    messages = await chat_service.get_messages(room_id, limit=limit, before_id=before_id)

    return ChatMessageListResponse(
        room_id=room_id,
        messages=[
            ChatMessageResponse(
                id=m.id,
                room_id=m.room_id,
                sender_org_id=m.sender_org_id,
                content=m.content,
                message_type=m.message_type,
                read_at=m.read_at,
                created_at=m.created_at,
            )
            for m in messages
        ],
        total_count=len(messages),
    )


@app.post("/api/chat/rooms/{room_id}/messages", response_model=ChatMessageResponse)
async def send_chat_message(
    room_id: int,
    request: ChatSendRequest,
    org_id: int = Query(..., description="Sender organization ID"),
    session: AsyncSession = Depends(get_session),
    _: str = Depends(require_api_key),
):
    """Send a message in a chat room (REST fallback — prefer WebSocket)."""
    from chat.service import ChatService

    chat_service = ChatService(session)
    msg = await chat_service.send_message(room_id, org_id, request.content)
    if not msg:
        raise HTTPException(status_code=400, detail="Failed to send message")

    await session.commit()

    return ChatMessageResponse(
        id=msg.id,
        room_id=msg.room_id,
        sender_org_id=msg.sender_org_id,
        content=msg.content,
        message_type=msg.message_type,
        read_at=msg.read_at,
        created_at=msg.created_at,
    )


@app.post("/api/chat/rooms/{room_id}/read")
async def mark_messages_read(
    room_id: int,
    org_id: int = Query(..., description="Reader organization ID"),
    session: AsyncSession = Depends(get_session),
    _: str = Depends(require_api_key),
):
    """Mark all messages in a room as read by an organization."""
    from chat.service import ChatService

    chat_service = ChatService(session)
    count = await chat_service.mark_messages_read(room_id, org_id)
    await session.commit()
    return {"marked_read": count}


@app.websocket("/ws/chat/{room_id}")
async def websocket_chat(
    websocket: WebSocket,
    room_id: int,
    org_id: int = Query(...),
    api_key: str = Query(...),
):
    """WebSocket endpoint for real-time chat.

    Connect with: ws://host/ws/chat/{room_id}?org_id=X&api_key=Y
    Send JSON: {"content": "message text"}
    Receive JSON: {"id", "room_id", "sender_org_id", "content", "message_type", "created_at"}
    """
    # Validate API key
    if api_key != settings.api_key:
        await websocket.close(code=4003, reason="Invalid API key")
        return

    from chat.manager import connection_manager
    from chat.service import ChatService

    await connection_manager.connect(websocket, room_id, org_id)

    # Send presence notification
    await connection_manager.broadcast_to_room(
        room_id,
        {"type": "presence", "org_id": org_id, "status": "online"},
        exclude_org=org_id,
    )

    try:
        while True:
            data = await websocket.receive_json()
            content = data.get("content", "").strip()
            if not content:
                continue

            # Persist message
            async with get_session() as session:
                chat_service = ChatService(session)
                msg = await chat_service.send_message(room_id, org_id, content)
                await session.commit()

                # Broadcast to room
                await connection_manager.broadcast_to_room(
                    room_id,
                    {
                        "type": "message",
                        "id": msg.id,
                        "room_id": room_id,
                        "sender_org_id": org_id,
                        "content": content,
                        "message_type": "user",
                        "created_at": msg.created_at.isoformat(),
                    },
                )

    except WebSocketDisconnect:
        connection_manager.disconnect(websocket, room_id, org_id)
        await connection_manager.broadcast_to_room(
            room_id,
            {"type": "presence", "org_id": org_id, "status": "offline"},
        )


# ==================== Feedback ====================

@app.post("/api/matches/{match_id}/feedback", response_model=MatchFeedbackResponse)
async def submit_match_feedback(
    match_id: int,
    request: MatchFeedbackRequest,
    org_id: int = Query(..., description="Organization submitting feedback"),
    session: AsyncSession = Depends(get_session),
    _: str = Depends(require_api_key),
):
    """Submit feedback on a match — drives adaptive scoring."""
    from models.entities import MatchFeedback

    match_repo = MatchRepository(session)
    match = await match_repo.get_by_id(match_id)
    if not match:
        raise HTTPException(status_code=404, detail="Match not found")

    feedback = MatchFeedback(
        match_id=match_id,
        organization_id=org_id,
        feedback_type=request.feedback_type.value,
        comment=request.comment,
    )
    feedback_repo = FeedbackRepository(session)
    feedback = await feedback_repo.create(feedback)

    # If user wants to connect, update match status and create chat room
    if request.feedback_type.value == "connect":
        await match_repo.update_status(match_id, "contacted")
        if settings.chat_enabled:
            from chat.service import ChatService
            chat_service = ChatService(session)
            await chat_service.get_or_create_room(match_id)

    await session.commit()

    return MatchFeedbackResponse(
        id=feedback.id,
        match_id=feedback.match_id,
        feedback_type=feedback.feedback_type,
        comment=feedback.comment,
        created_at=feedback.created_at,
    )


# ==================== AI Features ====================

@app.post("/api/ai/enrich-profile", response_model=ProfileEnrichResponse)
async def enrich_profile(
    request: ProfileEnrichRequest,
    _: str = Depends(require_api_key),
):
    """Extract structured profile data from free text using AI."""
    from ai.profile_enrichment import profile_enricher

    result = profile_enricher.enrich_from_text(request.text)
    if not result:
        raise HTTPException(status_code=500, detail="Profile enrichment failed")

    return ProfileEnrichResponse(**{
        k: v for k, v in result.items()
        if k in ProfileEnrichResponse.model_fields
    })


@app.get("/api/ai/explain-match/{match_id}", response_model=MatchExplanationResponse)
async def explain_match(
    match_id: int,
    session: AsyncSession = Depends(get_session),
    _: str = Depends(require_api_key),
):
    """Generate an AI explanation for why two profiles were matched."""
    from ai.match_explainer import match_explainer

    match_repo = MatchRepository(session)
    match = await match_repo.get_by_id(match_id)
    if not match:
        raise HTTPException(status_code=404, detail="Match not found")

    # If we already have a rationale, return it
    if match.rationale:
        return MatchExplanationResponse(match_id=match_id, explanation=match.rationale)

    explanation = match_explainer.explain_match_object(
        match, match.source_org, match.target_org
    )
    if not explanation:
        raise HTTPException(status_code=500, detail="Failed to generate explanation")

    # Persist the explanation
    match.rationale = explanation
    await session.commit()

    return MatchExplanationResponse(match_id=match_id, explanation=explanation)


# ==================== Run ====================

if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "api.main:app",
        host=settings.api_host,
        port=settings.api_port,
        reload=settings.debug,
    )
