"""Anthropic Messages route: SDK smoke, tool_use round trip, tenant isolation.

The official `anthropic` SDK (httpx2 transport) talks to Aegis in-process; Aegis
talks to the extended mock Upstream over httpx. NER is disabled so gazetteer
and pattern numbering are deterministic, as in the OpenAI round-trip tests.
"""

from __future__ import annotations

import hashlib
import json
import uuid
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any

import anthropic
import httpx
import httpx2
import pytest
from asgi_lifespan import LifespanManager
from redis.asyncio import Redis

from app import main as aegis_main
from app.anthropic_adapter import reinject_response, scrub_request
from app.config import settings
from app.main import app as aegis_app
from app.schemas import EntityType
from app.upstream import Upstream
from scripts import mock_upstream as mock_upstream_module
from scripts.mock_upstream import app as mock_app

TOOLS: list[dict[str, Any]] = [
    {
        "name": "initiate_transfer",
        "description": "Initiate a bank transfer.",
        "input_schema": {
            "type": "object",
            "properties": {
                "name": {"type": "string"},
                "account_no": {"type": "string"},
                "amount": {"type": "number"},
            },
            "required": ["name", "account_no", "amount"],
        },
    }
]

PLANTED = ["Chinedu Okafor", "22334455667", "0123456789", "08031234567"]


class FakeSessionMap:
    """Same original -> same Placeholder, no Redis."""

    def __init__(self) -> None:
        self._rev: dict[tuple[EntityType, str], str] = {}
        self._ctr: dict[EntityType, int] = {}

    async def get_or_create_placeholder(self, entity_type: EntityType, original: str) -> str:
        key = (entity_type, original)
        if key not in self._rev:
            self._ctr[entity_type] = self._ctr.get(entity_type, 0) + 1
            self._rev[key] = f"[[{entity_type.value}_{self._ctr[entity_type]}]]"
        return self._rev[key]


def sdk_client(headers: dict[str, str] | None = None) -> anthropic.AsyncAnthropic:
    """Official SDK pointed at Aegis, the only changed setting a client needs."""
    return anthropic.AsyncAnthropic(
        api_key="sk-ant-test",
        base_url="http://aegis.test",
        http_client=httpx2.AsyncClient(
            transport=httpx2.ASGITransport(app=aegis_app), trust_env=False
        ),
        default_headers=headers,
        max_retries=0,
    )


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
async def aegis_client(
    monkeypatch: pytest.MonkeyPatch, keys_file: Path | None = None
) -> AsyncIterator[httpx.AsyncClient]:
    upstream = Upstream(
        base_url="http://mock-upstream.test/v1",
        client=httpx.AsyncClient(
            transport=httpx.ASGITransport(app=mock_app), timeout=60.0, trust_env=False
        ),
    )
    monkeypatch.setattr(aegis_main, "build_upstream", lambda: upstream)
    monkeypatch.setattr(settings, "ner_enabled", False)
    if keys_file is not None:
        monkeypatch.setattr(settings, "aegis_keys_file", str(keys_file))
    async with LifespanManager(aegis_app, startup_timeout=300):
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=aegis_app),
            base_url="http://aegis.test",
            trust_env=False,
        ) as client:
            yield client


@pytest.fixture
async def client(monkeypatch: pytest.MonkeyPatch) -> AsyncIterator[httpx.AsyncClient]:
    async with aegis_client(monkeypatch) as client:
        yield client


@pytest.fixture
async def redis_client() -> AsyncIterator[Redis]:
    client = Redis.from_url(settings.redis_url, decode_responses=True)
    yield client
    await client.aclose()


