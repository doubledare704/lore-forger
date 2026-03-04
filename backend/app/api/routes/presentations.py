from __future__ import annotations

from fastapi import APIRouter, Depends, Query

from backend.app.api.schemas import (
    GeneratePresentationRequest,
    GeneratePresentationResponse,
    ListPresentationsResponse,
    PresentationListItem,
)
from backend.app.services import get_presentation_service, PresentationService


router = APIRouter(tags=["presentations"])


@router.post("/presentations", response_model=GeneratePresentationResponse)
async def generate_presentation(
    req: GeneratePresentationRequest,
    service: PresentationService = Depends(get_presentation_service),
) -> GeneratePresentationResponse:
    data = await service.generate_presentation(
        prompt=req.prompt,
        session_id=req.session_id,
        slide_count=req.slide_count,
        events_limit=req.events_limit,
    )
    return GeneratePresentationResponse(**data)


@router.get("/presentations", response_model=ListPresentationsResponse)
async def list_presentations(
    session_id: str = Query(..., min_length=1),
    limit: int = Query(default=25, ge=1, le=200),
    service: PresentationService = Depends(get_presentation_service),
) -> ListPresentationsResponse:
    items_data = await service.list_presentations(session_id=session_id, limit=limit)
    items = [PresentationListItem(**item) for item in items_data]
    return ListPresentationsResponse(session_id=session_id, presentations=items)
