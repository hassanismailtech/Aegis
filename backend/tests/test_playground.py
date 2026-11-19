"""Playground boundaries locally; real Lua/concurrency/cleanup checks in CI."""

import asyncio
import hashlib
import json
import logging
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock
from uuid import uuid4

import httpx
import pytest
from asgi_lifespan import LifespanManager
from redis.asyncio import Redis
from redis.exceptions import RedisError

from app import main, playground, telemetry
from app.config import Settings
from app.errors import ScrubError
from app.schemas import EntityType
from app.session_map import SessionMap

_EXAMPLE = json.loads((Path(__file__).parents[2] / "demo/prompts.json").read_text())[0]
_TEXT = _EXAMPLE["text"]
_VALUES = _EXAMPLE["planted"]
_MAP = dict(zip(["[[PERSON_1]]", "[[PHONE_1]]", "[[BVN_1]]"], _VALUES))
_SCRUBBED = _TEXT
for _ph, _value in _MAP.items():
    _SCRUBBED = _SCRUBBED.replace(_value, _ph)
_CLOCK = 20 * 86400 + 310


def test_playground_is_disabled_and_bounded_by_default(monkeypatch):
    for name in ("PLAYGROUND_ENABLED", "PLAYGROUND_MAX_CHARS", "PLAYGROUND_RATE_PER_MINUTE", "PLAYGROUND_TRUST_PROXY"):
        monkeypatch.delenv(name, raising=False)
    defaults = Settings(_env_file=None)
    assert defaults.playground_enabled is False
    assert defaults.playground_max_chars == 2000
    assert defaults.playground_rate_per_minute == 20
    assert defaults.playground_trust_proxy is False


@pytest.fixture(autouse=True)
def settings_and_no_events(monkeypatch: pytest.MonkeyPatch, tmp_path: Path):
    for name, value in {
        "playground_enabled": True, "playground_max_chars": 2000,
        "playground_rate_per_minute": 20, "playground_trust_proxy": False,
        "ner_enabled": False, "bind_host": "127.0.0.1",
        "aegis_keys_file": "", "aegis_demo_token": "",
        "aegis_ticket_secret": "", "aegis_insecure_dev": False,
        "audit_db_path": str(tmp_path / "audit.db"),
    }.items():
        monkeypatch.setattr(main.settings, name, value)
    spies = [AsyncMock() for _ in range(3)]
    monkeypatch.setattr(main, "_emit", spies[0])
    monkeypatch.setattr(main, "record_event", spies[1])
    monkeypatch.setattr(telemetry, "record", spies[2])
    yield
    for spy in spies:
        spy.assert_not_awaited()


@pytest.fixture
async def service(monkeypatch: pytest.MonkeyPatch):
    redis = SimpleNamespace(set=AsyncMock(), get=AsyncMock(return_value="unit-salt"), eval=AsyncMock(return_value=1))
    session = SimpleNamespace(forward_map=AsyncMock(return_value=_MAP), destroy=AsyncMock())
    factory = Mock(return_value=session)
    counts = {kind: int(kind in (EntityType.PERSON, EntityType.PHONE, EntityType.BVN)) for kind in EntityType}
    scrubber = AsyncMock(return_value=([{"role": "user", "content": _SCRUBBED}], counts, 1.25))
    upstream, audit = Mock(), SimpleNamespace(append=AsyncMock())
    for name, value in {"redis": redis, "ner": None, "tenants": None, "upstream": upstream, "audit": audit}.items():
        monkeypatch.setattr(main.app.state, name, value, raising=False)
    monkeypatch.setattr(playground, "SessionMap", factory)
    monkeypatch.setattr(playground, "scrub_messages", scrubber)
    monkeypatch.setattr(playground, "time", lambda: _CLOCK)
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=main.app, client=("192.0.2.1", 123)),
        base_url="http://aegis.test", trust_env=False,
    ) as client:
        yield SimpleNamespace(client=client, redis=redis, session=session, factory=factory, scrubber=scrubber)
    assert not upstream.mock_calls
    audit.append.assert_not_awaited()


