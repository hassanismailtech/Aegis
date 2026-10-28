"""OpenAI-shaped error bodies (PRD 7.4) and Scrubber failure type (PRD 8)."""

from typing import Any


class ScrubError(Exception):
    """Scrubber failure (pattern/gazetteer/NER); requests fail closed (PRD 8)."""


def aegis_error(
    message: str, code: str, err_type: str = "invalid_request_error", param: str | None = None
) -> dict[str, Any]:
    return {"error": {"message": message, "type": err_type, "param": param, "code": code}}


def anthropic_error(message: str, err_type: str = "invalid_request_error") -> dict[str, Any]:
    """Anthropic-shaped error body (the Messages SDK parses this shape)."""
    return {"type": "error", "error": {"type": err_type, "message": message}}
