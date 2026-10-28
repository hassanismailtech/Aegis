"""Upstream: one shared httpx.AsyncClient for OpenAI and Anthropic routes."""

from collections.abc import Callable
from typing import Any

import httpx

from app.config import settings
from app.errors import aegis_error, anthropic_error

TIMEOUT_SECONDS = 60.0
ANTHROPIC_VERSION = "2023-06-01"

_ErrorFactory = Callable[[str, str], dict[str, Any]]


def _openai_error(message: str, code: str) -> dict[str, Any]:
    return aegis_error(message, code, err_type="api_error")


def _anthropic_error(message: str, code: str) -> dict[str, Any]:
    return anthropic_error(message, "api_error")


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
        self.messages_url = f"{self.base_url}/messages"
        self.client = client or httpx.AsyncClient(timeout=TIMEOUT_SECONDS, trust_env=False)

    async def aclose(self) -> None:
        await self.client.aclose()

    async def _post(
        self,
        url: str,
        body: dict[str, Any],
        headers: dict[str, str],
        error: _ErrorFactory,
    ) -> tuple[int, Any]:
        """POST one protocol-agnostic request; transport failures use `error`."""
        try:
            response = await self.client.post(url, json=body, headers=headers)
        except httpx.TimeoutException:
            return 504, error(
                f"Upstream timed out after {TIMEOUT_SECONDS:.0f} s.", "aegis_upstream_timeout"
            )
        except httpx.RequestError:
            return 502, error(
                f"Upstream at {self.base_url} is unreachable.", "aegis_upstream_unreachable"
            )
        try:
            data: Any = response.json()
        except ValueError:
            data = None
        return response.status_code, data

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
        status, data = await self._post(self.url, body, headers, _openai_error)
        if status >= 400 and not (
            isinstance(data, dict) and isinstance(data.get("error"), dict)
        ):
            data = aegis_error(
                f"Upstream returned HTTP {status} without an OpenAI error body.",
                "aegis_upstream_error",
                err_type="api_error",
            )
        return status, data

    async def messages(
        self,
        body: dict[str, Any],
        *,
        api_key: str | None,
        version: str | None,
        beta: str | None = None,
    ) -> tuple[int, dict[str, Any]]:
        """POST an Anthropic Messages body; errors are Anthropic-shaped."""
        headers = {"anthropic-version": version or ANTHROPIC_VERSION}
        key = settings.upstream_api_key or api_key
        if key:
            headers["x-api-key"] = key.removeprefix("Bearer ").strip()
        if beta:
            headers["anthropic-beta"] = beta
        status, data = await self._post(self.messages_url, body, headers, _anthropic_error)
        if status >= 400 and not (
            isinstance(data, dict)
            and data.get("type") == "error"
            and isinstance(data.get("error"), dict)
        ):
            data = anthropic_error(
                f"Upstream returned HTTP {status} without an Anthropic error body.",
                "api_error",
            )
        return status, data
