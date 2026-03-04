from __future__ import annotations

from fastapi import APIRouter, Depends, Response
from fastapi.responses import HTMLResponse

from backend.app.services import get_presentation_service, PresentationService


router = APIRouter(prefix="/presentations")


@router.get("/demo", response_class=HTMLResponse)
def demo_presentation() -> HTMLResponse:
    """Minimal Reveal.js demo deck.

    Step 5.1: verify rendering + separate-tab open.
    Step 5.2 will generate dynamic decks from the agent.
    """

    html = """<!doctype html>
<html lang=\"en\">
  <head>
    <meta charset=\"utf-8\" />
    <meta name=\"viewport\" content=\"width=device-width, initial-scale=1.0\" />
    <title>LoreForge — Demo Deck</title>
    <link rel=\"stylesheet\" href=\"https://cdn.jsdelivr.net/npm/reveal.js@5/dist/reveal.css\" />
    <link rel=\"stylesheet\" href=\"https://cdn.jsdelivr.net/npm/reveal.js@5/dist/theme/black.css\" />
    <style>
      :root { color-scheme: dark; }
      .reveal .slides { font-family: ui-serif, Georgia, serif; }
      .reveal h2, .reveal h3 { letter-spacing: 0.02em; }
      .reveal .lore { color: #d6b35f; }
      .reveal .muted { color: #bcae8a; font-size: 0.75em; }
    </style>
  </head>
  <body>
    <div class=\"reveal\">
      <div class=\"slides\">
        <section>
          <h2 class=\"lore\">LoreForge</h2>
          <p class=\"muted\">Reveal.js demo deck (served by FastAPI)</p>
        </section>
        <section>
          <h3>World Pillars</h3>
          <ul>
            <li>Tone: candlelit mystery</li>
            <li>Conflict: ancient oaths awakening</li>
            <li>Play loop: explore → bargain → unveil</li>
          </ul>
        </section>
        <section>
          <h3>Next</h3>
          <p>Step 5.2 will generate slides from the agent and open them automatically.</p>
        </section>
      </div>
    </div>

    <script src=\"https://cdn.jsdelivr.net/npm/reveal.js@5/dist/reveal.js\"></script>
    <script>
      Reveal.initialize({
        hash: true,
        controls: true,
        progress: true,
        transition: 'fade'
      });
    </script>
  </body>
</html>"""

    return HTMLResponse(content=html)


@router.get("/{presentation_id}", response_class=HTMLResponse)
async def get_generated_presentation(
    presentation_id: str,
    service: PresentationService = Depends(get_presentation_service),
) -> HTMLResponse:
    content = await service.get_presentation_html(presentation_id)
    return HTMLResponse(content=content)


@router.get("/{presentation_id}/images/{image_id}")
async def get_presentation_image(
    presentation_id: str,
    image_id: str,
    service: PresentationService = Depends(get_presentation_service),
) -> Response:
    data, mime_type = await service.get_presentation_image(presentation_id, image_id)

    return Response(
        content=data,
        media_type=mime_type,
        headers={"Cache-Control": "public, max-age=31536000, immutable"},
    )

