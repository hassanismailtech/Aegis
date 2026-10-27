"""Round-trip tests (Step 2): passthrough, pseudo-stream, error mapping, Wire Tap.

Aegis runs behind httpx.ASGITransport; its Upstream client points at the mock
Upstream ASGI app (same transport). ASGITransport does not enforce httpx
timeouts (verified in httpx 0.28.1), so the timeout test drives a real socket
blackhole server instead.
"""

import asyncio
import json
import uuid
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Any

import httpx
import pytest
from asgi_lifespan import LifespanManager
from fastapi import FastAPI, Request, Response
from fastapi.responses import JSONResponse
from redis.asyncio import Redis
from redis.exceptions import RedisError

from app import main as aegis_main
from app.config import settings
from app.errors import ScrubError
from app.main import WIRETAP_TTL_SECONDS, app as aegis_app
from app.session_map import SessionMap
from app.upstream import Upstream
from scripts import mock_upstream as mock_upstream_module
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
    # GLiNER warms in lifespan (PRD 5.2): the one-time load needs > asgi-lifespan's 5s default.
    async with LifespanManager(aegis_app, startup_timeout=300):
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
    assert 0.0 <= float(response.headers["X-Aegis-Overhead-Ms"]) <= settings.ner_timeout_ms
    assert response.headers["X-Aegis-Entities"].isdigit()