async def test_disabled_is_404_before_validation(service, monkeypatch):
    monkeypatch.setattr(main.settings, "playground_enabled", False)
    for content in [{"text": _TEXT}, {"text": {}}, {}]:
        response = await service.client.post(playground.PLAYGROUND_PATH, json=content)
        assert response.status_code == 404
        assert response.headers["cache-control"] == "no-store"
    service.redis.set.assert_not_awaited()
    service.factory.assert_not_called()


async def test_scrubbed_only_contract_and_cleanup(service):
    response = await service.client.post(playground.PLAYGROUND_PATH, json={"text": _TEXT})
    assert response.status_code == 200
    assert response.headers["cache-control"] == "no-store"
    body = response.json()
    assert set(body) == {"scrubbed", "entities", "counts", "simulated_reply", "overhead_ms", "mode"}
    assert body["scrubbed"] == _SCRUBBED
    assert {item["placeholder"] for item in body["entities"]} == set(_MAP)
    assert body["counts"]["PERSON"] == 1
    assert body["mode"] == "lite"
    assert body["overhead_ms"] == 1.25
    for value in _VALUES:
        assert value not in response.text
    for ph in _MAP:
        assert ph in body["simulated_reply"]
    service.session.destroy.assert_awaited_once()
    sid = service.factory.call_args.args[1]
    assert sid.startswith("pg-") and len(sid) == 35
    assert service.factory.call_args.kwargs == {"ttl": 60}


@pytest.mark.parametrize("payload", [{}, {"text": ""}, {"text": 123}, {"text": None}, {"text": {"secret": _TEXT}}, {"text": _TEXT + " " * 2000}])
async def test_invalid_input_is_safe_422(service, payload):
    response = await service.client.post(playground.PLAYGROUND_PATH, json=payload)
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "aegis_invalid_request"
    for value in _VALUES:
        assert value not in response.text
    service.redis.set.assert_not_awaited()


async def test_malformed_json_is_safe(service):
    response = await service.client.post(playground.PLAYGROUND_PATH, content='{"text": "' + _TEXT, headers={"content-type": "application/json"})
    assert response.status_code == 422
    for value in _VALUES:
        assert value not in response.text


@pytest.mark.parametrize("path", ["/v1/chat/completions", "/v1/messages"])
async def test_existing_validation_keeps_400_without_input(service, path):
    response = await service.client.post(path, json={"text": _TEXT})
    assert response.status_code == 400
    assert response.json()["error"]["type"] == "invalid_request_error"
    for value in _VALUES:
        assert value not in response.text


async def test_configured_length_limit(service, monkeypatch):
    monkeypatch.setattr(main.settings, "playground_max_chars", len(_TEXT) - 1)
    assert (await service.client.post(playground.PLAYGROUND_PATH, json={"text": _TEXT})).status_code == 422


async def test_exact_length_boundary(service):
    response = await service.client.post(playground.PLAYGROUND_PATH, json={"text": _TEXT.ljust(2000)})
    assert response.status_code == 200


async def test_input_placeholders_do_not_become_detected_entities(service):
    service.scrubber.return_value[0][0]["content"] = _SCRUBBED + " [[PERSON_999]]"
    body = (await service.client.post(playground.PLAYGROUND_PATH, json={"text": _TEXT + " [[PERSON_999]]"})).json()
    assert "[[PERSON_999]]" not in {item["placeholder"] for item in body["entities"]}
    assert "[[PERSON_999]]" not in body["simulated_reply"]


async def test_limited_request_does_not_scrub(service):
    service.redis.eval.return_value = 21
    response = await service.client.post(playground.PLAYGROUND_PATH, json={"text": _TEXT})
    assert response.status_code == 429
    assert response.headers["retry-after"] == "50"
    assert response.headers["cache-control"] == "no-store"
    service.scrubber.assert_not_awaited()
    service.factory.assert_not_called()


@pytest.mark.parametrize(("enabled", "header", "expected"), [
    (False, "198.51.100.2", "192.0.2.1"),
    (True, "198.51.100.2, 192.0.2.5", "198.51.100.2"),
    (True, "invalid", "192.0.2.1"),
])
async def test_forwarded_ip_requires_explicit_trust(service, monkeypatch, enabled, header, expected):
    monkeypatch.setattr(main.settings, "playground_trust_proxy", enabled)
    limiter = AsyncMock(return_value=0)
    monkeypatch.setattr(playground, "_rate_limit", limiter)
    assert (await service.client.post(playground.PLAYGROUND_PATH, json={"text": _TEXT}, headers={"x-forwarded-for": header})).status_code == 200
    assert limiter.await_args.args[1] == expected


