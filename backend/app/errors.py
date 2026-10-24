"""OpenAI-shaped error bodies (PRD 7.4)."""

from typing import Any


def aegis_error(
    message: str, code: str, err_type: str = "invalid_request_error", param: str | None = None
) -> dict[str, Any]:
    return {"error": {"message": message, "type": err_type, "param": param, "code": code}}
