import base64
import json
import logging
import re
from typing import Any

from google import genai
from backend.app.core.config import Settings


DEFAULT_NEGATIVE_PROMPT = (
    "text, letters, words, alphabet, characters, script, calligraphy, label, tag, branding, "
    "overlaid text, captions, subtitles, title, watermark, signature, logo, "
    "website, URL, UI, HUD, menu, digital lettering, floating letters, typography"
)

STATE_DERIVATION_SYSTEM_PROMPT = (
    "You are LoreForge's world-state steward.\n"
    "Update and maintain an OPINIONATED campaign state and inventory for an RPG.\n\n"
    "Return ONLY valid JSON (no markdown, no prose).\n"
    "Return an object with EXACTLY two keys: world_state and inventory.\n"
    "Keep it compact: prefer <= 8 entries per list; dedupe by name; preserve stable naming.\n"
    "If something is unknown, use empty string or omit optional fields, but keep the overall structure."
)

PRESENTATION_CONTEXT_SYSTEM_PROMPT = (
    "You are generating a Reveal.js slide deck for an RPG world building app.\n"
    "Use the CANONICAL WORLD STATE and INVENTORY below as the primary source of truth.\n"
    "Use RECENT EVENTS only to: (a) add recency/context, (b) pick highlights, (c) validate.\n"
    "If something is in events but not represented in canonical state, treat it as uncertain and avoid inventing details."
)

PRESENTATION_OUTLINE_INSTRUCTION = (
    "Return ONLY valid JSON (no markdown, no code fences). "
    "Create a concise Reveal.js slide outline for an RPG world building presentation. "
    "Use exactly {slide_count} slides (not counting the title slide). "
    "Each slide: 3-6 bullets. Keep bullets short. "
    "If helpful, add brief speaker notes in 'notes'. "
    "IMPORTANT: Ensure JSON is strictly valid and complete (no truncated output, no dangling quotes, no trailing commas). "
    "If you need quotes inside strings, escape them."
)


def looks_like_scene_prompt(prompt: str) -> bool:
    """Minimal heuristic: user explicitly says "scene"."""
    return bool(re.search(r"\bscene\b", prompt, flags=re.IGNORECASE))


def build_image_prompt(*, user_prompt: str, assistant_text: str) -> str:
    """Build a prompt for Imagen from user request and assistant lore."""
    assistant_excerpt = assistant_text.strip().replace("\n", " ")
    if len(assistant_excerpt) > 600:
        assistant_excerpt = assistant_excerpt[:600].rsplit(" ", 1)[0] + "…"

    return (
        "Create a single cinematic fantasy illustration. "
        "Atmospheric, dramatic lighting, high detail. "
        "NO OVERLAID TEXT, NO LETTERS, NO WORDS, NO UI, NO LOGOS. "
        "Clean cinematic landscape or interior view. "
        "The image should visually depict the following scene elements, but do NOT include any text overlays: "
        f"Prompt: {user_prompt.strip()}\n"
        f"Description: {assistant_excerpt}\n"
        "Ensure no digital overlays, watermarks, or typography are present. "
        "If a building or structure naturally contains a sign or weathered inscription, it must be environmental and not an overlay."
    )


def build_deck_image_prompt(*, deck_title: str, slide: dict[str, Any]) -> str:
    """Build a prompt for a presentation slide background image."""
    title = str(slide.get("title") or "")
    kind = str(slide.get("kind") or "")
    bullets = slide.get("bullets")
    if not isinstance(bullets, list):
        bullets = []
    bullets_txt = " ".join(str(b).strip() for b in bullets if str(b).strip())
    if len(bullets_txt) > 600:
        bullets_txt = bullets_txt[:600].rsplit(" ", 1)[0] + "…"

    return (
        "Create a single cinematic fantasy illustration as a clean background plate for a presentation slide. "
        "Atmospheric, dramatic lighting, high detail. "
        "STRICTLY NO OVERLAID TEXT, NO LETTERS, NO WORDS, NO UI. "
        "Clean scenic view without any digital typography or watermarks. "
        "The image should visually represent these themes: "
        f"Context: {deck_title}, {title}. "
        + (f"Kind: {kind}. " if kind else "")
        + (f"Details: {bullets_txt}" if bullets_txt else "")
        + "\nEnvironmental writing on buildings or structures is acceptable if it looks natural and weathered, but NO digital text overlays."
    )


