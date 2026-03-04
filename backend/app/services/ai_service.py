import asyncio
import threading
from typing import AsyncIterator

from backend.app.ai.client import get_genai_client
from backend.app.ai.logic import generate_scene_image, looks_like_scene_prompt
from backend.app.core.config import get_settings


class AIService:
    def __init__(self):
        self.settings = get_settings()
        self.client = get_genai_client()

    async def event_stream(
        self, prompt: str, session_id: str | None, auto_image: bool | None
    ) -> AsyncIterator[dict]:
        """SSE generator emitting interleaved events."""

        yield {
            "type": "meta",
            "model": self.settings.gemini_model,
            "session_id": session_id,
        }

        loop = asyncio.get_running_loop()
        queue: asyncio.Queue[dict] = asyncio.Queue()

        def worker() -> None:
            def emit(msg: dict) -> None:
                asyncio.run_coroutine_threadsafe(queue.put(msg), loop)

            assistant_parts: list[str] = []
            try:
                for chunk in self.client.models.generate_content_stream(
                    model=self.settings.gemini_model,
                    contents=prompt,
                ):
                    text = getattr(chunk, "text", None)
                    if text:
                        assistant_parts.append(text)
                        emit({"type": "text", "delta": text})
            except Exception as e:
                emit({"type": "error", "message": str(e)})

            # Optional image generation after text has finished streaming.
            try:
                should_auto_image = (
                    True
                    if auto_image is True
                    else False
                    if auto_image is False
                    else (
                        self.settings.auto_image_for_scenes and looks_like_scene_prompt(prompt)
                    )
                )

                assistant_text = "".join(assistant_parts)
                if should_auto_image and assistant_text.strip():
                    data_url = generate_scene_image(
                        client=self.client,
                        settings=self.settings,
                        prompt=prompt,
                        assistant_text=assistant_text,
                    )
                    emit({"type": "image", "url": data_url, "alt": "Generated scene image"})
            except Exception as e:
                # Do not fail the whole stream if image generation fails.
                emit({"type": "error", "message": f"Image generation failed: {e}"})
            finally:
                emit({"type": "done"})

        threading.Thread(target=worker, daemon=True).start()

        # Drain messages produced by the worker thread.
        while True:
            msg = await queue.get()
            yield msg
            if msg.get("type") == "done":
                break
