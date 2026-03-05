import asyncio
import logging
from typing import Any
from uuid import uuid4

from fastapi import HTTPException
from google.genai import types

from backend.app.ai.client import get_genai_client
from backend.app.ai.logic import (
    build_deck_image_prompt,
    build_presentation_context_prompt,
    build_presentation_outline_prompt,
)
from backend.app.core.config import get_settings
from backend.app.core.templates import render_template
from backend.app.core.utils import coerce_json_object
from backend.app.db.firestore import SessionStore
from backend.app.db.presentations import PresentationStore


class PresentationService:
    def __init__(self, store: PresentationStore, session_store: SessionStore):
        self.store = store
        self.session_store = session_store

    async def generate_presentation(
        self,
        prompt: str | None,
        session_id: str | None,
        slide_count: int,
        events_limit: int,
    ) -> dict[str, Any]:
        try:
            focus = (prompt or "").strip() or None

            if session_id:
                model_input = await self._build_prompt_from_session(
                    session_id=session_id,
                    focus=focus,
                    events_limit=events_limit,
                )
                stored_source = focus or f"session:{session_id}"
            else:
                if not focus:
                    raise HTTPException(
                        status_code=400,
                        detail="Either prompt must be provided or session_id must be provided",
                    )
                model_input = focus
                stored_source = focus

            outline = await self._generate_outline(
                prompt=model_input, slide_count=slide_count
            )

            # Allocate id early so generated slide images can be stored and served by URL.
            presentation_id = str(uuid4())

            outline = await self._attach_deck_images(
                presentation_id=presentation_id,
                outline=outline,
            )

            title, deck_html = self._render_reveal_html(outline)

            settings = get_settings()
            await self.store.create_presentation(
                presentation_id,
                session_id=session_id,
                title=title,
                html=deck_html,
                outline=outline,
                source_prompt=stored_source,
                model=settings.gemini_model,
            )

            return {
                "presentation_id": presentation_id,
                "url": f"/presentations/{presentation_id}",
                "title": title,
            }
        except HTTPException:
            raise
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))

    async def list_presentations(
        self, session_id: str, limit: int
    ) -> list[dict[str, Any]]:
        try:
            rows = await self.store.list_presentations_for_session(
                session_id=session_id, limit=limit
            )
        except Exception as e:
            raise HTTPException(status_code=503, detail=f"Firestore error: {e}")

        items: list[dict[str, Any]] = []
        for r in rows:
            pid = str(r.get("presentation_id") or "")
            if not pid:
                continue
            title = str(r.get("title") or "LoreForge — Presentation")
            items.append(
                {
                    "presentation_id": pid,
                    "url": f"/presentations/{pid}",
                    "title": title,
                    "created_at": self._ts_to_str(r.get("created_at")),
                    "source_prompt": str(r.get("source_prompt"))
                    if r.get("source_prompt") is not None
                    else None,
                    "model": str(r.get("model"))
                    if r.get("model") is not None
                    else None,
                }
            )
        return items

    async def get_presentation_html(self, presentation_id: str) -> str:
        item = await self.store.get_presentation(presentation_id)
        if item is None or not item.get("html"):
            raise HTTPException(
                status_code=404, detail="Presentation not found (or expired)"
            )
        return str(item["html"])

    async def get_presentation_image(
        self, presentation_id: str, image_id: str
    ) -> tuple[bytes, str]:
        item = await self.store.get_presentation_image(presentation_id, image_id)
        if item is None:
            raise HTTPException(status_code=404, detail="Image not found")

        mime_type = str(item.get("mime_type") or "application/octet-stream")
        raw = item.get("image_bytes")
        if not isinstance(raw, bytes):
            raise HTTPException(status_code=500, detail="Invalid image payload")

        return raw, mime_type

    def _ts_to_str(self, v: Any) -> str | None:
        if v is None:
            return None
        iso = getattr(v, "format", None)
        if callable(iso):
            try:
                return str(iso())
            except Exception:
                pass
        return str(v)

    async def _build_prompt_from_session(
        self, *, session_id: str, focus: str | None, events_limit: int
    ) -> str:
        """Fetch session and recent events and format into a single model prompt."""

        session = await self.session_store.get_session(session_id)
        if not session:
            raise ValueError("Session not found")

        world_state = session.get("world_state") or {}
        inventory = session.get("inventory") or []

        # list_events returns newest-first; reverse so the model reads chronologically.
        events = await self.session_store.list_events(session_id, limit=events_limit)
        events = list(reversed(events))

        focus_line = (
            focus.strip()
            if (focus or "").strip()
            else "Create a campaign recap + next-session briefing deck."
        )

        events_lines: list[str] = []
        for ev in events:
            role = str(ev.get("role") or "?")
            kind = str(ev.get("kind") or "text")
            content = str(ev.get("content") or "").strip()
            if not content:
                continue
            # keep each line bounded
            if len(content) > 800:
                content = content[:800] + "…"
            events_lines.append(f"- [{role}:{kind}] {content}")

        return build_presentation_context_prompt(
            focus_line=focus_line,
            session_id=session_id,
            world_state=world_state,
            inventory=inventory,
            events_text="\n".join(events_lines) if events_lines else "(no events)\n",
        )

    def _render_reveal_html(self, outline: dict[str, Any]) -> tuple[str, str]:
        title = str(outline.get("title") or "LoreForge — Presentation")
        html_content = render_template(
            "presentation.html",
            title=title,
            subtitle=outline.get("subtitle"),
            slides=outline.get("slides") or [],
        )
        return title, html_content

    async def _generate_outline(
        self, *, prompt: str, slide_count: int
    ) -> dict[str, Any]:
        """Fetch a JSON outline from Gemini."""

        settings = get_settings()
        client = get_genai_client()

        contents = build_presentation_outline_prompt(
            slide_count=slide_count,
            user_prompt=prompt,
        )

        last_text = ""
        for attempt in range(3):
            # Blocking model call.
            resp = await asyncio.to_thread(
                client.models.generate_content,
                model=settings.gemini_model,
                contents=contents
                if attempt == 0
                else (
                    contents
                    + "\n\nIMPORTANT: Your previous response was invalid JSON and could not be parsed. "
                    + "Return ONLY corrected JSON (no markdown, no code fences). "
                    + "Return a COMPLETE JSON object that validates against the schema. Keep strings short.\n"
                    + "INVALID RESPONSE:\n"
                    + last_text
                ),
                config=types.GenerateContentConfig(
                    response_mime_type="application/json",
                    temperature=0.2 if attempt == 0 else 0.0,
                    max_output_tokens=3072,
                ),
            )

            last_text = getattr(resp, "text", None) or ""
            try:
                outline = coerce_json_object(last_text)
                return outline
            except Exception:
                if attempt == 2:
                    raise

        # unreachable
        raise RuntimeError("Outline generation failed")

    async def _attach_deck_images(
        self,
        *,
        presentation_id: str,
        outline: dict[str, Any],
    ) -> dict[str, Any]:
        """Generate and persist per-slide images, then attach URLs into outline."""

        settings = get_settings()
        if not settings.deck_images_enabled:
            return outline

        slides = outline.get("slides")
        if not isinstance(slides, list) or not slides:
            return outline

        client = get_genai_client()
        deck_title = str(outline.get("title") or "LoreForge")

        max_slides = max(0, int(settings.deck_images_max or 0))
        if max_slides and len(slides) > max_slides:
            slides_iter = list(enumerate(slides[:max_slides]))
        else:
            slides_iter = list(enumerate(slides))

        for idx, raw in slides_iter:
            if not isinstance(raw, dict):
                continue

            # If the model already provided a background_image URL, we keep it.
            if raw.get("background_image"):
                continue

            try:
                image_prompt = build_deck_image_prompt(deck_title=deck_title, slide=raw)

                config: dict = {
                    "number_of_images": 1,
                    "output_mime_type": settings.image_output_mime_type,
                    "aspect_ratio": settings.image_aspect_ratio,
                }
                try:
                    result: types.GenerateImagesResponse = await asyncio.to_thread(
                        client.models.generate_images,
                        model=settings.image_model,
                        prompt=image_prompt,
                        config=config,
                    )
                except Exception:
                    logging.exception("Error generating image")
                    raise

                generated = result.generated_images[0] if result.generated_images else None
                image_obj = generated.image if generated else None
                image_bytes = image_obj.image_bytes if image_obj else None
                if not image_bytes:
                    raise RuntimeError("Image model returned no image bytes")

                # Firestore doc size limit is ~1MiB; be defensive.
                if len(image_bytes) > 900_000:
                    raise RuntimeError(
                        f"Generated image too large to store in Firestore ({len(image_bytes)} bytes)"
                    )

                image_id = str(uuid4())
                alt = f"{deck_title} — {raw.get('title') or 'Slide'}"
                await self.store.create_presentation_image(
                    presentation_id,
                    image_id,
                    slide_index=idx,
                    mime_type=settings.image_output_mime_type,
                    image_bytes=image_bytes,
                    prompt=image_prompt,
                    alt=alt,
                )

                raw["background_image"] = f"/presentations/{presentation_id}/images/{image_id}"
            except Exception:
                # Best-effort: if any slide image fails, keep generating the deck.
                logging.exception("Error generating slide image")
                continue

        return outline