async def test_anthropic_sdk_smoke(
    client: httpx.AsyncClient, redis_client: Redis
) -> None:
    sid = "anthropic-smoke-" + uuid.uuid4().hex[:8]
    before = len(mock_upstream_module._bodies)
    sdk = sdk_client()
    try:
        message = await sdk.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=64,
            messages=[
                {
                    "role": "user",
                    "content": "Transfer 50000 to Chinedu Okafor, BVN 22334455667",
                }
            ],
            extra_headers={"X-Aegis-Session": sid},
        )
    finally:
        await sdk.close()

    assert message.type == "message"
    assert message.role == "assistant"
    assert message.content[0].type == "text"
    assert message.content[0].text == "Transfer initiated to Chinedu Okafor"

    bodies = mock_upstream_module._bodies[before:]
    assert len(bodies) == 1
    outbound = json.dumps(bodies[0])
    assert "Chinedu Okafor" not in outbound and "22334455667" not in outbound
    assert "[[PERSON_1]]" in outbound and "[[BVN_1]]" in outbound

    session = hashlib.sha256(sid.encode()).hexdigest()[:16]
    assert await redis_client.hget(f"aegis:sess:{session}:fwd", "[[PERSON_1]]") == "Chinedu Okafor"


async def test_anthropic_tool_use_round_trip(
    client: httpx.AsyncClient,
) -> None:
    sid = "anthropic-tools-" + uuid.uuid4().hex[:8]
    sdk = sdk_client()
    try:
        first = await sdk.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=128,
            messages=[
                {
                    "role": "user",
                    "content": (
                        "Wire 50000 to Chinedu Okafor from account 0123456789"
                    ),
                }
            ],
            tools=TOOLS,
            extra_headers={"X-Aegis-Session": sid},
        )

        assert first.stop_reason == "tool_use"
        tool_use = first.content[0]
        assert tool_use.type == "tool_use"
        assert tool_use.name == "initiate_transfer"
        assert tool_use.input == {
            "name": "Chinedu Okafor",
            "account_no": "0123456789",
            "amount": 75000,
        }

        second = await sdk.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=128,
            messages=[
                {
                    "role": "user",
                    "content": "Wire 50000 to Chinedu Okafor from account 0123456789",
                },
                {
                    "role": "assistant",
                    "content": [
                        {
                            "type": "tool_use",
                            "id": tool_use.id,
                            "name": tool_use.name,
                            "input": tool_use.input,
                        }
                    ],
                },
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "tool_result",
                            "tool_use_id": tool_use.id,
                            "content": "Queued for Chinedu Okafor, BVN 22334455667",
                        },
                        {
                            "type": "tool_result",
                            "tool_use_id": "toolu_other",
                            "content": [{"type": "text", "text": "Phone 08031234567"}],
                        },
                    ],
                },
            ],
            tools=TOOLS,
            extra_headers={"X-Aegis-Session": sid},
        )
    finally:
        await sdk.close()

    assert second.stop_reason == "end_turn"
    assert second.content[0].text == "Transfer initiated to Chinedu Okafor"

    taps = mock_upstream_module._bodies[-2:]
    assert len(taps) == 2
    first_tap, second_tap = (json.dumps(body) for body in taps)
    for value in PLANTED:
        assert value not in first_tap
        assert value not in second_tap
    assert "[[PERSON_1]]" in first_tap and "[[ACCOUNT_NO_1]]" in first_tap
    assert "[[PERSON_1]]" in second_tap
    assert "[[BVN_1]]" in second_tap and "[[PHONE_1]]" in second_tap


