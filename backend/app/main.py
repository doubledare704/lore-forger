from __future__ import annotations

from typing import AsyncIterator

from fastapi import Depends, FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse

from backend.app.api.router import api_router
from backend.app.api.schemas import StreamRequest
from backend.app.ai.sse import sse_json
from backend.app.core.config import get_settings
from backend.app.services import get_ai_service, AIService
from backend.app.web.presentations import router as presentations_router


settings = get_settings()
app = FastAPI(title="LoreForge API", version="0.1.0")

app.include_router(api_router)
app.include_router(presentations_router)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
def health() -> dict:
    return {"status": "ok"}


async def _event_stream(req: StreamRequest, service: AIService) -> AsyncIterator[str]:
    async for msg in service.event_stream(
        prompt=req.prompt, session_id=req.session_id, auto_image=req.auto_image
    ):
        yield sse_json(msg)


@app.post("/api/stream")
async def stream(
    req: StreamRequest, service: AIService = Depends(get_ai_service)
) -> StreamingResponse:
    return StreamingResponse(
        _event_stream(req, service),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            # Helps some reverse proxies (e.g., nginx) not buffer SSE.
            "X-Accel-Buffering": "no",
        },
    )
