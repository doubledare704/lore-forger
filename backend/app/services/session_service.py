import asyncio
from typing import Any
from uuid import uuid4

from fastapi import HTTPException
from google.genai import types

from backend.app.ai.client import get_genai_client
from backend.app.ai.logic import build_state_derivation_prompt
from backend.app.core.config import get_settings
from backend.app.core.utils import coerce_json_object
from backend.app.db.firestore import SessionStore


class SessionService:
    def __init__(self, store: SessionStore):
        self.store = store

    async def create_session(
        self, session_id: str | None, world_state: dict[str, Any], inventory: list[Any]
    ) -> dict[str, Any]:
        session_id = session_id or str(uuid4())
        try:
            doc = await self.store.create_session(
                session_id,
                world_state=world_state,
                inventory=inventory,
            )
        except Exception as e:
            raise HTTPException(status_code=503, detail=f"Firestore error: {e}")
        return {
            "session_id": session_id,
            "world_state": doc.get("world_state") or {},
            "inventory": doc.get("inventory") or [],
        }

    async def get_session(self, session_id: str) -> dict[str, Any]:
        try:
            doc = await self.store.get_session(session_id)
        except Exception as e:
            raise HTTPException(status_code=503, detail=f"Firestore error: {e}")
        if not doc:
            raise HTTPException(status_code=404, detail="Session not found")
        return {
            "session_id": session_id,
            "world_state": doc.get("world_state") or {},
            "inventory": doc.get("inventory") or [],
        }

    async def update_state(
        self, session_id: str, world_state: dict[str, Any] | None, inventory: list[Any] | None
    ) -> None:
        try:
            await self.store.update_state(
                session_id,
                world_state=world_state,
                inventory=inventory,
            )
        except Exception as e:
            raise HTTPException(status_code=503, detail=f"Firestore error: {e}")

    async def add_event(
        self, session_id: str, role: str, content: str, kind: str
    ) -> str:
        try:
            event_id = await self.store.add_event(
                session_id,
                event={"role": role, "content": content, "kind": kind},
            )
        except Exception as e:
            raise HTTPException(status_code=503, detail=f"Firestore error: {e}")
        return event_id

    async def list_events(self, session_id: str, limit: int) -> list[dict[str, Any]]:
        try:
            events = await self.store.list_events(session_id, limit=limit)
        except Exception as e:
            raise HTTPException(status_code=503, detail=f"Firestore error: {e}")
        return events

    async def derive_state(self, session_id: str, events_limit: int) -> dict[str, Any]:
        try:
            world_state, inventory = await self._derive_state_from_session(
                session_id=session_id,
                events_limit=events_limit,
            )
        except ValueError as e:
            msg = str(e)
            if msg.lower().strip() == "session not found":
                raise HTTPException(status_code=404, detail=msg)
            raise HTTPException(status_code=502, detail=f"State derivation error: {msg}")
        except Exception as e:
            raise HTTPException(status_code=502, detail=f"State derivation error: {e}")

        try:
            await self.store.update_state(
                session_id, world_state=world_state, inventory=inventory
            )
        except Exception as e:
            raise HTTPException(status_code=503, detail=f"Firestore error: {e}")

        return {
            "session_id": session_id,
            "world_state": world_state,
            "inventory": inventory,
        }

    async def _derive_state_from_session(
        self, *, session_id: str, events_limit: int
    ) -> tuple[dict[str, Any], list[Any]]:
        """Fetch session + events and ask Gemini to produce updated world_state/inventory."""

        session = await self.store.get_session(session_id)
        if not session:
            raise ValueError("Session not found")

        current_world_state = session.get("world_state") or {}
        current_inventory = session.get("inventory") or []

        events = await self.store.list_events(session_id, limit=events_limit)
        events = list(reversed(events))  # chronological

        lines: list[str] = []
        for ev in events:
            role = str(ev.get("role") or "?")
            kind = str(ev.get("kind") or "text")
            content = str(ev.get("content") or "").strip()
            if not content:
                continue
            if len(content) > 900:
                content = content[:900] + "…"
            lines.append(f"- [{role}:{kind}] {content}")

        contents = build_state_derivation_prompt(
            current_world_state=current_world_state,
            current_inventory=current_inventory,
            events_text="\n".join(lines) if lines else "(no events)\n",
        )

        settings = get_settings()
        client = get_genai_client()
        # Retry once if the model violates JSON-only constraints.
        last_text = ""
        for attempt in range(2):
            resp = await asyncio.to_thread(
                client.models.generate_content,
                model=settings.gemini_model,
                contents=contents
                if attempt == 0
                else (
                    "Your previous response was invalid JSON and could not be parsed. "
                    "Return ONLY corrected JSON with keys world_state and inventory.\n\n"
                    f"INVALID RESPONSE:\n{last_text}"
                ),
                config=types.GenerateContentConfig(
                    response_mime_type="application/json",
                    temperature=0.0,
                    max_output_tokens=4096,
                ),
            )

            last_text = getattr(resp, "text", None) or ""
            try:
                obj = coerce_json_object(last_text)
                break
            except Exception:
                if attempt == 1:
                    raise

        world_state = obj.get("world_state")
        inventory = obj.get("inventory")
        if not isinstance(world_state, dict):
            raise ValueError("Model returned invalid world_state")
        if not isinstance(inventory, list):
            raise ValueError("Model returned invalid inventory")

        return world_state, inventory
