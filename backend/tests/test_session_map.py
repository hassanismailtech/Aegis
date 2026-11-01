"""Session Map tests (PRD 5.3, 7.2): stable numbering, counters, sliding TTL, expiry."""

import asyncio
import json
import uuid
from pathlib import Path

import pytest
from redis.asyncio import Redis

from app.schemas import EntityType
from app.scrubber import scrub_messages
from app.session_map import SessionMap

_FIXTURES = Path(__file__).with_name("fixtures") / "session_stability.json"


@pytest.fixture
async def redis_client() -> Redis:
    client = Redis.from_url("redis://localhost:6379/0", decode_responses=True)
    yield client
    await client.aclose()


def _sid() -> str:
    return "test-" + uuid.uuid4().hex[:12]


async def test_same_value_same_placeholder(redis_client: Redis) -> None:
    sm = SessionMap(redis_client, _sid())
    first = await sm.get_or_create_placeholder(EntityType.PERSON, "Chinedu Okafor")
    second = await sm.get_or_create_placeholder(EntityType.PERSON, "Chinedu Okafor")
    assert first == second == "[[PERSON_1]]"
    assert await sm.resolve(first) == "Chinedu Okafor"


async def test_different_values_increment_per_type(redis_client: Redis) -> None:
    sm = SessionMap(redis_client, _sid())
    assert await sm.get_or_create_placeholder(EntityType.PERSON, "Ada Obi") == "[[PERSON_1]]"
    assert await sm.get_or_create_placeholder(EntityType.PERSON, "Bola Ade") == "[[PERSON_2]]"
    assert await sm.get_or_create_placeholder(EntityType.PHONE, "08031234567") == "[[PHONE_1]]"
    assert await sm.get_or_create_placeholder(EntityType.BVN, "22334455667") == "[[BVN_1]]"


async def test_planted_session_stability_fixtures_do_not_merge_or_persist(
    redis_client: Redis,
) -> None:
    """A Session keeps its customer map; a new Session starts a new map."""
    fixture = json.loads(_FIXTURES.read_text(encoding="utf-8"))

    within = fixture["within_session"]
    session = SessionMap(redis_client, _sid())
    scrubbed, _, _ = await scrub_messages(within["messages"], session, None)
    assert scrubbed == within["expected"]
    assert await session.forward_map() == {
        "[[PERSON_1]]": "Chinedu Okafor",
        "[[PERSON_2]]": "Ada Obi",
    }

    first, second = fixture["across_sessions"]
    first_session = SessionMap(redis_client, _sid())
    second_session = SessionMap(redis_client, _sid())
    first_scrubbed, _, _ = await scrub_messages(first["messages"], first_session, None)
    second_scrubbed, _, _ = await scrub_messages(second["messages"], second_session, None)
    assert first_scrubbed == first["expected"]
    assert second_scrubbed == second["expected"]
    assert await first_session.forward_map() == {
        "[[PERSON_1]]": "Chinedu Okafor",
        "[[PERSON_2]]": "Ada Obi",
    }
    assert await second_session.forward_map() == {"[[PERSON_1]]": "Ada Obi"}
    assert await second_session.resolve("[[PERSON_2]]") is None


async def test_concurrent_claims_share_placeholder(redis_client: Redis) -> None:
    sm = SessionMap(redis_client, _sid())
    claims = await asyncio.gather(
        *[sm.get_or_create_placeholder(EntityType.PERSON, "Ngozi Eze") for _ in range(10)]
    )
    assert claims == ["[[PERSON_1]]"] * 10


async def test_ttl_is_refreshed_on_every_call(redis_client: Redis) -> None:
    sm = SessionMap(redis_client, _sid(), ttl=2)
    await sm.get_or_create_placeholder(EntityType.PERSON, "Ada Obi")
    await asyncio.sleep(1.0)
    await sm.get_or_create_placeholder(EntityType.PERSON, "Ada Obi")  # refresh #1
    await asyncio.sleep(1.5)
    assert await sm.resolve("[[PERSON_1]]") == "Ada Obi"  # refresh #2
    await asyncio.sleep(1.5)
    assert await redis_client.hget(sm.fwd_key, "[[PERSON_1]]") == "Ada Obi"


async def test_keys_expire(redis_client: Redis) -> None:
    sm = SessionMap(redis_client, _sid(), ttl=1)
    ph = await sm.get_or_create_placeholder(EntityType.EMAIL, "ada@obi.ng")
    for key in (sm.fwd_key, sm.rev_key, sm.ctr_key):
        assert 0 < await redis_client.ttl(key) <= 1
    await asyncio.sleep(1.3)
    assert await sm.resolve(ph) is None
    assert await redis_client.hgetall(sm.rev_key) == {}