async def test_anthropic_cross_tenant_isolation(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    redis_client: Redis,
) -> None:
    path = _keys_file(tmp_path, {"tenant-a": "key-a", "tenant-b": "key-b"})
    session_header = "anthropic-shared-" + uuid.uuid4().hex[:8]
    async with aegis_client(monkeypatch, path):
        sdk_a = sdk_client({"Authorization": "Bearer key-a"})
        sdk_b = sdk_client({"Authorization": "Bearer key-b"})
        try:
            first = await sdk_a.messages.create(
                model="claude-sonnet-4-6",
                max_tokens=64,
                messages=[{"role": "user", "content": "Chinedu Okafor"}],
                extra_headers={"X-Aegis-Session": session_header},
            )
            second = await sdk_b.messages.create(
                model="claude-sonnet-4-6",
                max_tokens=64,
                messages=[{"role": "user", "content": "Ada Obi"}],
                extra_headers={"X-Aegis-Session": session_header},
            )
        finally:
            await sdk_a.close()
            await sdk_b.close()

    assert first.content[0].text == "Transfer initiated to Chinedu Okafor"
    assert second.content[0].text == "Transfer initiated to Ada Obi"
    assert "Chinedu Okafor" not in second.content[0].text

    session_a = hashlib.sha256(("tenant-a" + session_header).encode()).hexdigest()[:16]
    session_b = hashlib.sha256(("tenant-b" + session_header).encode()).hexdigest()[:16]
    assert session_a != session_b
    assert await redis_client.hget(f"aegis:sess:{session_a}:fwd", "[[PERSON_1]]") == "Chinedu Okafor"
    assert await redis_client.hget(f"aegis:sess:{session_b}:fwd", "[[PERSON_1]]") == "Ada Obi"


async def test_anthropic_adapter_scrubs_system_and_tool_results() -> None:
    fake = FakeSessionMap()
    payload = {
        "model": "claude-sonnet-4-6",
        "max_tokens": 64,
        "system": [{"type": "text", "text": "Operator: Ada Obi"}],
        "messages": [
            {
                "role": "user",
                "content": [
                    {
                        "type": "tool_result",
                        "tool_use_id": "toolu_1",
                        "content": "Call Chinedu Okafor on 08031234567",
                    },
                    {
                        "type": "tool_result",
                        "tool_use_id": "toolu_2",
                        "content": [{"type": "text", "text": "BVN 22334455667"}],
                    },
                    {"type": "image", "source": {"type": "base64", "data": "abc"}},
                ],
            }
        ],
    }
    outbound, counts, _ = await scrub_request(payload, fake, None)
    assert outbound["system"][0]["text"] == "Operator: [[PERSON_1]]"
    assert outbound["messages"][0]["content"][0]["content"] == (
        "Call [[PERSON_2]] on [[PHONE_1]]"
    )
    assert outbound["messages"][0]["content"][1]["content"][0]["text"] == "BVN [[BVN_1]]"
    assert outbound["messages"][0]["content"][2] == payload["messages"][0]["content"][2]
    assert counts[EntityType.PERSON] == 2
    assert counts[EntityType.PHONE] == 1
    assert counts[EntityType.BVN] == 1

    response = {
        "content": [
            {"type": "text", "text": "Sent to [[PERSON_2]]"},
            {
                "type": "tool_use",
                "id": "toolu_1",
                "name": "initiate_transfer",
                "input": {"customer": "[[PERSON_2]]", "bvn": "[[BVN_1]]", "amount": 5},
            },
        ]
    }
    unresolved = reinject_response(
        response, {"[[PERSON_2]]": "Chinedu Okafor", "[[BVN_1]]": "22334455667"}
    )
    assert unresolved == 0
    assert response["content"][0]["text"] == "Sent to Chinedu Okafor"
    assert response["content"][1]["input"] == {
        "customer": "Chinedu Okafor",
        "bvn": "22334455667",
        "amount": 5,
    }


async def test_anthropic_stream_and_malformed_errors_are_anthropic_shaped(
    client: httpx.AsyncClient,
) -> None:
    streamed = await client.post(
        "/v1/messages",
        json={
            "model": "claude-sonnet-4-6",
            "max_tokens": 64,
            "stream": True,
            "messages": [{"role": "user", "content": "hello"}],
        },
    )
    assert streamed.status_code == 400
    assert streamed.json()["type"] == "error"
    assert streamed.json()["error"]["type"] == "invalid_request_error"

    malformed = await client.post(
        "/v1/messages",
        content=b"{not json",
        headers={"content-type": "application/json"},
    )
    assert malformed.status_code == 400
    assert malformed.json()["type"] == "error"
    assert malformed.json()["error"]["type"] == "invalid_request_error"
