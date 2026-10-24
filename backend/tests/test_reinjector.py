"""Reinjector tests (PRD 5.4, 7.1): every tolerant row, must-not cases,
JSON-escaping inside tool-call arguments, unresolved counting, and the
Session Map forward table it resolves against.
"""

import json
import uuid
from collections.abc import AsyncIterator

import pytest
from redis.asyncio import Redis

from app.reinjector import Reinjector
from app.schemas import EntityType
from app.session_map import SessionMap

VALUE = "Ngozi Obi"  # [[PERSON_1]]'s value for every 7.1 row
FWD = {"[[PERSON_1]]": VALUE}


@pytest.fixture
async def redis_client() -> AsyncIterator[Redis]:
    client = Redis.from_url("redis://localhost:6379/0", decode_responses=True)
    yield client
    await client.aclose()

RESOLVE_ROWS: list[tuple[str, str]] = [
    ("[[PERSON_1]]", VALUE),
    ("[[ PERSON_1 ]]", VALUE),
    ("[[person_1]]", VALUE),
    ("[PERSON_1]", VALUE),
    ("[ PERSON_1 ]", VALUE),
    ("[[PERSON_1]]'s", f"{VALUE}'s"),
    ("**[[PERSON_1]]**", f"**{VALUE}**"),
]

MUST_NOT_ROWS: list[tuple[str, int]] = [
    ("[[PERSON_9]]", 1),  # absent from the map: stays as-is, counts unresolved
    ("[[ PERSON_9 ]]", 1),
    ("Phone [[PHONE_1]] unknown here", 1),  # type absent from the map
    ("Please answer [1] to the list", 0),  # not a Placeholder, never touched
    ("plain text without brackets", 0),
]


def reinjector_for(forward: dict[str, str]) -> Reinjector:
    return Reinjector(forward)


@pytest.mark.parametrize(("text", "expected"), RESOLVE_ROWS)
def test_tolerant_rows_resolve(text: str, expected: str) -> None:
    injector = reinjector_for(FWD)
    assert injector.content(text) == expected
    assert injector.unresolved == 0


@pytest.mark.parametrize(("text", "unresolved"), MUST_NOT_ROWS)
def test_must_not_rows_stay_unresolved(text: str, unresolved: int) -> None:
    injector = reinjector_for(FWD)
    assert injector.content(text) == text
    assert injector.unresolved == unresolved


def test_uppercase_normalizes_for_map_lookup() -> None:
    injector = reinjector_for(FWD)
    assert injector.content("[[ person_1 ]]") == VALUE


async def test_session_map_forward_table(redis_client: Redis) -> None:
    sm = SessionMap(redis_client, "test-reinjector-" + uuid.uuid4().hex[:10])
    person = await sm.get_or_create_placeholder(EntityType.PERSON, "Ada Obi")
    bvn = await sm.get_or_create_placeholder(EntityType.BVN, "22334455667")
    forward = await sm.forward_map()
    assert forward == {person: "Ada Obi", bvn: "22334455667"}
    injector = reinjector_for(forward)
    assert injector.content(f"{person} checked {bvn}") == "Ada Obi checked 22334455667"
    assert injector.unresolved == 0


def test_arguments_json_escaping() -> None:
    weird = 'Ada "Obi" \\ \nTab\tEnd'
    injector = reinjector_for({"[[PERSON_1]]": weird})
    arguments = injector.arguments(json.dumps({"note": "call [[PERSON_1]] today", "amount": 5}))
    assert json.loads(arguments) == {"note": f"call {weird} today", "amount": 5}
    assert injector.unresolved == 0


def test_arguments_multiple_placeholders_and_lowercase_type() -> None:
    injector = reinjector_for({"[[PERSON_1]]": "Ada Obi", "[[ACCOUNT_NO_1]]": "0123456789"})
    arguments = injector.arguments('{"to": "[[PERSON_1]]", "from": "[[account_no_1]]"}')
    assert json.loads(arguments) == {"to": "Ada Obi", "from": "0123456789"}


def test_arguments_unknown_count_without_breaking_json() -> None:
    injector = reinjector_for(FWD)
    arguments = injector.arguments('{"to": "[[PERSON_9]]", "note": "[[PERSON_1]]"}')
    assert json.loads(arguments) == {"to": "[[PERSON_9]]", "note": VALUE}
    assert injector.unresolved == 1


def _completion() -> dict[str, dict]:
    """Fresh completion with Placeholders in message content and tool arguments."""
    return {
        "choices": [
            {
                "message": {
                    "role": "assistant",
                    "content": "[[PERSON_1]], [ PERSON_1 ] and [[BVN_1]]",
                    "tool_calls": [
                        {
                            "id": "call_1",
                            "type": "function",
                            "function": {
                                "name": "initiate_transfer",
                                "arguments": '{"person": "[[PERSON_1]]", "bvn": "[[BVN_1]]"}',
                            },
                        }
                    ],
                }
            }
        ]
    }


def test_inject_swaps_content_and_tool_arguments() -> None:
    completion = _completion()
    injector = reinjector_for({"[[PERSON_1]]": VALUE, "[[BVN_1]]": "22334455667"})
    injector.inject(completion)
    assert completion["choices"][0]["message"]["content"] == (
        f"{VALUE}, {VALUE} and 22334455667"
    )
    arguments = json.loads(completion["choices"][0]["message"]["tool_calls"][0]["function"]["arguments"])
    assert arguments == {"person": VALUE, "bvn": "22334455667"}
    assert injector.unresolved == 0


def test_inject_counts_unresolved_across_both_places() -> None:
    completion = _completion()
    injector = reinjector_for(FWD)  # no [[BVN_1]] entry
    injector.inject(completion)
    assert injector.unresolved == 2  # once in content, once in arguments
    assert "[[BVN_1]]" in completion["choices"][0]["message"]["content"]


def test_inject_leaves_error_shape_and_non_string_content_untouched() -> None:
    injector = reinjector_for(FWD)
    error_body: dict[str, object] = {"error": {"message": "upstream exploded"}}
    injector.inject(error_body)  # type: ignore[arg-type]
    assert injector.unresolved == 0
    none_content = {"choices": [{"message": {"content": None, "tool_calls": None}}]}
    injector.inject(none_content)  # type: ignore[arg-type]
    assert none_content["choices"][0]["message"]["content"] is None
    assert injector.unresolved == 0


def test_empty_map_counts_every_placeholder() -> None:
    injector = reinjector_for({})
    text = "[[PERSON_1]] [[PHONE_2]] [[PERSON_1]]"
    assert injector.content(text) == text
    assert injector.unresolved == 3
