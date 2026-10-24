"""Telemetry tests (PRD 5.5, 7.2, 7.3): event record → stream + stats + pubsub,
fee math, percentiles, endpoints (stats, seed, SSE live feed)."""

import asyncio
import contextlib
import json
import re
import uuid
from collections.abc import AsyncIterator
from typing import Any

import httpx
import pytest
import uvicorn
from asgi_lifespan import LifespanManager
from redis.asyncio import Redis

from app import main as aegis_main
from app.main import app as aegis_app
from app.telemetry import (
    EVENTS_KEY,
    LEAKTEST_KEY,
    OVERHEAD_KEY,
    PUBSUB_CHANNEL,
    STATS_KEY,
    fields,
    fee_usd,
    make_event,
    percentile,
    record,
    seed_events,
)
from app.upstream import Upstream
from scripts.mock_upstream import app as mock_app

_PLANTED = ["Chinedu Okafor", "22334455667", "08031234567"]
_EVENT_KEYS = {
    "request_id", "ts", "session", "model", "stream_requested", "entities",
    "entities_total", "scrub_ms", "reinject_ms", "upstream_ms", "overhead_ms",
    "unresolved", "status", "fee_usd",
}


@pytest.fixture
async def redis_client() -> AsyncIterator[Redis]:
    client = Redis.from_url("redis://localhost:6379/0", decode_responses=True)
    yield client
    await client.aclose()


@pytest.fixture
async def client(monkeypatch: pytest.MonkeyPatch) -> AsyncIterator[httpx.AsyncClient]:
    aegis_upstream = Upstream(
        base_url="http://mock-upstream.test/v1",
        client=httpx.AsyncClient(
            transport=httpx.ASGITransport(app=mock_app), timeout=60.0, trust_env=False
        ),
    )
    monkeypatch.setattr(aegis_main, "build_upstream", lambda: aegis_upstream)
    async with LifespanManager(aegis_app, startup_timeout=300):
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=aegis_app),
            base_url="http://aegis.test",
            trust_env=False,
        ) as client:
            yield client


def _event(**overrides: Any) -> Any:
    base: dict[str, Any] = dict(
        request_id="req_" + uuid.uuid4().hex,
        session="sess-test",
        model="gpt-5-mini",
        stream_requested=False,
        entities={"PERSON": 2, "BVN": 1, "PHONE": 1},
        scrub_ms=31.24,
        reinject_ms=0.76,
        upstream_ms=912.4,
        unresolved=0,
        status="ok",
        usage={"prompt_tokens": 100, "completion_tokens": 200},
    )
    base.update(overrides)
    return make_event(**base)


def test_fee_usd_from_upstream_usage() -> None:
    assert fee_usd({"prompt_tokens": 100, "completion_tokens": 200}) == pytest.approx(
        (100 + 200) / 1000 * 0.001
    )
    assert fee_usd(None) == 0.0
    assert fee_usd({}) == 0.0
    assert fee_usd({"prompt_tokens": 5}) == pytest.approx(5 / 1000 * 0.001)


