"""Round-trip tests (Step 2): passthrough, pseudo-stream, error mapping, Wire Tap.

Aegis runs behind httpx.ASGITransport; its Upstream client points at the mock
Upstream ASGI app (same transport). ASGITransport does not enforce httpx
timeouts (verified in httpx 0.28.1), so the timeout test drives a real socket
blackhole server instead.
"""

import asyncio
import json
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Any

import httpx
import pytest
from asgi_lifespan import LifespanManager
from fastapi import FastAPI, Request, Response
from fastapi.responses import JSONResponse
from redis.asyncio import Redis

from app import main as aegis_main
from app.config import settings
from app.main import WIRETAP_TTL_SECONDS, app as aegis_app
from app.upstream import Upstream
from scripts.mock_upstream import app as mock_app

_PAYLOAD: dict[str, Any] = {
    "model": "gpt-5-mini",
    "messages": [{"role": "user", "content": "Hello Aegis"}],
}

flaky_upstream = FastAPI()


@flaky_upstream.post("/v1/chat/completions")
async def _flaky(body: dict) -> Response:
    text = body["messages"][0]["content"]
    if text == "openai-shape":
        return JSONResponse(
            status_code=429,
            content={
                "error": {
                    "message": "rate limited",
                    "type": "rate_limit_error",
                    "param": None,
                    "code": "rate_limit_exceeded",
                }
            },
        )
    return JSONResponse(status_code=500, content={"detail": "upstream exploded"})


capture_upstream = FastAPI()
seen: dict[str, Any] = {}


@capture_upstream.post("/v1/chat/completions")
async def _capture(request: Request, body: dict) -> dict:
    seen["authorization"] = request.headers.get("authorization")
    seen["model"] = body["model"]
    return {
        "id": "chatcmpl-capture",
        "object": "chat.completion",
        "created": 0,
        "model": body["model"],
        "choices": [
            {"index": 0, "message": {"role": "assistant", "content": "ok"}, "finish_reason": "stop"}
        ],
        "usage": {"prompt_tokens": 1, "completion_tokens": 1, "total_tokens": 2},
    }


def _upstream_client(app: FastAPI, timeout: float = 60.0) -> httpx.AsyncClient:
    return httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), timeout=timeout, trust_env=False
    )


@asynccontextmanager
async def aegis_with_upstream(
    monkeypatch: pytest.MonkeyPatch, upstream: Upstream
) -> AsyncIterator[httpx.AsyncClient]:
    monkeypatch.setattr(aegis_main, "build_upstream", lambda: upstream)
    async with LifespanManager(aegis_app):
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=aegis_app),
            base_url="http://aegis.test",
            trust_env=False,
        ) as client:
            yield client


@pytest.fixture
async def client(monkeypatch: pytest.MonkeyPatch) -> AsyncIterator[httpx.AsyncClient]:
    aegis_upstream = Upstream(base_url="http://mock-upstream.test/v1", client=_upstream_client(mock_app))
    async with aegis_with_upstream(monkeypatch, aegis_upstream) as client:
        yield client


@pytest.fixture
async def redis_client() -> AsyncIterator[Redis]:
    client = Redis.from_url(settings.redis_url, decode_responses=True)
    yield client
    await client.aclose()


async def test_plain_request_round_trips(client: httpx.AsyncClient) -> None:
    response = await client.post("/v1/chat/completions", json=_PAYLOAD)
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("application/json")
    assert response.json()["choices"][0]["message"]["content"].startswith("Transfer initiated to")
    assert response.headers["X-Aegis-Request-Id"].startswith("req_")
    assert response.headers["X-Aegis-Overhead-Ms"] == "0"


async def test_stream_true_returns_valid_sse(client: httpx.AsyncClient) -> None:
    response = await client.post("/v1/chat/completions", json={**_PAYLOAD, "stream": True})
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/event-stream")
    assert response.headers["X-Aegis-Request-Id"].startswith("req_")

    events = [e for e in response.text.split("\n\n") if e.strip()]
    assert events[-1] == "data: [DONE]"
    chunks = [json.loads(e.removeprefix("data: ")) for e in events[:-1]]
    assert chunks[0]["object"] == "chat.completion.chunk"
    assert chunks[0]["id"] == chunks[1]["id"]
    assert chunks[0]["model"] == chunks[1]["model"]
    assert chunks[0]["choices"][0]["delta"]["content"] == "Transfer initiated to (no placeholder)"
    assert chunks[1]["choices"][0]["delta"] == {}
    assert chunks[1]["choices"][0]["finish_reason"] == "stop"


