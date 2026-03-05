import os
from dataclasses import dataclass


@dataclass(frozen=True)
class Settings:
    """Runtime configuration loaded from environment variables."""

    gemini_model: str
    cors_origins: list[str]

    image_model: str
    image_output_mime_type: str
    image_aspect_ratio: str
    auto_image_for_scenes: bool

    deck_images_enabled: bool
    deck_images_max: int


def get_settings() -> Settings:
    model = os.getenv("LOREFORGE_GEMINI_MODEL", "gemini-3-flash-preview")

    # Comma-separated list. Example: "http://localhost:5173,https://myapp.com"
    raw_origins = os.getenv("LOREFORGE_CORS_ORIGINS", "http://localhost:5173")
    cors_origins = [o.strip() for o in raw_origins.split(",") if o.strip()]

    image_model = os.getenv("LOREFORGE_IMAGE_MODEL", "imagen-4.0-fast-generate-001")
    image_output_mime_type = os.getenv("LOREFORGE_IMAGE_OUTPUT_MIME", "image/jpeg")
    image_aspect_ratio = os.getenv("LOREFORGE_IMAGE_ASPECT_RATIO", "16:9")
    auto_image_for_scenes = os.getenv(
        "LOREFORGE_AUTO_IMAGE_FOR_SCENES", "1"
    ).strip().lower() in (
        "1",
        "true",
        "yes",
        "on",
    )

    deck_images_enabled = os.getenv("LOREFORGE_DECK_IMAGES", "1").strip().lower() in (
        "1",
        "true",
        "yes",
        "on",
    )
    deck_images_max = int(os.getenv("LOREFORGE_DECK_IMAGES_MAX", "12"))

    return Settings(
        gemini_model=model,
        cors_origins=cors_origins,
        image_model=image_model,
        image_output_mime_type=image_output_mime_type,
        image_aspect_ratio=image_aspect_ratio,
        auto_image_for_scenes=auto_image_for_scenes,
        deck_images_enabled=deck_images_enabled,
        deck_images_max=deck_images_max,
    )