STATE_DERIVATION_SCHEMA_HINT = {
    "world_state": {
        "campaign": {"title": "string", "premise": "string", "tone": "string"},
        "locations": [
            {
                "name": "string",
                "description": "string",
                "tags": ["string"],
                "status": "string",
            }
        ],
        "npcs": [
            {
                "name": "string",
                "role": "string",
                "description": "string",
                "location": "string",
                "status": "string",
                "goals": ["string"],
            }
        ],
        "factions": [
            {
                "name": "string",
                "description": "string",
                "goals": ["string"],
                "relationships": [{"with": "string", "relation": "string"}],
            }
        ],
        "quests": [
            {
                "name": "string",
                "status": "open|completed|failed|paused",
                "summary": "string",
                "next_steps": ["string"],
                "involved_npcs": ["string"],
                "locations": ["string"],
            }
        ],
        "facts": ["string"],
        "open_questions": ["string"],
        "next_session": {
            "objective": "string",
            "scenes": ["string"],
            "hooks": ["string"],
        },
    },
    "inventory": [
        {
            "name": "string",
            "qty": "number",
            "description": "string",
            "tags": ["string"],
        }
    ],
}


def build_state_derivation_prompt(
    *,
    current_world_state: dict[str, Any],
    current_inventory: list[Any],
    events_text: str,
) -> str:
    """Build a prompt for Gemini to derive updated world state/inventory."""
    return (
        f"{STATE_DERIVATION_SYSTEM_PROMPT}\n\n"
        f"SCHEMA HINT (types only):\n{json.dumps(STATE_DERIVATION_SCHEMA_HINT, ensure_ascii=False)}\n\n"
        f"CURRENT STATE world_state:\n{json.dumps(current_world_state, ensure_ascii=False, default=str)}\n\n"
        f"CURRENT STATE inventory:\n{json.dumps(current_inventory, ensure_ascii=False, default=str)}\n\n"
        f"RECENT EVENTS (chronological):\n{events_text}"
    )


def build_presentation_context_prompt(
    *,
    focus_line: str,
    session_id: str,
    world_state: dict[str, Any],
    inventory: list[Any],
    events_text: str,
) -> str:
    """Build a prompt for Gemini with full session context for deck generation."""
    return (
        f"{PRESENTATION_CONTEXT_SYSTEM_PROMPT}\n\n"
        f"DECK GOAL: {focus_line}\n"
        f"SESSION ID: {session_id}\n\n"
        "CANONICAL WORLD STATE (JSON):\n"
        + json.dumps(world_state, ensure_ascii=False, default=str)
        + "\n\nCANONICAL INVENTORY (JSON):\n"
        + json.dumps(inventory, ensure_ascii=False, default=str)
        + "\n\nRECENT EVENTS (chronological):\n"
        + events_text
    )


PRESENTATION_OUTLINE_SCHEMA = {
    "title": "string",
    "subtitle": "string (optional)",
    "slides": [
        {
            "title": "string",
            "kind": "string (optional short label like Scene|Faction|Location)",
            "bullets": ["string", "..."],
            "callout": "string (optional, a memorable tagline/quote)",
            "notes": "string (optional)",
            "background_color": "string (optional, e.g. #1a1410)",
            "background_image": "string (optional URL)",
            "transition": "string (optional, e.g. fade|slide|convex)",
        }
    ],
}


def build_presentation_outline_prompt(
    *,
    slide_count: int,
    user_prompt: str,
) -> str:
    """Build a prompt for Gemini to generate a slide deck outline."""
    return (
        f"SYSTEM INSTRUCTION:\n{PRESENTATION_OUTLINE_INSTRUCTION.format(slide_count=slide_count)}\n\n"
        f"JSON SCHEMA (informal):\n{json.dumps(PRESENTATION_OUTLINE_SCHEMA)}\n\n"
        f"USER REQUEST:\n{user_prompt}\n"
    )


def generate_scene_image(
    client: genai.Client,
    settings: Settings,
    prompt: str,
    assistant_text: str,
) -> str:
    """Generate an image via Imagen and return it as a data URL."""

    image_prompt = build_image_prompt(
        user_prompt=prompt,
        assistant_text=assistant_text,
    )

    config: dict = {
        "number_of_images": 1,
        "output_mime_type": settings.image_output_mime_type,
    }
    # Aspect ratio is only supported on some Imagen model variants.
    if settings.image_aspect_ratio and settings.image_model.startswith("imagen-4"):
        config["aspect_ratio"] = settings.image_aspect_ratio

    try:
        result = client.models.generate_images(
            model=settings.image_model,
            prompt=image_prompt,
            config=config,
        )
    except Exception:
        logging.exception("Error generating image")
        raise

    generated = (getattr(result, "generated_images", None) or [None])[0]
    image_obj = getattr(generated, "image", None) if generated else None
    image_bytes = getattr(image_obj, "image_bytes", None) if image_obj else None
    if not image_bytes:
        raise RuntimeError("Image model returned no image bytes")

    b64 = base64.b64encode(image_bytes).decode("ascii")
    return f"data:{settings.image_output_mime_type};base64,{b64}"