async def test_upstream_500_maps_to_openai_shape(monkeypatch: pytest.MonkeyPatch) -> None:
    upstream = Upstream(base_url="http://flaky.test/v1", client=_upstream_client(flaky_upstream))
    async with aegis_with_upstream(monkeypatch, upstream) as client:
        response = await client.post("/v1/chat/completions", json=_PAYLOAD)
    assert response.status_code == 500
    error = response.json()["error"]
    assert error["type"] == "api_error"
    assert error["code"] == "aegis_upstream_error"
    assert "500" in error["message"]


async def test_upstream_openai_error_passes_through(monkeypatch: pytest.MonkeyPatch) -> None:
    upstream = Upstream(base_url="http://flaky.test/v1", client=_upstream_client(flaky_upstream))
    async with aegis_with_upstream(monkeypatch, upstream) as client:
        response = await client.post(
            "/v1/chat/completions",
            json={**_PAYLOAD, "messages": [{"role": "user", "content": "openai-shape"}]},
        )
    assert response.status_code == 429
    assert response.json()["error"] == {
        "message": "rate limited",
        "type": "rate_limit_error",
        "param": None,
        "code": "rate_limit_exceeded",
    }


async def test_upstream_timeout_maps_to_504(monkeypatch: pytest.MonkeyPatch) -> None:
    server = await asyncio.start_server(lambda r, w: asyncio.sleep(5), "127.0.0.1", 0)
    try:
        port = server.sockets[0].getsockname()[1]
        upstream = Upstream(
            base_url=f"http://127.0.0.1:{port}/v1",
            client=httpx.AsyncClient(timeout=0.2, trust_env=False),
        )
        async with aegis_with_upstream(monkeypatch, upstream) as client:
            response = await client.post("/v1/chat/completions", json=_PAYLOAD)
    finally:
        # Windows: Server.wait_closed() never returns here (hangs in CPython 3.12 on
        # Win), so just close() — the ephemeral listener dies with the process.
        server.close()
    assert response.status_code == 504
    error = response.json()["error"]
    assert error["type"] == "api_error"
    assert error["code"] == "aegis_upstream_timeout"


async def test_unknown_fields_reach_upstream_unchanged(
    client: httpx.AsyncClient, redis_client: Redis
) -> None:
    payload = {
        **_PAYLOAD,
        "reasoning_effort": "high",
        "max_completion_tokens": 256,
        "temperature": 0.3,
    }
    response = await client.post("/v1/chat/completions", json=payload)
    assert response.status_code == 200
    request_id = response.headers["X-Aegis-Request-Id"]

    key = f"aegis:wiretap:{request_id}"
    tap = await client.get(f"/v1/aegis/wiretap/{request_id}")
    assert tap.status_code == 200
    assert tap.json() == {**payload, "stream": False}
    assert 0 < await redis_client.ttl(key) <= WIRETAP_TTL_SECONDS

    missing = await client.get("/v1/aegis/wiretap/req_missing")
    assert missing.status_code == 404
    assert missing.json()["error"]["code"] == "aegis_not_found"


async def test_authorization_forwarded_and_override_applied(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    upstream = Upstream(base_url="http://capture.test/v1", client=_upstream_client(capture_upstream))
    async with aegis_with_upstream(monkeypatch, upstream) as client:
        await client.post(
            "/v1/chat/completions", json=_PAYLOAD, headers={"Authorization": "Bearer sk-client"}
        )
        assert seen["authorization"] == "Bearer sk-client"
        assert seen["model"] == _PAYLOAD["model"]

        monkeypatch.setattr(settings, "upstream_api_key", "sk-fixed")
        monkeypatch.setattr(settings, "upstream_model_override", "gpt-4o-mini")
        await client.post("/v1/chat/completions", json=_PAYLOAD)
        assert seen["authorization"] == "Bearer sk-fixed"
        assert seen["model"] == "gpt-4o-mini"


async def test_malformed_body_is_openai_shaped_400(client: httpx.AsyncClient) -> None:
    response = await client.post("/v1/chat/completions", content=b"{not json", headers={
        "content-type": "application/json"
    })
    assert response.status_code == 400
    assert response.json()["error"]["code"] == "aegis_invalid_request"

    response = await client.post("/v1/chat/completions", json={"messages": []})
    assert response.status_code == 400
    assert response.json()["error"]["type"] == "invalid_request_error"
