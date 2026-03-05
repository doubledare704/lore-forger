from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
from typing import Any

from google.cloud import firestore
from google.cloud.firestore_v1 import SERVER_TIMESTAMP


@lru_cache(maxsize=1)
def get_firestore_client() -> firestore.AsyncClient:
    """Lazy singleton Firestore client.

    Auth:
      - Local dev: gcloud ADC (`gcloud auth application-default login`)
      - Cloud Run: service account ADC
    """
    return firestore.AsyncClient()


@dataclass(slots=True)
class SessionStore:
    """Store for game sessions and events in Firestore."""

    client: firestore.AsyncClient
    collection: str = "sessions"

    def _sessions(self) -> firestore.AsyncCollectionReference:
        """Helper to get the main sessions collection."""
        return self.client.collection(self.collection)

    def _session_ref(self, session_id: str) -> firestore.AsyncDocumentReference:
        """Helper to get a document reference for a session."""
        return self._sessions().document(session_id)

    def _events(self, session_id: str) -> firestore.AsyncCollectionReference:
        """Helper to get the events sub-collection for a session."""
        return self._session_ref(session_id).collection("events")  # type: ignore

    async def create_session(
        self,
        session_id: str,
        *,
        world_state: dict[str, Any] | None = None,
        inventory: list[Any] | None = None,
    ) -> dict[str, Any]:
        """Create a new session document. Overwrites if it exists."""
        doc_ref = self._session_ref(session_id)
        data = {
            "world_state": world_state or {},
            "inventory": inventory or [],
            "created_at": SERVER_TIMESTAMP,
            "updated_at": SERVER_TIMESTAMP,
        }
        await doc_ref.set(data, merge=False)

        # We re-fetch to resolve SERVER_TIMESTAMP values from the server.
        return (await self.get_session(session_id)) or (data | {"session_id": session_id})

    async def get_session(self, session_id: str) -> dict[str, Any] | None:
        """Fetch session data by ID. Returns None if document does not exist."""
        snap = await self._session_ref(session_id).get()
        if not snap.exists:
            return None
        return (snap.to_dict() or {}) | {"session_id": session_id}

    async def update_state(
        self,
        session_id: str,
        *,
        world_state: dict[str, Any] | None = None,
        inventory: list[Any] | None = None,
    ) -> None:
        """Merge new world_state or inventory into the session document."""
        patch: dict[str, Any] = {"updated_at": SERVER_TIMESTAMP}
        if world_state is not None:
            patch["world_state"] = world_state
        if inventory is not None:
            patch["inventory"] = inventory
        await self._session_ref(session_id).set(patch, merge=True)

    async def add_event(self, session_id: str, *, event: dict[str, Any]) -> str:
        """Append an event to sessions/{id}/events/{autoId} and update session's updated_at."""
        session_ref = self._session_ref(session_id)
        event_ref = self._events(session_id).document()

        batch = self.client.batch()
        batch.set(event_ref, event | {"created_at": SERVER_TIMESTAMP})
        batch.set(session_ref, {"updated_at": SERVER_TIMESTAMP}, merge=True)
        await batch.commit()

        return event_ref.id

    async def list_events(
        self, session_id: str, *, limit: int = 50
    ) -> list[dict[str, Any]]:
        """List recent events for a session, newest first."""
        query = (
            self._events(session_id)
            .order_by("created_at", direction=firestore.Query.DESCENDING)
            .limit(limit)
        )
        return [
            (s.to_dict() or {}) | {"event_id": s.id}
            async for s in query.stream()
        ]


def get_session_store() -> SessionStore:
    """Dependency provider for SessionStore."""
    return SessionStore(client=get_firestore_client())