def test_make_event_overhead_entities_and_timestamp() -> None:
    event = _event()
    assert event.overhead_ms == 32.0  # PRD 7.3: scrub + reinject only
    assert event.scrub_ms == 31.2 and event.reinject_ms == 0.8
    assert event.entities_total == 4
    assert set(event.entities) == {"PERSON", "PHONE", "BVN", "NIN", "ACCOUNT_NO", "EMAIL"}
    assert re.fullmatch(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z", event.ts) is not None
    assert set(fields(event)) == _EVENT_KEYS


def test_percentile_nearest_rank() -> None:
    assert percentile([], 0.95) == 0.0
    values = [1.0, 2.0, 3.0]
    assert percentile(values, 0.50) == 2.0
    assert percentile(values, 0.95) == 3.0
    assert percentile([5.0], 0.50) == 5.0


async def test_record_writes_stream_stats_overhead_and_publish(
    redis_client: Redis,
) -> None:
    events_before = await redis_client.xlen(EVENTS_KEY)
    stats_before = await redis_client.hgetall(STATS_KEY)
    overhead_before = await redis_client.llen(OVERHEAD_KEY)
    pubsub = redis_client.pubsub()
    await pubsub.subscribe(PUBSUB_CHANNEL)

    event = _event()
    await record(redis_client, event)

    last = await redis_client.xrevrange(EVENTS_KEY, count=1)
    assert last and await redis_client.xlen(EVENTS_KEY) == events_before + 1
    stored = dict(last[0][1])
    assert stored["request_id"] == event.request_id
    assert stored["status"] == "ok"
    assert stored["unresolved"] == "0"
    assert json.loads(stored["entities"]) == {
        "PERSON": 2, "PHONE": 1, "BVN": 1, "NIN": 0, "ACCOUNT_NO": 0, "EMAIL": 0
    }
    assert await redis_client.llen(OVERHEAD_KEY) == overhead_before + 1
    stats_after = await redis_client.hgetall(STATS_KEY)
    assert int(stats_after["requests"]) == int(stats_before.get("requests", 0)) + 1
    assert int(stats_after["fee_micro_usd"]) >= int(stats_before.get("fee_micro_usd", 0)) + 300

    published: dict[str, Any] | None = None
    for _ in range(3):  # first read may swallow the dropped subscribe ack
        message = await pubsub.get_message(ignore_subscribe_messages=True, timeout=1.0)
        if message is not None:
            published = message
            break
    assert published is not None and published["channel"] == PUBSUB_CHANNEL
    assert json.loads(published["data"])["request_id"] == event.request_id
    await pubsub.aclose()


def test_seed_events_are_synthetic() -> None:
    events = seed_events()
    assert len(events) == 20
    assert len({event.request_id for event in events}) == 20
    assert all(event.status == "ok" for event in events)
    assert all(event.session.startswith("seed-") for event in events)


async def test_stats_endpoint_shape(client: httpx.AsyncClient, redis_client: Redis) -> None:
    stats = (await client.get("/v1/aegis/stats")).json()
    assert set(stats) == {
        "requests", "entities_total", "entities", "state_loss",
        "overhead_ms_p50", "overhead_ms_p95", "fee_usd", "leaks",
    }
    assert set(stats["entities"]) == {"PERSON", "PHONE", "BVN", "NIN", "ACCOUNT_NO", "EMAIL"}
    assert stats["overhead_ms_p50"] <= stats["overhead_ms_p95"]


async def test_stats_surfaces_last_leaktest_report(
    client: httpx.AsyncClient, redis_client: Redis, pytestconfig: pytest.Config
) -> None:
    """PRD 5.6: dashboard leaks come from the last `pytest --report` run."""
    previous = await redis_client.get(LEAKTEST_KEY)
    if pytestconfig.getoption("--report") and previous is not None:
        stats = (await client.get("/v1/aegis/stats")).json()
        assert stats["leaks"] == json.loads(previous)
        return
    report = {"leaks": 0, "planted": 31, "ts": "2026-10-24T09:00:00Z"}
    await redis_client.set(LEAKTEST_KEY, json.dumps(report))
    try:
        stats = (await client.get("/v1/aegis/stats")).json()
        assert stats["leaks"] == report
    finally:
        if pytestconfig.getoption("--report"):
            return
        if previous is None:
            await redis_client.delete(LEAKTEST_KEY)
        else:
            await redis_client.set(LEAKTEST_KEY, previous)


async def test_seed_endpoint_adds_20_events(
    client: httpx.AsyncClient, redis_client: Redis
) -> None:
    requests_before = int((await redis_client.hgetall(STATS_KEY)).get("requests", 0))
    events_before = await redis_client.xlen(EVENTS_KEY)
    overhead_before = await redis_client.llen(OVERHEAD_KEY)

    response = await client.post("/v1/aegis/_seed")
    assert response.status_code == 200
    body = response.json()
    assert body["seeded"] == 20 and len(body["events"]) == 20
    assert {event["request_id"] for event in body["events"]} == {
        f"req_seed{i:02d}" for i in range(20)
    }
    assert int((await redis_client.hgetall(STATS_KEY)).get("requests", 0)) == requests_before + 20
    assert await redis_client.xlen(EVENTS_KEY) == events_before + 20
    assert await redis_client.llen(OVERHEAD_KEY) == overhead_before + 20


async def test_live_request_reaches_stream_without_planted_text(
    client: httpx.AsyncClient, redis_client: Redis
) -> None:
    requests_before = int((await redis_client.hgetall(STATS_KEY)).get("requests", 0))
    response = await client.post(
        "/v1/chat/completions",
        json={
            "model": "gpt-5-mini",
            "messages": [{
                "role": "user",
                "content": "Transfer 50000 to Chinedu Okafor, BVN 22334455667, phone 08031234567",
            }],
        },
        headers={"X-Aegis-Session": "telemetry-live-" + uuid.uuid4().hex[:8]},
    )
    assert response.status_code == 200
    request_id = response.headers["X-Aegis-Request-Id"]

    stats_after = await redis_client.hgetall(STATS_KEY)
    assert int(stats_after["requests"]) == requests_before + 1
    assert "fee_micro_usd" in stats_after  # mock usage is metered (PRD 7.3 fee math)

    last = await redis_client.xrevrange(EVENTS_KEY, count=1)
    stored = dict(last[0][1])
    assert stored["request_id"] == request_id
    assert stored["status"] == "ok"
    blob = json.dumps(stored)
    for value in _PLANTED:  # PRD 5.5: post-scrub metadata only, never the pre-scrub text
        assert value not in blob


@pytest.fixture
async def live_aegis_server() -> AsyncIterator[httpx.AsyncClient]:
    """Real uvicorn server on an ephemeral port.

    httpx.ASGITransport buffers a response until the ASGI app call returns, so
    it cannot deliver an unbounded SSE body; the live feed needs a socket.
    """
    config = uvicorn.Config(aegis_app, host="127.0.0.1", port=0, log_level="warning")
    server = uvicorn.Server(config)
    task = asyncio.create_task(server.serve())
    while not server.started:
        await asyncio.sleep(0.05)
    port = server.servers[0].sockets[0].getsockname()[1]
    async with httpx.AsyncClient(base_url=f"http://127.0.0.1:{port}", trust_env=False) as client:
        yield client
    server.should_exit = True
    with contextlib.suppress(asyncio.TimeoutError, asyncio.CancelledError):
        await asyncio.wait_for(task, timeout=10)


async def test_sse_feed_publishes_telemetry_and_heartbeats(
    live_aegis_server: httpx.AsyncClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(aegis_main, "HEARTBEAT_SECONDS", 0.2)
    async with live_aegis_server.stream("GET", "/v1/aegis/events") as response:
        assert response.headers["content-type"].startswith("text/event-stream")
        buffer, posted, data = "", False, None
        async for chunk in response.aiter_text():
            buffer += chunk
            if ": heartbeat" in buffer and not posted:
                posted = True
                # No mock Upstream required: any completed request records an
                # event (502 upstream_error when nothing listens on :9000).
                posted_response = await live_aegis_server.post(
                    "/v1/chat/completions",
                    json={"model": "gpt-5-mini",
                          "messages": [{"role": "user", "content": "hello"}]},
                    headers={"X-Aegis-Session": "sse-" + uuid.uuid4().hex[:8]},
                )
                assert posted_response.status_code in {200, 502}, posted_response.status_code
            if "event: telemetry" in buffer and "data: " in buffer:
                tail = buffer[buffer.rindex("data: ") :]
                data = json.loads(tail.split("\n\n", 1)[0].removeprefix("data: "))
                break
    assert posted, "no heartbeat seen"
    assert data is not None, "no telemetry event streamed"
    assert data["status"] in {"ok", "state_loss", "upstream_error"}
    assert set(data) == _EVENT_KEYS
    blob = json.dumps(data)
    for value in _PLANTED:
        assert value not in blob  # PRD 5.5: no pre-scrub text in the live feed
