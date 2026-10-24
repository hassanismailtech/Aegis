"""Session Map tests (PRD 5.3, 7.2): stable numbering, counters, sliding TTL, expiry."""

import asyncio
import uuid

import pytest
from redis.asyncio import Redis

from app.schemas import EntityType
from app.session_map import SessionMap


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
