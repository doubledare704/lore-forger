import unittest

from backend.app.ai.logic import (
    DEFAULT_NEGATIVE_PROMPT,
    build_deck_image_prompt,
    build_image_prompt,
)


class PromptGuardrailTests(unittest.TestCase):
    def test_scene_image_prompt_strongly_forbids_readable_text(self) -> None:
        prompt = build_image_prompt(
            user_prompt="Generate a scene in an icy fortress",
            assistant_text="Frozen arches and torchlight reflect across the hall.",
        ).lower()

        self.assertIn("no readable text of any kind", prompt)
        self.assertIn(DEFAULT_NEGATIVE_PROMPT.lower(), prompt)
        self.assertIn("blank, obscured, or abstract and unreadable", prompt)
        self.assertIn(
            "never present the image as a poster, title card, labeled map, manuscript, or ui screen",
            prompt,
        )

    def test_deck_image_prompt_forbids_text_bearing_objects(self) -> None:
        prompt = build_deck_image_prompt(
            deck_title="The Frost March",
            slide={
                "title": "Citadel Approach",
                "kind": "Scene",
                "bullets": ["Ice walls", "Aurora overhead", "Travelers at the gate"],
            },
        ).lower()

        self.assertIn("background art only", prompt)
        self.assertIn("no readable text of any kind", prompt)
        self.assertIn("avoid books, scrolls, signs, banners", prompt)
        self.assertIn("readable runes", prompt)


if __name__ == "__main__":
    unittest.main()