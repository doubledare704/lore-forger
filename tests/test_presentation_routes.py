import unittest

from backend.app.api.routes.presentations import generate_presentation, list_presentations
from backend.app.api.schemas import GeneratePresentationRequest
from backend.app.web.presentations import (
    get_generated_presentation,
    get_presentation_image,
    router as presentations_router,
)


class StubPresentationService:
    def __init__(self) -> None:
        self.generate_args = None
        self.list_args = None
        self.html_request = None
        self.image_request = None

    async def generate_presentation(self, **kwargs):
        self.generate_args = kwargs
        return {
            "presentation_id": "pres-123",
            "url": "/presentations/pres-123",
            "title": "Deck Title",
        }

    async def list_presentations(self, **kwargs):
        self.list_args = kwargs
        return [
            {
                "presentation_id": "pres-123",
                "url": "/presentations/pres-123",
                "title": "Deck Title",
                "created_at": "2026-03-06T12:00:00Z",
            }
        ]

    async def get_presentation_html(self, presentation_id: str):
        self.html_request = presentation_id
        return "<html><body>deck</body></html>"

    async def get_presentation_image(self, presentation_id: str, image_id: str):
        self.image_request = (presentation_id, image_id)
        return b"img-bytes", "image/png"


class PresentationRouteTests(unittest.IsolatedAsyncioTestCase):
    async def test_generate_presentation_route_passes_request_fields(self) -> None:
        service = StubPresentationService()

        response = await generate_presentation(
            GeneratePresentationRequest(
                prompt="focus on the citadel",
                session_id="session-1",
                slide_count=7,
                events_limit=12,
            ),
            service=service,
        )

        self.assertEqual(response.presentation_id, "pres-123")
        self.assertEqual(response.url, "/presentations/pres-123")
        self.assertEqual(
            service.generate_args,
            {
                "prompt": "focus on the citadel",
                "session_id": "session-1",
                "slide_count": 7,
                "events_limit": 12,
            },
        )

    async def test_list_presentations_route_wraps_items_in_response_model(self) -> None:
        service = StubPresentationService()

        response = await list_presentations(
            session_id="session-1",
            limit=5,
            service=service,
        )

        self.assertEqual(response.session_id, "session-1")
        self.assertEqual(len(response.presentations), 1)
        self.assertEqual(response.presentations[0].presentation_id, "pres-123")
        self.assertEqual(service.list_args, {"session_id": "session-1", "limit": 5})

    async def test_generated_presentation_route_returns_html(self) -> None:
        service = StubPresentationService()

        response = await get_generated_presentation("pres-123", service=service)

        self.assertEqual(service.html_request, "pres-123")
        self.assertEqual(response.body, b"<html><body>deck</body></html>")
        self.assertIn("text/html", response.headers["content-type"])

    async def test_presentation_image_route_sets_cache_headers(self) -> None:
        service = StubPresentationService()

        response = await get_presentation_image("pres-123", "img-1", service=service)

        self.assertEqual(service.image_request, ("pres-123", "img-1"))
        self.assertEqual(response.body, b"img-bytes")
        self.assertEqual(response.headers["cache-control"], "public, max-age=31536000, immutable")
        self.assertEqual(response.headers["content-type"], "image/png")

    async def test_demo_route_is_not_registered(self) -> None:
        paths = {route.path for route in presentations_router.routes}

        self.assertNotIn("/presentations/demo", paths)
        self.assertIn("/presentations/{presentation_id}", paths)
        self.assertIn("/presentations/{presentation_id}/images/{image_id}", paths)


if __name__ == "__main__":
    unittest.main()