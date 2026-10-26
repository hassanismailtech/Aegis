"""Per-tenant API key auth: valid key, invalid key, Session isolation."""

from __future__ import annotations

import hashlib
import json
import logging
import uuid
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any

import httpx
import pytest
from asgi_lifespan import LifespanManager
from fastapi import FastAPI, Request
from redis.asyncio import Redis

from app import main as aegis_main
from app.auth import load_keys
from app.config import settings
from app.main import app as aegis_app
from app.upstream import Upstream

_AUTH_UPSTREAM = FastAPI()
_upstream_state: dict[str, Any] = {"content": "ok", "authorization": None, "calls": 0}


@_AUTH_UPSTREAM.post("/v1/chat/completions")
async def _completion(request: Request, body: dict) -> dict:
    _upstream_state["authorization"] = request.headers.get("authorization")
    _upstream_state["calls"] += 1
    return {
        "id": "chatcmpl-auth",
        "object": "chat.completion",
        "created": 0,
        "model": body["model"],
        "choices": [
            {
                "index": 0,
                "message": {"role": "assistant", "content": _upstream_state["content"]},
                "finish_reason": "stop",
            }
        ],
        "usage": {"prompt_tokens": 1, "completion_tokens": 1, "total_tokens": 2},
    }


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
    monkeypatch: pytest.MonkeyPatch, path: Path, content: str = "ok"
) -> AsyncIterator[httpx.AsyncClient]:
    _upstream_state.update(content=content, authorization=None, calls=0)
    monkeypatch.setattr(settings, "aegis_keys_file", str(path))
    monkeypatch.setattr(settings, "ner_enabled", False)
    upstream = Upstream(
        base_url="http://auth-upstream.test/v1",
        client=httpx.AsyncClient(
            transport=httpx.ASGITransport(app=_AUTH_UPSTREAM),
            timeout=60.0,
            trust_env=False,
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


@pytest.fixture
async def redis_client() -> AsyncIterator[Redis]:
    client = Redis.from_url(settings.redis_url, decode_responses=True)
    yield client
    await client.aclose()


def _payload(content: str = "hello") -> dict[str, Any]:
    return {"model": "gpt-5-mini", "messages": [{"role": "user", "content": content}]}


async def test_valid_key_authenticates_and_scopes_session(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    redis_client: Redis,
) -> None:
    path = _keys_file(tmp_path, {"tenant-a": "key-a"})
    session_header = "auth-" + uuid.uuid4().hex[:8]
    async with _client(monkeypatch, path, content="[[PERSON_1]]") as client:
        response = await client.post(
            "/v1/chat/completions",
            json=_payload("Chinedu Okafor"),
            headers={
                "Authorization": "Bearer key-a",
                "X-Aegis-Session": session_header,
            },
        )
    assert response.status_code == 200
    assert response.json()["choices"][0]["message"]["content"] == "Chinedu Okafor"
    assert response.headers["X-Aegis-Unresolved"] == "0"
    assert _upstream_state["authorization"] is None  # the tenant key stays local

    expected = hashlib.sha256(("tenant-a" + session_header).encode()).hexdigest()[:16]
    assert (
        await redis_client.hget(f"aegis:sess:{expected}:fwd", "[[PERSON_1]]")
        == "Chinedu Okafor"
    )


async def test_invalid_or_missing_key_is_openai_shaped_401(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    path = _keys_file(tmp_path, {"tenant-a": "key-a"})
    async with _client(monkeypatch, path) as client:
        invalid = await client.post(
            "/v1/chat/completions",
            json=_payload(),
            headers={"Authorization": "Bearer wrong-key"},
        )
        missing = await client.post("/v1/chat/completions", json=_payload())
    for response in (invalid, missing):
        assert response.status_code == 401
        assert response.headers["www-authenticate"] == "Bearer"
        assert response.json()["error"] == {
            "message": "Aegis access token required.",
            "type": "invalid_request_error",
            "param": None,
            "code": "aegis_unauthorized",
        }
    assert _upstream_state["calls"] == 0  # rejected before anything crossed the border


async def test_tenant_cannot_resolve_another_tenants_placeholder(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    redis_client: Redis,
) -> None:
    path = _keys_file(tmp_path, {"tenant-a": "key-a", "tenant-b": "key-b"})
    session_header = "shared-" + uuid.uuid4().hex[:8]
    headers_a = {"Authorization": "Bearer key-a", "X-Aegis-Session": session_header}
    headers_b = {"Authorization": "Bearer key-b", "X-Aegis-Session": session_header}
    async with _client(monkeypatch, path, content="[[PERSON_1]]") as client:
        first = await client.post(
            "/v1/chat/completions", json=_payload("Chinedu Okafor"), headers=headers_a
        )
        second = await client.post(
            "/v1/chat/completions", json=_payload(), headers=headers_b
        )

    assert first.status_code == 200
    assert first.json()["choices"][0]["message"]["content"] == "Chinedu Okafor"

    assert second.status_code == 200
    assert second.headers["X-Aegis-Unresolved"] == "1"
    assert second.json()["choices"][0]["message"]["content"] == "[[PERSON_1]]"
    assert "Chinedu Okafor" not in second.text

    session_a = hashlib.sha256(("tenant-a" + session_header).encode()).hexdigest()[:16]
    session_b = hashlib.sha256(("tenant-b" + session_header).encode()).hexdigest()[:16]
    assert session_a != session_b
    assert await redis_client.exists(f"aegis:sess:{session_b}:fwd") == 0


def test_unset_keys_file_warns_and_disables_auth(
    caplog: pytest.LogCaptureFixture,
) -> None:
    with caplog.at_level(logging.WARNING, logger="aegis.auth"):
        assert load_keys("") is None
    assert "AEGIS_KEYS_FILE is not set" in caplog.text


def test_invalid_keys_file_fails_fast(tmp_path: Path) -> None:
    path = tmp_path / "aegis-keys.json"
    path.write_text('[{"tenant_id": "tenant-a", "key_sha256": "not-a-hash"}]')
    with pytest.raises(RuntimeError):
        load_keys(str(path))
