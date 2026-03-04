from __future__ import annotations

from fastapi import APIRouter, Depends, Query

from backend.app.api.schemas import (
    AddEventRequest,
    CreateSessionRequest,
    DeriveStateRequest,
    SessionResponse,
    UpdateStateRequest,
)
from backend.app.services import get_session_service, SessionService


router = APIRouter(prefix="/sessions")


@router.post("", response_model=SessionResponse)
async def create_session(
    body: CreateSessionRequest,
    service: SessionService = Depends(get_session_service),
) -> SessionResponse:
    data = await service.create_session(
        session_id=body.session_id,
        world_state=body.world_state,
        inventory=body.inventory,
    )
    return SessionResponse(**data)


@router.get("/{session_id}", response_model=SessionResponse)
async def get_session(
    session_id: str,
    service: SessionService = Depends(get_session_service),
) -> SessionResponse:
    data = await service.get_session(session_id)
    return SessionResponse(**data)


@router.put("/{session_id}/state")
async def update_state(
    session_id: str,
    body: UpdateStateRequest,
    service: SessionService = Depends(get_session_service),
) -> dict:
    await service.update_state(
        session_id=session_id,
        world_state=body.world_state,
        inventory=body.inventory,
    )
    return {"ok": True}


@router.post("/{session_id}/events")
async def add_event(
    session_id: str,
    body: AddEventRequest,
    service: SessionService = Depends(get_session_service),
) -> dict:
    event_id = await service.add_event(
        session_id=session_id,
        role=body.role,
        content=body.content,
        kind=body.kind,
    )
    return {"ok": True, "event_id": event_id}


@router.get("/{session_id}/events")
async def list_events(
    session_id: str,
    limit: int = Query(default=50, ge=1, le=200),
    service: SessionService = Depends(get_session_service),
) -> dict:
    events = await service.list_events(session_id=session_id, limit=limit)
    return {"session_id": session_id, "events": events}


@router.post("/{session_id}/state/derive", response_model=SessionResponse)
async def derive_state(
    session_id: str,
    body: DeriveStateRequest,
    service: SessionService = Depends(get_session_service),
) -> SessionResponse:
    data = await service.derive_state(
        session_id=session_id,
        events_limit=body.events_limit,
    )
    return SessionResponse(**data)
