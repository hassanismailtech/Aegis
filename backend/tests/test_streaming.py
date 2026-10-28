"""True streaming (Phase 3.2/3.3): hold-back, split Placeholders, both protocols."""

from __future__ import annotations

import json
import uuid
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Any

import anthropic
import httpx
import httpx2
import pytest
from asgi_lifespan import LifespanManager
from redis.asyncio import Redis

from app import main as aegis_main
from app.config import settings
from app.main import app as aegis_app
from app.reinjector import HOLDBACK_CHARS, StreamingReinjector
from app.streaming import OpenAIStreamRewriter
from app.upstream import Upstream
from scripts.mock_upstream import app as mock_app

FORWARD = {"[[PERSON_1]]": "Chinedu Okafor", "[[PERSON_2]]": "Ada Obi"}

# Every tolerant row from PRD 7.1 that must resolve to [[PERSON_1]]'s value.
TOLERANT_FORMS = [
    "[[PERSON_1]]",
    "[[ PERSON_1 ]]",
    "[[person_1]]",
    "[PERSON_1]",
    "[ PERSON_1 ]",
    "[[PERSON_1]",
]

TOOLS: list[dict[str, Any]] = [
    {
        "name": "initiate_transfer",
        "description": "Initiate a bank transfer.",
        "input_schema": {
            "type": "object",
            "properties": {"name": {"type": "string"}},
            "required": ["name"],
        },
    }
]


def _drain(parts: list[str], forward: dict[str, str] | None = None) -> tuple[str, int]:
    reinjector = StreamingReinjector(forward or {})
    emitted = "".join(reinjector.feed_text("content", part) for part in parts)
    return emitted + reinjector.flush_text("content"), reinjector.unresolved


@pytest.mark.parametrize("form", TOLERANT_FORMS)
def test_every_placeholder_split_boundary(form: str) -> None:
    """For every tolerant form, splitting at every character still resolves."""
    sentence = f"Transfer to {form} now."
    expected = "Transfer to Chinedu Okafor now."
    for boundary in range(len(form) + 1):
        start = sentence.index(form)
        parts = [
            sentence[: start + boundary],
            sentence[start + boundary :],
        ]
        emitted, unresolved = _drain(parts, FORWARD)
        assert emitted == expected, (form, boundary)
        assert unresolved == 0
        assert "[[" not in emitted and "[PERSON" not in emitted


@pytest.mark.parametrize("form", TOLERANT_FORMS)
def test_every_sentence_split_boundary(form: str) -> None:
    """Split the whole sentence (prefix, placeholder and suffix) everywhere."""
    sentence = f"Before {form} after."
    expected = "Before Chinedu Okafor after."
    for boundary in range(len(sentence) + 1):
        emitted, unresolved = _drain(
            [sentence[:boundary], sentence[boundary:]], FORWARD
        )
        assert emitted == expected, (form, boundary)
        assert unresolved == 0


def test_one_character_at_a_time() -> None:
    sentence = "Pay [[ PERSON_1 ]] and [PERSON_2] today."
    emitted, unresolved = _drain(list(sentence), {"[[PERSON_1]]": "Chinedu Okafor", "[[PERSON_2]]": "Ada Obi"})
    assert emitted == "Pay Chinedu Okafor and Ada Obi today."
    assert unresolved == 0


def test_unknown_placeholder_stays_and_counts() -> None:
    emitted, unresolved = _drain(["Missing [", "[PERSON_9]] now"], FORWARD)
    assert emitted == "Missing [[PERSON_9]] now"
    assert unresolved == 1


def test_earlier_single_bracket_does_not_steal_placeholder_close() -> None:
    """Regression: `[see` must not pair with the first `]` of `[[PERSON_1]]`."""
    sentence = "Note [see [[PERSON_1]]"
    for boundary in range(len(sentence) + 1):
        emitted, unresolved = _drain(
            [sentence[:boundary], sentence[boundary:]], FORWARD
        )
        assert emitted == "Note [see Chinedu Okafor", boundary
        assert unresolved == 0


def test_complete_placeholder_at_chunk_end_is_released_by_next_text() -> None:
    reinjector = StreamingReinjector(FORWARD)
    assert reinjector.feed_text(0, "Pay [[PERSON_1]]") == "Pay "
    assert reinjector.feed_text(0, " now") == "Chinedu Okafor now"