async def test_rate_keys_are_secret_keyed_and_salt_is_shared(service):
    await playground._rate_limit(service.redis, "192.0.2.1")
    first = service.redis.eval.await_args.args[2]
    assert "192.0.2.1" not in first
    assert hashlib.sha256(b"192.0.2.1").hexdigest()[:32] not in first
    assert service.redis.set.await_args.kwargs["nx"] is True
    assert service.redis.set.await_args.kwargs["ex"] > 0
    service.redis.get.return_value = "another-unit-salt"
    await playground._rate_limit(service.redis, "192.0.2.1")
    assert service.redis.eval.await_args.args[2] != first


@pytest.mark.parametrize(("enabled", "ready", "mode"), [(False, False, "lite"), (True, False, "lite"), (True, True, "full")])
async def test_mode_reports_actual_model_availability(service, monkeypatch, enabled, ready, mode):
    monkeypatch.setattr(main.settings, "ner_enabled", enabled)
    monkeypatch.setattr(main.app.state, "ner", SimpleNamespace(ready=True) if ready else None)
    assert (await service.client.post(playground.PLAYGROUND_PATH, json={"text": _TEXT})).json()["mode"] == mode


@pytest.mark.parametrize("failure", ["rate", "scrub", "map", "cleanup"])
async def test_failures_are_private_and_cleanup_is_attempted(service, caplog, failure):
    target = {"rate": service.redis.get, "scrub": service.scrubber, "map": service.session.forward_map, "cleanup": service.session.destroy}[failure]
    target.side_effect = ScrubError(_TEXT) if failure == "scrub" else RedisError(_TEXT)
    with caplog.at_level(logging.DEBUG):
        response = await service.client.post(playground.PLAYGROUND_PATH, json={"text": _TEXT}, headers={"Authorization": "Bearer private-test-key"})
    assert response.status_code == 503
    for value in [*_VALUES, "private-test-key"]:
        assert value not in response.text
        assert value not in caplog.text
    if failure != "rate":
        service.session.destroy.assert_awaited_once()


async def test_no_detected_entities(service):
    service.session.forward_map.return_value = {}
    body = (await service.client.post(playground.PLAYGROUND_PATH, json={"text": _TEXT})).json()
    assert body["entities"] == []
    assert body["simulated_reply"] == "No sensitive identifiers detected."


async def test_lost_salt_fails_closed(service):
    service.redis.get.return_value = None
    response = await service.client.post(playground.PLAYGROUND_PATH, json={"text": _TEXT})
    assert response.status_code == 503
    service.factory.assert_not_called()


async def test_cleanup_has_a_deadline(service):
    release = asyncio.Event()
    async def stalled():
        await release.wait()
    service.session.destroy.side_effect = stalled
    task = asyncio.create_task(service.client.post(playground.PLAYGROUND_PATH, json={"text": _TEXT}))
    try:
        done, _ = await asyncio.wait({task}, timeout=4)
        assert task in done
        response = task.result()
        assert response.status_code == 503
        assert response.json()["error"]["code"] == "aegis_state_unavailable"
    finally:
        release.set()
        await task


async def test_cancellation_cleans_session(service):
    started = asyncio.Event()
    async def blocked(*args):
        started.set()
        await asyncio.Event().wait()
    service.scrubber.side_effect = blocked
    task = asyncio.create_task(service.client.post(playground.PLAYGROUND_PATH, json={"text": _TEXT}))
    await asyncio.wait_for(started.wait(), timeout=2)
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task
    service.session.destroy.assert_awaited_once()


async def test_cancellation_waits_for_cleanup(service):
    started, release, finished = asyncio.Event(), asyncio.Event(), asyncio.Event()
    async def delayed():
        started.set()
        await release.wait()
        finished.set()
    service.session.destroy.side_effect = delayed
    task = asyncio.create_task(playground._destroy(service.session))
    await started.wait()
    task.cancel()
    await asyncio.sleep(0)
    assert not task.done()
    release.set()
    with pytest.raises(asyncio.CancelledError):
        await task
    assert finished.is_set()


