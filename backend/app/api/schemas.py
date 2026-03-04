from typing import Any
from pydantic import BaseModel, Field


class StreamRequest(BaseModel):
    prompt: str = Field(..., min_length=1, description="User prompt")
    session_id: str | None = Field(
        default=None, description="Optional client-provided session id"
    )

    # If None, the server may decide (e.g., based on prompt). If true/false, force enable/disable.
    auto_image: bool | None = Field(
        default=None,
        description="If true, generate 1 image and emit SSE {type:'image'}; if false, never generate an image.",
    )


class CreateSessionRequest(BaseModel):
    session_id: str | None = Field(default=None, description="Optional session id")
    world_state: dict[str, Any] = Field(default_factory=dict)
    inventory: list[Any] = Field(default_factory=list)


class SessionResponse(BaseModel):
    session_id: str
    world_state: dict[str, Any] = Field(default_factory=dict)
    inventory: list[Any] = Field(default_factory=list)


class UpdateStateRequest(BaseModel):
    world_state: dict[str, Any] | None = None
    inventory: list[Any] | None = None


class AddEventRequest(BaseModel):
    role: str = Field(..., description="e.g. user|assistant|system")
    content: str = Field(..., description="raw text for now")
    kind: str = Field(default="text", description="text|image|audio|tool|meta")


class DeriveStateRequest(BaseModel):
    events_limit: int = Field(default=50, ge=5, le=200)


class GeneratePresentationRequest(BaseModel):
    prompt: str | None = Field(
        default=None,
        description=(
            "Optional focus request for the deck. If session_id is provided, this is treated as a focus/goal. "
            "If session_id is not provided, this is the full source prompt."
        ),
    )
    session_id: str | None = Field(
        default=None,
        description="If set, build the deck from Firestore session state/events",
    )
    slide_count: int = Field(default=6, ge=3, le=12)
    events_limit: int = Field(default=30, ge=5, le=200)


class GeneratePresentationResponse(BaseModel):
    presentation_id: str
    url: str
    title: str


class PresentationListItem(BaseModel):
    presentation_id: str
    url: str
    title: str
    created_at: str | None = None
    source_prompt: str | None = None
    model: str | None = None


class ListPresentationsResponse(BaseModel):
    session_id: str
    presentations: list[PresentationListItem]
