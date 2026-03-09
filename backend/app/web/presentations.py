from __future__ import annotations

from fastapi import APIRouter, Depends, Response
from fastapi.responses import HTMLResponse

from backend.app.services import get_presentation_service, PresentationService


router = APIRouter(prefix="/presentations")


@router.get("/{presentation_id}", response_class=HTMLResponse)
async def get_generated_presentation(
    presentation_id: str,
    service: PresentationService = Depends(get_presentation_service),
) -> HTMLResponse:
    content = await service.get_presentation_html(presentation_id)
    return HTMLResponse(content=content)


@router.get("/{presentation_id}/images/{image_id}")
async def get_presentation_image(
    presentation_id: str,
    image_id: str,
    service: PresentationService = Depends(get_presentation_service),
) -> Response:
    data, mime_type = await service.get_presentation_image(presentation_id, image_id)

    return Response(
        content=data,
        media_type=mime_type,
        headers={"Cache-Control": "public, max-age=31536000, immutable"},
    )
