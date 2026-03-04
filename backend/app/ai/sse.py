from __future__ import annotations

import json


def sse_json(payload: dict) -> str:
    """Serialize a JSON payload as an SSE 'data' message."""
    return f"data: {json.dumps(payload, ensure_ascii=False)}\n\n"