def test_complete_placeholder_with_following_text_flushes_immediately() -> None:
    reinjector = StreamingReinjector(FORWARD)
    assert reinjector.feed_text(0, "Pay [[PERSON_1]] now") == "Pay Chinedu Okafor now"
    assert reinjector.flush_text(0) == ""


def test_holdback_flushes_after_cap_without_dropping_bytes() -> None:
    reinjector = StreamingReinjector({})
    held = "[" + "x" * (HOLDBACK_CHARS - 1)
    assert reinjector.feed_text(0, held) == ""
    released = reinjector.feed_text(0, "y")
    assert released == held + "y"
    assert reinjector.flush_text(0) == ""


def test_holdback_never_drops_unclosed_bytes() -> None:
    reinjector = StreamingReinjector({})
    text = "[" + "z" * 100
    emitted = reinjector.feed_text(0, text) + reinjector.flush_text(0)
    assert emitted == text


def _openai_chunk(
    choices: list[dict[str, Any]], template: dict[str, Any] | None = None
) -> dict[str, Any]:
    return {
        **(template or {"id": "chunk_1", "created": 0, "model": "gpt-test"}),
        "object": "chat.completion.chunk",
        "choices": choices,
    }


def test_openai_rewriter_handles_n_greater_than_one() -> None:
    rewriter = OpenAIStreamRewriter(FORWARD)
    first = rewriter.rewrite(
        _openai_chunk(
            [
                {"index": 0, "delta": {"content": "A [[PERSON_1"}, "finish_reason": None},
                {"index": 1, "delta": {"content": "B [[PERSON_2"}, "finish_reason": None},
            ]
        )
    )
    second = rewriter.rewrite(
        _openai_chunk(
            [
                {"index": 0, "delta": {"content": "]]"}, "finish_reason": None},
                {"index": 1, "delta": {"content": "]]"}, "finish_reason": None},
            ]
        )
    )
    finished = rewriter.rewrite(
        _openai_chunk(
            [
                {"index": 0, "delta": {}, "finish_reason": "stop"},
                {"index": 1, "delta": {}, "finish_reason": "stop"},
            ]
        )
    )
    text: dict[int, str] = {}
    for chunk in first + second + finished:
        for choice in chunk["choices"]:
            text[choice["index"]] = text.get(choice["index"], "") + choice["delta"].get(
                "content", ""
            )
    assert text == {0: "A Chinedu Okafor", 1: "B Ada Obi"}
    assert rewriter.unresolved == 0
    assert [
        chunk["choices"][0]["finish_reason"]
        for chunk in finished
        if chunk["choices"][0]["finish_reason"]
    ] == ["stop", "stop"]


@asynccontextmanager
async def aegis_client(monkeypatch: pytest.MonkeyPatch) -> AsyncIterator[httpx.AsyncClient]:
    upstream = Upstream(
        base_url="http://mock-upstream.test/v1",
        client=httpx.AsyncClient(
            transport=httpx.ASGITransport(app=mock_app), timeout=60.0, trust_env=False
        ),
    )
    monkeypatch.setattr(aegis_main, "build_upstream", lambda: upstream)
    monkeypatch.setattr(settings, "ner_enabled", False)
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


def _openai_events(response: httpx.Response) -> list[dict[str, Any]]:
    events = [event for event in response.text.split("\n\n") if event.strip()]
    assert events[-1] == "data: [DONE]"
    return [json.loads(event.removeprefix("data: ")) for event in events[:-1]]


def _message_text(chunks: list[dict[str, Any]]) -> str:
    return "".join(
        choice["delta"].get("content", "")
        for chunk in chunks
        for choice in chunk["choices"]
    )


async def test_openai_stream_reinjects_split_placeholder(
    client: httpx.AsyncClient, redis_client: Redis
) -> None:
    sid = "stream-openai-" + uuid.uuid4().hex[:8]
    response = await client.post(
        "/v1/chat/completions",
        json={
            "model": "gpt-5-mini",
            "stream": True,
            "messages": [{"role": "user", "content": "Transfer to Chinedu Okafor"}],
        },
        headers={"X-Aegis-Session": sid},
    )
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/event-stream")
    assert response.headers["X-Aegis-Request-Id"].startswith("req_")
    assert "X-Aegis-Unresolved" not in response.headers

    chunks = _openai_events(response)
    assert _message_text(chunks) == "Transfer initiated to Chinedu Okafor"
    assert "[[PERSON_1]]" not in response.text
    finishes = [
        chunk["choices"][0]["finish_reason"]
        for chunk in chunks
        if chunk["choices"][0]["finish_reason"]
    ]
    assert finishes == ["stop"]

    tap = await client.get(
        f"/v1/aegis/wiretap/{response.headers['X-Aegis-Request-Id']}"
    )
    outbound = tap.json()
    assert outbound["stream"] is True
    assert "Chinedu Okafor" not in json.dumps(outbound)
    assert "[[PERSON_1]]" in outbound["messages"][0]["content"]

    entries = await redis_client.xrevrange("aegis:events", count=1)
    fields = dict(entries[0][1])
    assert fields["status"] == "ok"
    assert fields["stream_requested"] == "true"
    assert fields["unresolved"] == "0"


