from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from threading import Lock
from typing import Any
from uuid import uuid4


@dataclass(frozen=True)
class StoredPresentation:
    presentation_id: str
    created_at: datetime
    title: str
    outline: dict[str, Any]
    html: str


class InMemoryPresentationStore:
    """Simple in-memory store for generated Reveal.js decks.

    Notes:
    - Suitable for local dev / single instance.
    - On Cloud Run with multiple instances, in-memory storage is not shared.
      We can move this to Firestore in a later step.
    """

    def __init__(self, *, ttl_seconds: int = 60 * 60, max_items: int = 100) -> None:
        self._ttl = timedelta(seconds=ttl_seconds)
        self._max_items = max_items
        self._lock = Lock()
        self._items: dict[str, StoredPresentation] = {}

    def put(
        self, *, title: str, outline: dict[str, Any], html: str
    ) -> StoredPresentation:
        now = datetime.now(timezone.utc)
        item = StoredPresentation(
            presentation_id=str(uuid4()),
            created_at=now,
            title=title,
            outline=outline,
            html=html,
        )

        with self._lock:
            self._cleanup_locked(now)

            # Basic max size eviction (oldest first)
            if len(self._items) >= self._max_items:
                oldest = min(self._items.values(), key=lambda it: it.created_at)
                self._items.pop(oldest.presentation_id, None)

            self._items[item.presentation_id] = item

        return item

    def get(self, presentation_id: str) -> StoredPresentation | None:
        now = datetime.now(timezone.utc)
        with self._lock:
            self._cleanup_locked(now)
            return self._items.get(presentation_id)

    def _cleanup_locked(self, now: datetime) -> None:
        expired_before = now - self._ttl
        expired_ids = [
            pid for pid, item in self._items.items() if item.created_at < expired_before
        ]
        for pid in expired_ids:
            self._items.pop(pid, None)


store = InMemoryPresentationStore()