async def test_destroy_only_deletes_its_exact_keys():
    redis = Mock(spec=Redis)
    redis.delete = AsyncMock()
    session = SessionMap(redis, "pg-owned", ttl=60)
    await session.destroy()
    redis.delete.assert_awaited_once_with("aegis:sess:pg-owned:fwd", "aegis:sess:pg-owned:rev", "aegis:sess:pg-owned:ctr")


@pytest.fixture
async def real_service(monkeypatch):
    clock = [_CLOCK]
    monkeypatch.setattr(playground, "time", lambda: clock[0])
    suffix = uuid4().hex[:24]
    ip = "2001:db8:" + ":".join(suffix[i:i + 4] for i in range(0, 24, 4))
    async with LifespanManager(main.app):
        redis = main.app.state.redis
        assert await redis.ping()
        audit = AsyncMock()
        monkeypatch.setattr(main.app.state.audit, "append", audit)
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=main.app, client=(ip, 123)), base_url="http://aegis.test", trust_env=False) as client:
            yield client, redis, clock
        audit.assert_not_awaited()


async def test_real_redis_scrubs_cleans_and_emits_no_events(real_service, caplog):
    client, redis, _ = real_service
    before = (await redis.xlen("aegis:events"), await redis.hgetall("aegis:stats"), await redis.llen("aegis:overhead"))
    with caplog.at_level(logging.DEBUG):
        response = await client.post(playground.PLAYGROUND_PATH, json={"text": _TEXT})
    assert response.status_code == 200
    for value in _VALUES:
        assert value not in response.text and value not in caplog.text
    assert response.json()["counts"]["BVN"] == 1
    assert "[[PERSON_1]]" in response.json()["scrubbed"]
    assert await redis.keys("aegis:sess:pg-*") == []
    assert before == (await redis.xlen("aegis:events"), await redis.hgetall("aegis:stats"), await redis.llen("aegis:overhead"))


async def test_real_redis_concurrent_rate_limit(real_service):
    client, redis, _ = real_service
    responses = await asyncio.gather(*[client.post(playground.PLAYGROUND_PATH, json={"text": _TEXT}) for _ in range(30)])
    statuses = [response.status_code for response in responses]
    assert statuses.count(200) == 20
    assert statuses.count(429) == 10
    assert await redis.keys("aegis:sess:pg-*") == []
    for key in await redis.keys("aegis:pg:rl:*"):
        assert 0 < await redis.ttl(key) <= 70


async def test_real_redis_rate_limit_rollover(real_service):
    client, _, clock = real_service
    for _ in range(20):
        assert (await client.post(playground.PLAYGROUND_PATH, json={"text": _TEXT})).status_code == 200
    response = await client.post(playground.PLAYGROUND_PATH, json={"text": _TEXT})
    assert response.status_code == 429 and response.headers["retry-after"] == "50"
    clock[0] += 60
    assert (await client.post(playground.PLAYGROUND_PATH, json={"text": _TEXT})).status_code == 200


async def test_real_redis_daily_salt_rollover(real_service):
    client, redis, clock = real_service
    assert (await client.post(playground.PLAYGROUND_PATH, json={"text": _TEXT})).status_code == 200
    previous = await redis.get(f"aegis:pg:salt:{clock[0] // 86400}")
    clock[0] += 86400
    assert (await client.post(playground.PLAYGROUND_PATH, json={"text": _TEXT})).status_code == 200
    assert previous != await redis.get(f"aegis:pg:salt:{clock[0] // 86400}")


@pytest.mark.parametrize("failure", ["error", "cancel"])
async def test_real_redis_partial_session_cleanup(real_service, monkeypatch, failure):
    client, redis, _ = real_service
    started = asyncio.Event()
    async def interrupted(messages, session, ner):
        await session.get_or_create_placeholder(EntityType.PERSON, _VALUES[0])
        started.set()
        if failure == "error":
            raise ScrubError(_TEXT)
        await asyncio.Event().wait()
    monkeypatch.setattr(playground, "scrub_messages", interrupted)
    task = asyncio.create_task(client.post(playground.PLAYGROUND_PATH, json={"text": _TEXT}))
    await asyncio.wait_for(started.wait(), timeout=3)
    if failure == "cancel":
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task
    else:
        assert (await task).status_code == 503
    assert await redis.keys("aegis:sess:pg-*") == []