async def test_openai_stream_reinjects_split_tool_arguments(
    client: httpx.AsyncClient,
) -> None:
    response = await client.post(
        "/v1/chat/completions",
        json={
            "model": "gpt-5-mini",
            "stream": True,
            "messages": [{"role": "user", "content": "Pay Chinedu Okafor"}],
            "tools": [
                {
                    "type": "function",
                    "function": {
                        "name": "initiate_transfer",
                        "parameters": {
                            "type": "object",
                            "properties": {"name": {"type": "string"}},
                        },
                    },
                }
            ],
        },
        headers={"X-Aegis-Session": "stream-tools-" + uuid.uuid4().hex[:8]},
    )
    assert response.status_code == 200
    chunks = _openai_events(response)
    names = [
        call["function"].get("name")
        for chunk in chunks
        for choice in chunk["choices"]
        for call in choice["delta"].get("tool_calls", [])
    ]
    arguments = "".join(
        call["function"].get("arguments", "")
        for chunk in chunks
        for choice in chunk["choices"]
        for call in choice["delta"].get("tool_calls", [])
    )
    assert "initiate_transfer" in names
    assert json.loads(arguments) == {"name": "Chinedu Okafor"}
    assert "[[PERSON_1]]" not in arguments
    assert [
        chunk["choices"][0]["finish_reason"]
        for chunk in chunks
        if chunk["choices"][0]["finish_reason"]
    ] == ["tool_calls"]


def _sdk(extra_headers: dict[str, str] | None = None) -> anthropic.AsyncAnthropic:
    return anthropic.AsyncAnthropic(
        api_key="sk-ant-test",
        base_url="http://aegis.test",
        http_client=httpx2.AsyncClient(
            transport=httpx2.ASGITransport(app=aegis_app), trust_env=False
        ),
        default_headers=extra_headers,
        max_retries=0,
    )


async def test_anthropic_sdk_stream_reinjects_split_text(
    client: httpx.AsyncClient, redis_client: Redis
) -> None:
    sid = "stream-anthropic-" + uuid.uuid4().hex[:8]
    sdk = _sdk()
    try:
        async with sdk.messages.stream(
            model="claude-sonnet-4-6",
            max_tokens=64,
            messages=[{"role": "user", "content": "Transfer to Chinedu Okafor"}],
            extra_headers={"X-Aegis-Session": sid},
        ) as stream:
            message = await stream.get_final_message()
    finally:
        await sdk.close()

    assert message.content[0].text == "Transfer initiated to Chinedu Okafor"
    assert message.stop_reason == "end_turn"

    entries = await redis_client.xrevrange("aegis:events", count=1)
    fields = dict(entries[0][1])
    assert fields["status"] == "ok"
    assert fields["stream_requested"] == "true"
    assert fields["unresolved"] == "0"


async def test_anthropic_sdk_stream_reinjects_split_tool_input(
    client: httpx.AsyncClient,
) -> None:
    sdk = _sdk()
    try:
        async with sdk.messages.stream(
            model="claude-sonnet-4-6",
            max_tokens=64,
            messages=[{"role": "user", "content": "Pay Chinedu Okafor"}],
            tools=TOOLS,
            extra_headers={"X-Aegis-Session": "stream-anthropic-tools-" + uuid.uuid4().hex[:8]},
        ) as stream:
            message = await stream.get_final_message()
    finally:
        await sdk.close()

    assert message.stop_reason == "tool_use"
    tool_use = message.content[0]
    assert tool_use.type == "tool_use"
    assert tool_use.name == "initiate_transfer"
    assert tool_use.input == {"name": "Chinedu Okafor"}
