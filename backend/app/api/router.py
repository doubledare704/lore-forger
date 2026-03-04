from __future__ import annotations

from fastapi import APIRouter

from backend.app.api.routes.presentations import router as presentations_router
from backend.app.api.routes.sessions import router as sessions_router


api_router = APIRouter(prefix="/api")
api_router.include_router(sessions_router, tags=["sessions"])
api_router.include_router(presentations_router)