async def test_stream_true_returns_valid_sse(
    client: httpx.AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(settings, "ner_enabled", False)  # passthrough test: no NER
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


async def test_stream_true_preserves_tool_call_delta(
    client: httpx.AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(settings, "ner_enabled", False)
    response = await client.post(
        "/v1/chat/completions",
        json={
            "model": "gpt-5-mini",
            "stream": True,
            "messages": [{"role": "user", "content": "Look up Ada Obi"}],
            "tools": [
                {
                    "type": "function",
                    "function": {
                        "name": "lookup_customer",
                        "parameters": {"type": "object", "properties": {"name": {"type": "string"}}},
                    },
                }
            ],
        },
    )
    events = [e for e in response.text.split("\n\n") if e.strip()]
    chunks = [json.loads(e.removeprefix("data: ")) for e in events[:-1]]
    tool_delta = chunks[1]["choices"][0]["delta"]["tool_calls"][0]
    assert tool_delta["function"]["name"] == "lookup_customer"
    assert chunks[2]["choices"][0]["finish_reason"] == "tool_calls"


async def test_client_placeholder_cannot_reinject_session_value(
    client: httpx.AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(settings, "ner_enabled", False)
    session = "placeholder-injection-" + uuid.uuid4().hex[:8]
    first = await client.post(
        "/v1/chat/completions",
        json={"model": "gpt-5-mini", "messages": [{"role": "user", "content": "Chinedu Okafor"}]},
        headers={"X-Aegis-Session": session},
    )
    assert first.status_code == 200
    second = await client.post(
        "/v1/chat/completions",
        json={
            "model": "gpt-5-mini",
            "messages": [{"role": "user", "content": "literal [[PERSON_1]]"}],
        },
        headers={"X-Aegis-Session": session},
    )
    assert second.status_code == 200
    assert "Chinedu Okafor" not in second.text


async def test_demo_token_protects_operational_routes(
    client: httpx.AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(settings, "aegis_demo_token", "test-secret")
    denied = await client.get("/v1/aegis/stats")
    assert denied.status_code == 401
    allowed = await client.get(
        "/v1/aegis/stats", headers={"X-Aegis-Demo-Token": "test-secret"}
    )
    assert allowed.status_code == 200


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
    client: httpx.AsyncClient,
    redis_client: Redis,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(settings, "ner_enabled", False)  # passthrough test: no NER
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


async def test_scrubber_replaces_pii_before_upstream(client: httpx.AsyncClient) -> None:
    """Step 3: Nigerian PII becomes Placeholders; Wire Tap proves it (PRD 3)."""
    planted = ["Chinedu Okafor", "22334455667", "0803 123 4567", "ada@obi.ng"]
    payload = {
        **_PAYLOAD,
        "messages": [
            {
                "role": "user",
                "content": (
                    "Transfer 50000 to Chinedu Okafor, BVN 22334455667, "
                    "phone 0803 123 4567, email ada@obi.ng"
                ),
            }
        ],
    }
    response = await client.post(
        "/v1/chat/completions",
        json=payload,
        headers={"X-Aegis-Session": "step3-wiring-pii"},
    )
    assert response.status_code == 200
    entity_count = response.headers["X-Aegis-Entities"]
    assert entity_count.isdigit() and int(entity_count) >= 4

    request_id = response.headers["X-Aegis-Request-Id"]
    tap = await client.get(f"/v1/aegis/wiretap/{request_id}")
    assert tap.status_code == 200
    outbound = json.dumps(tap.json())
    for value in planted:
        assert value not in outbound
    assert "[[PERSON_1]]" in outbound and "[[BVN_1]]" in outbound
    assert "[[PHONE_1]]" in outbound and "[[EMAIL_1]]" in outbound


async def test_tool_call_round_trip_reinjects_arguments(
    client: httpx.AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Step 4: mock Upstream tool mode returns arguments with Placeholders; the
    client still receives the real values (PRD 3 step 5, PRD 5.4).

    NER is off: the gazetteer covers the planted names deterministically."""
    monkeypatch.setattr(settings, "ner_enabled", False)
    planted = ["Chinedu Okafor", "22334455667", "08031234567"]  # checked: sees order
    payload = {
        **_PAYLOAD,
        "messages": [
            {
                "role": "user",
                "content": "Book transfer 50000: to Chinedu Okafor, BVN 22334455667, phone 08031234567",
            }
        ],
        "tools": [
            {
                "type": "function",
                "function": {
                    "name": "initiate_transfer",
                    "parameters": {"type": "object", "properties": {}},
                },
            }
        ],
    }
    response = await client.post("/v1/chat/completions", json=payload)
    assert response.status_code == 200
    assert response.headers["X-Aegis-Unresolved"] == "0"
    tool_calls = response.json()["choices"][0]["message"]["tool_calls"]
    arguments = json.loads(tool_calls[0]["function"]["arguments"])
    assert arguments == {"placeholders": planted}


async def test_second_turn_rescrubs_history_to_same_placeholders(
    client: httpx.AsyncClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Step 4 item 4: multi-turn — the agent resends history that now contains
    reinjected real values; the Scrubber must reuse the same Placeholders.

    NER is off: gazetteer + patterns give deterministic numbering."""
    monkeypatch.setattr(settings, "ner_enabled", False)
    sid = "step4-multiturn-" + uuid.uuid4().hex[:8]
    first = "Wire 50000 to Chinedu Okafor from account 0123456789."
    r1 = await client.post(
        "/v1/chat/completions",
        json={**_PAYLOAD, "messages": [{"role": "user", "content": first}]},
        headers={"X-Aegis-Session": sid},
    )
    assert r1.status_code == 200
    reply = r1.json()["choices"][0]["message"]  # client saw REINJECTED real values
    assert "Chinedu Okafor" in reply["content"]

    r2 = await client.post(
        "/v1/chat/completions",
        json={
            **_PAYLOAD,
            "messages": [
                {"role": "user", "content": first},
                {"role": "assistant", "content": reply["content"]},
                {"role": "user", "content": "Confirm the transfer to Chinedu Okafor."},
            ],
        },
        headers={"X-Aegis-Session": sid},
    )
    assert r2.status_code == 200
    tap = await client.get(f"/v1/aegis/wiretap/{r2.headers['X-Aegis-Request-Id']}")
    outbound = json.dumps(tap.json())
    assert "[[PERSON_1]]" in outbound  # same numbering as turn 1, never PERSON_2
    assert "[[ACCOUNT_NO_1]]" in outbound
    assert "Chinedu Okafor" not in outbound and "0123456789" not in outbound


async def test_redis_flush_between_scrub_and_reinject_is_state_loss(
    client: httpx.AsyncClient,
    redis_client: Redis,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """PRD 8: Placeholder missing from the Session Map at reinjection (flush)
    -> reply keeps Placeholders, HTTP 200, X-Aegis-Unresolved, telemetry state_loss."""
    real_forward_map = SessionMap.forward_map

    async def flush_then_load(self: SessionMap) -> dict[str, str]:
        await redis_client.flushdb()  # map lost mid-request, after Scrub
        return await real_forward_map(self)

    monkeypatch.setattr(SessionMap, "forward_map", flush_then_load)
    response = await client.post(
        "/v1/chat/completions",
        json={
            **_PAYLOAD,
            "messages": [{"role": "user", "content": "Transfer 50000 to Chinedu Okafor, BVN 22334455667"}],
        },
        headers={"X-Aegis-Session": "step4-flush-" + uuid.uuid4().hex[:8]},
    )
    assert response.status_code == 200
    assert response.headers["X-Aegis-Unresolved"] == "1"
    content = response.json()["choices"][0]["message"]["content"]
    assert "Chinedu Okafor" not in content
    assert "[[PERSON_1]]" in content  # degraded reply, never guessed PII

    entries = await redis_client.xrevrange("aegis:events", count=1)
    assert entries, "telemetry event recorded"
    fields = dict(entries[0][1])
    assert fields["status"] == "state_loss"
    assert fields["unresolved"] == "1"


async def test_scrub_failure_blocks_request(monkeypatch: pytest.MonkeyPatch) -> None:
    """PRD 8: ScrubError blocks fail-closed — 503, nothing sent Upstream."""

    async def boom(*args: object, **kwargs: object) -> object:
        raise ScrubError("simulated NER timeout")

    monkeypatch.setattr(aegis_main, "scrub_messages", boom)
    async with aegis_with_upstream(monkeypatch, Upstream(
        base_url="http://mock-upstream.test/v1", client=_upstream_client(mock_app)
    )) as client:
        response = await client.post("/v1/chat/completions", json=_PAYLOAD)
        assert response.status_code == 503
        assert response.json()["error"]["code"] == "aegis_scrub_failed"
        tap = await client.get("/v1/aegis/wiretap/req_missing")
        assert tap.status_code == 404  # nothing was stored or sent


async def test_redis_failure_blocks_request(monkeypatch: pytest.MonkeyPatch) -> None:
    """PRD 8: Redis down before Upstream → 503 aegis_state_unavailable, and the
    mock Upstream /_tap stays empty: nothing ever crossed the border."""

    async def boom(*args: object, **kwargs: object) -> object:
        raise RedisError("simulated outage")

    monkeypatch.setattr(aegis_main, "scrub_messages", boom)
    bodies_before = len(mock_upstream_module._bodies)
    async with aegis_with_upstream(monkeypatch, Upstream(
        base_url="http://mock-upstream.test/v1", client=_upstream_client(mock_app)
    )) as client:
        response = await client.post("/v1/chat/completions", json=_PAYLOAD)
        assert response.status_code == 503
        assert response.json()["error"]["code"] == "aegis_state_unavailable"
        tap = await client.get("/v1/aegis/wiretap/req_missing")
        assert tap.status_code == 404  # nothing was stored or sent
        assert len(mock_upstream_module._bodies) == bodies_before  # /_tap unchanged


async def test_readyz_ready_when_redis_and_ner_are_up(client: httpx.AsyncClient) -> None:
    response = await client.get("/readyz")
    assert response.status_code == 200
    assert response.json() == {"status": "ready", "redis": "ok", "ner": "warm"}


async def test_readyz_fails_when_redis_is_down(
    client: httpx.AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    async def down(_: Redis) -> bool:
        raise RedisError("simulated outage")

    monkeypatch.setattr(Redis, "ping", down)
    response = await client.get("/readyz")
    assert response.status_code == 503
    assert response.json() == {
        "status": "not_ready",
        "redis": "unavailable",
        "ner": "warm",
    }


async def test_readyz_fails_when_ner_is_enabled_but_not_warm(
    client: httpx.AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(settings, "ner_enabled", True)
    monkeypatch.setattr(aegis_app.state, "ner", None)
    response = await client.get("/readyz")
    assert response.status_code == 503
    assert response.json()["ner"] == "not_warm"


async def test_readyz_skips_ner_when_disabled(
    client: httpx.AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(settings, "ner_enabled", False)
    monkeypatch.setattr(aegis_app.state, "ner", None)
    response = await client.get("/readyz")
    assert response.status_code == 200
    assert response.json() == {"status": "ready", "redis": "ok", "ner": "disabled"}
