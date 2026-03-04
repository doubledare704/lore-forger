from fastapi import Depends

from backend.app.db.firestore import get_session_store, SessionStore
from backend.app.db.presentations import get_presentation_store, PresentationStore
from backend.app.services.ai_service import AIService
from backend.app.services.presentation_service import PresentationService
from backend.app.services.session_service import SessionService


def get_session_service(
    store: SessionStore = Depends(get_session_store),
) -> SessionService:
    return SessionService(store)


def get_presentation_service(
    store: PresentationStore = Depends(get_presentation_store),
    session_store: SessionStore = Depends(get_session_store),
) -> PresentationService:
    return PresentationService(store, session_store)


def get_ai_service() -> AIService:
    return AIService()
