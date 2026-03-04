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


def get_session_store() -> SessionStore:
    return SessionStore(client=get_firestore_client())


@dataclass(slots=True)
class SessionStore:
    client: firestore.AsyncClient
    collection: str = "sessions"

    def _sessions(self) -> firestore.AsyncCollectionReference:
        return self.client.collection(self.collection)

    def _session_ref(self, session_id: str) -> firestore.AsyncDocumentReference:
        return self._sessions().document(session_id)

    async def create_session(
        self,
        session_id: str,
        *,
        world_state: dict[str, Any] | None = None,
        inventory: list[Any] | None = None,
    ) -> dict[str, Any]:
        doc_ref = self._session_ref(session_id)
        await doc_ref.set(
            {
                "world_state": world_state or {},
                "inventory": inventory or [],
                "created_at": SERVER_TIMESTAMP,
                "updated_at": SERVER_TIMESTAMP,
            },
            merge=False,
        )
        return (await self.get_session(session_id)) or {"session_id": session_id}

    async def get_session(self, session_id: str) -> dict[str, Any] | None:
        snap = await self._session_ref(session_id).get()
        if not snap.exists:
            return None
        data = snap.to_dict() or {}
        data["session_id"] = session_id
        return data

    async def update_state(
        self,
        session_id: str,
        *,
        world_state: dict[str, Any] | None = None,
        inventory: list[Any] | None = None,
    ) -> None:
        patch: dict[str, Any] = {"updated_at": SERVER_TIMESTAMP}
        if world_state is not None:
            patch["world_state"] = world_state
        if inventory is not None:
            patch["inventory"] = inventory
        await self._session_ref(session_id).set(patch, merge=True)

    async def add_event(self, session_id: str, *, event: dict[str, Any]) -> str:
        """Append an interaction event under sessions/{id}/events/{autoId}."""

        events_col = self._session_ref(session_id).collection("events")
        doc_ref = events_col.document()  # auto id
        await doc_ref.set({**event, "created_at": SERVER_TIMESTAMP}, merge=False)
        # touch session
        await self._session_ref(session_id).set({"updated_at": SERVER_TIMESTAMP}, merge=True)
        return doc_ref.id

    async def list_events(self, session_id: str, *, limit: int = 50) -> list[dict[str, Any]]:
        events_col = self._session_ref(session_id).collection("events")
        snaps = (
            events_col.order_by("created_at", direction=firestore.Query.DESCENDING)
            .limit(limit)
            .stream()
        )
        out: list[dict[str, Any]] = []
        async for s in snaps:
            d = s.to_dict() or {}
            d["event_id"] = s.id
            out.append(d)
        return out
