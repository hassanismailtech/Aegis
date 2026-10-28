"""Request limits: body size, message count and per-tenant token bucket."""

from __future__ import annotations

import hashlib
import json
import uuid
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any

import httpx
import pytest
from asgi_lifespan import LifespanManager

from app import main as aegis_main
from app.config import settings
from app.main import app as aegis_app
from app.upstream import Upstream
from scripts.mock_upstream import app as mock_app


def _keys_file(tmp_path: Path, keys: dict[str, str]) -> Path:
    path = tmp_path / "aegis-keys.json"
    path.write_text(
        json.dumps(
            [
                {
                    "tenant_id": tenant_id,
                    "key_sha256": hashlib.sha256(key.encode()).hexdigest(),
                }
                for tenant_id, key in keys.items()
            ]
        ),
        encoding="utf-8",
    )
    return path


@asynccontextmanager
async def _client(
    monkeypatch: pytest.MonkeyPatch, path: Path | None = None
) -> AsyncIterator[httpx.AsyncClient]:
    monkeypatch.setattr(settings, "aegis_keys_file", str(path) if path else "")
    if path:
        monkeypatch.setattr(settings, "aegis_ticket_secret", "test-limits-ticket-secret")
    monkeypatch.setattr(settings, "ner_enabled", False)
    upstream = Upstream(
        base_url="http://mock-upstream.test/v1",
        client=httpx.AsyncClient(
            transport=httpx.ASGITransport(app=mock_app), timeout=60.0, trust_env=False
        ),
    )
    monkeypatch.setattr(aegis_main, "build_upstream", lambda: upstream)
    async with LifespanManager(aegis_app, startup_timeout=300):
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=aegis_app),
            base_url="http://aegis.test",
            trust_env=False,
        ) as client:
            yield client


def _payload(content: str = "hello") -> dict[str, Any]:
    return {"model": "gpt-5-mini", "messages": [{"role": "user", "content": content}]}


async def test_body_size_limit_is_openai_shaped_413(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    path = _keys_file(tmp_path, {"tenant-a": "key-a"})
    monkeypatch.setattr(settings, "max_body_bytes", 256)
    async with _client(monkeypatch, path) as client:
        response = await client.post(
            "/v1/chat/completions",
            json=_payload("x" * 500),
            headers={"Authorization": "Bearer key-a"},
        )
    assert response.status_code == 413
    assert response.json()["error"]["code"] == "aegis_request_too_large"
    assert response.json()["error"]["type"] == "invalid_request_error"


async def test_message_count_limit_is_openai_shaped_400(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    path = _keys_file(tmp_path, {"tenant-a": "key-a"})
    monkeypatch.setattr(settings, "max_messages", 2)
    messages = [{"role": "user", "content": f"message {index}"} for index in range(3)]
    async with _client(monkeypatch, path) as client:
        response = await client.post(
            "/v1/chat/completions",
            json={"model": "gpt-5-mini", "messages": messages},
            headers={"Authorization": "Bearer key-a"},
        )
    assert response.status_code == 400
    assert response.json()["error"]["code"] == "aegis_too_many_messages"


async def test_rate_limit_is_per_tenant_and_returns_429(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    tenant_a = "rate-a-" + uuid.uuid4().hex[:8]
    tenant_b = "rate-b-" + uuid.uuid4().hex[:8]
    path = _keys_file(tmp_path, {tenant_a: "key-a", tenant_b: "key-b"})
    monkeypatch.setattr(settings, "rate_limit_capacity", 2)
    monkeypatch.setattr(settings, "rate_limit_refill_per_second", 0.001)
    headers_a = {"Authorization": "Bearer key-a"}
    headers_b = {"Authorization": "Bearer key-b"}
    async with _client(monkeypatch, path) as client:
        first = await client.post("/v1/chat/completions", json=_payload(), headers=headers_a)
        second = await client.post("/v1/chat/completions", json=_payload(), headers=headers_a)
        limited = await client.post("/v1/chat/completions", json=_payload(), headers=headers_a)
        other_tenant = await client.post(
            "/v1/chat/completions", json=_payload(), headers=headers_b
        )

    assert first.status_code == 200 and second.status_code == 200
    assert first.headers["X-RateLimit-Limit"] == "2"
    assert second.headers["X-RateLimit-Remaining"] == "0"
    assert limited.status_code == 429
    assert int(limited.headers["Retry-After"]) >= 1
    error = limited.json()["error"]
    assert error["type"] == "rate_limit_error"
    assert error["code"] == "aegis_rate_limited"
    assert other_tenant.status_code == 200  # tenant B has its own bucket


async def test_local_mode_skips_tenant_rate_limit(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "rate_limit_capacity", 1)
    monkeypatch.setattr(settings, "rate_limit_refill_per_second", 0.001)
    async with _client(monkeypatch) as client:
        first = await client.post("/v1/chat/completions", json=_payload())
        second = await client.post("/v1/chat/completions", json=_payload())
    assert first.status_code == 200 and second.status_code == 200
