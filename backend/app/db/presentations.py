from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from google.cloud import firestore
from google.cloud.firestore_v1 import SERVER_TIMESTAMP, FieldFilter

from backend.app.db.firestore import get_firestore_client


@dataclass(slots=True)
class PresentationStore:
    client: firestore.AsyncClient
    collection: str = "presentations"

    def _presentations(self) -> firestore.AsyncCollectionReference:
        return self.client.collection(self.collection)

    def _presentation_ref(self, presentation_id: str) -> firestore.AsyncDocumentReference:
        return self._presentations().document(presentation_id)

    def _presentation_images(
        self, presentation_id: str
    ) -> firestore.AsyncCollectionReference:
        return self._presentation_ref(presentation_id).collection("images")

    async def create_presentation_image(
        self,
        presentation_id: str,
        image_id: str,
        *,
        slide_index: int,
        mime_type: str,
        image_bytes: bytes,
        prompt: str,
        alt: str,
    ) -> None:
        await self._presentation_images(presentation_id).document(image_id).set(
            {
                "image_id": image_id,
                "presentation_id": presentation_id,
                "slide_index": slide_index,
                "mime_type": mime_type,
                "image_bytes": image_bytes,
                "prompt": prompt,
                "alt": alt,
                "created_at": SERVER_TIMESTAMP,
            },
            merge=False,
        )

    async def get_presentation_image(
        self, presentation_id: str, image_id: str
    ) -> dict[str, Any] | None:
        snap = await self._presentation_images(presentation_id).document(image_id).get()
        if not snap.exists:
            return None
        data = snap.to_dict() or {}
        data.setdefault("image_id", image_id)
        return data

    async def create_presentation(
        self,
        presentation_id: str,
        *,
        session_id: str | None = None,
        title: str,
        html: str,
        outline: dict[str, Any],
        source_prompt: str,
        model: str,
    ) -> None:
        await self._presentation_ref(presentation_id).set(
            {
                "presentation_id": presentation_id,
                "session_id": session_id,
                "title": title,
                "html": html,
                "outline": outline,
                "source_prompt": source_prompt,
                "model": model,
                "created_at": SERVER_TIMESTAMP,
                "updated_at": SERVER_TIMESTAMP,
            },
            merge=False,
        )

    async def get_presentation(self, presentation_id: str) -> dict[str, Any] | None:
        snap = await self._presentation_ref(presentation_id).get()
        if not snap.exists:
            return None
        data = snap.to_dict() or {}
        data.setdefault("presentation_id", presentation_id)
        return data


    async def list_presentations_for_session(
        self, *, session_id: str, limit: int = 25
    ) -> list[dict[str, Any]]:
        """List recent presentations for a session.

        Note: we avoid a compound order_by query to reduce Firestore composite-index
        requirements; results are sorted client-side when timestamps are present.
        """

        query = (
            self._presentations()
            .where(filter=FieldFilter("session_id", "==", session_id))
            .limit(limit)
            .select(
                [
                    "presentation_id",
                    "session_id",
                    "title",
                    "source_prompt",
                    "model",
                    "created_at",
                    "updated_at",
                ]
            )
        )
        snaps = query.stream()

        out: list[dict[str, Any]] = []
        async for s in snaps:
            d = s.to_dict() or {}
            d.setdefault("presentation_id", s.id)
            out.append(d)

        def _ts_key(v: Any) -> float:
            try:
                # Firestore returns datetime-like objects.
                if hasattr(v, "timestamp"):
                    return float(v.timestamp())
            except Exception:
                return 0.0
            return 0.0

        out.sort(
            key=lambda it: _ts_key(it.get("created_at") or it.get("updated_at")),
            reverse=True,
        )
        return out


def get_presentation_store() -> PresentationStore:
    return PresentationStore(client=get_firestore_client())
