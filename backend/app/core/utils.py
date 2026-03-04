from __future__ import annotations

import ast
import json
import re
from typing import Any


def coerce_json_object(text: str) -> dict[str, Any]:
    """Strictly extract ONE JSON object from a potentially messy LLM response.

    Uses a few heuristics:
    1. Strips markdown code fences.
    2. Finds the first '{' and last '}'.
    3. Handles common LLM errors (trailing commas, Python-style booleans).
    """

    def _strip_code_fences(s: str) -> str:
        s = s.strip()
        if "```" not in s:
            return s
        s = re.sub(r"```[a-zA-Z0-9_-]*", "", s)
        return s.strip()

    def _remove_trailing_commas(s: str) -> str:
        # Remove dangling commas before } or ] (common model mistake).
        for _ in range(5):
            fixed = re.sub(r",\s*([}\]])", r"\1", s)
            if fixed == s:
                break
            s = fixed
        return s

    def _balance_braces(s: str) -> str:
        """Try to fix truncated JSON by appending missing closing characters."""
        stack = []
        for char in s:
            if char == "{":
                stack.append("}")
            elif char == "[":
                stack.append("]")
            elif char == "}":
                if stack and stack[-1] == "}":
                    stack.pop()
            elif char == "]":
                if stack and stack[-1] == "]":
                    stack.pop()
        return s + "".join(reversed(stack))

    def _try_json_loads(s: str) -> dict[str, Any] | None:
        try:
            obj = json.loads(s)
            if isinstance(obj, dict):
                return obj
        except Exception:
            pass
        return None

    cleaned = _strip_code_fences(text)

    # 1) Direct parse
    obj = _try_json_loads(cleaned)
    if obj is not None:
        return obj

    # 2) Heuristic: Find outermost braces.
    start = cleaned.find("{")
    if start == -1:
        raise ValueError("No JSON object found in response (missing '{')")

    end = cleaned.rfind("}")
    candidates = []
    if end != -1 and end > start:
        candidates.append(cleaned[start : end + 1])

    # Also try balancing everything from the first '{' to the end.
    # This handles truncated JSON where the last '}' is missing or an internal brace was found.
    full_balanced = _balance_braces(cleaned[start:])
    if not candidates or full_balanced != candidates[0]:
        candidates.append(full_balanced)

    last_exception = None
    for cand in candidates:
        # 3) Try repaired candidate
        repaired = _remove_trailing_commas(cand)
        obj = _try_json_loads(repaired)
        if obj is not None:
            return obj

        # 4) Last resort: Python-literal parse (handles single quotes / trailing commas)
        py = repaired
        py = re.sub(r"\bnull\b", "None", py)
        py = re.sub(r"\btrue\b", "True", py)
        py = re.sub(r"\bfalse\b", "False", py)
        try:
            obj2 = ast.literal_eval(py)
            if isinstance(obj2, dict):
                return obj2
        except Exception as e:
            last_exception = e

    raise ValueError(f"Invalid JSON from model (unparseable): {last_exception}")
