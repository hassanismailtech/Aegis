"""Upstream: one shared httpx.AsyncClient posting chat completions (PRD 5.1, section 8)."""

from typing import Any

import httpx

from app.config import settings
from app.errors import aegis_error

TIMEOUT_SECONDS = 60.0


def outbound_body(body: dict[str, Any]) -> dict[str, Any]:
    """Apply UPSTREAM_MODEL_OVERRIDE (PRD 7.5); unchanged when empty."""
    if not settings.upstream_model_override:
        return body
    return {**body, "model": settings.upstream_model_override}


class Upstream:
    """Shared AsyncClient per process; transport injectable for tests."""

    def __init__(
        self, base_url: str | None = None, client: httpx.AsyncClient | None = None
    ) -> None:
        self.base_url = (base_url or settings.upstream_base_url).rstrip("/")
        self.url = f"{self.base_url}/chat/completions"
        self.client = client or httpx.AsyncClient(timeout=TIMEOUT_SECONDS, trust_env=False)

    async def aclose(self) -> None:
        await self.client.aclose()

    def _authorization(self, client_header: str | None) -> str | None:
        """Forward the client's Authorization unless UPSTREAM_API_KEY is set (PRD 5.1)."""
        if settings.upstream_api_key:
            key = settings.upstream_api_key
            return key if key.startswith("Bearer ") else f"Bearer {key}"
        return client_header

    async def chat_completions(
        self, body: dict[str, Any], client_authorization: str | None
    ) -> tuple[int, dict[str, Any]]:
        """POST the outbound body. Every Upstream error returns (status, OpenAI-shaped body)."""
        headers: dict[str, str] = {}
        authorization = self._authorization(client_authorization)
        if authorization:
            headers["Authorization"] = authorization
        try:
            response = await self.client.post(self.url, json=body, headers=headers)
        except httpx.TimeoutException:
            return 504, aegis_error(
                f"Upstream timed out after {TIMEOUT_SECONDS:.0f} s.",
                "aegis_upstream_timeout",
                err_type="api_error",
            )
        except httpx.RequestError:
            return 502, aegis_error(
                f"Upstream at {self.base_url} is unreachable.",
                "aegis_upstream_unreachable",
                err_type="api_error",
            )
        try:
            data: Any = response.json()
        except ValueError:
            data = None
        if response.status_code >= 400 and not (
            isinstance(data, dict) and isinstance(data.get("error"), dict)
        ):
            data = aegis_error(
                f"Upstream returned HTTP {response.status_code} without an OpenAI error body.",
                "aegis_upstream_error",
                err_type="api_error",
            )
        return response.status_code, data
