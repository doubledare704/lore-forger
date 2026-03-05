from fastapi import APIRouter

from backend.app.api.routes import presentations_router, sessions_router


api_router = APIRouter(prefix="/api")
api_router.include_router(sessions_router, tags=["sessions"])
api_router.include_router(presentations_router)
