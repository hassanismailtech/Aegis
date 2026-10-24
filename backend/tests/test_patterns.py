"""Scrubber tests (PRD 6 every row, 5.2, Step 3): patterns, gazetteer, merging,
message shapes through scrub_messages(), Session-Map stability.

ENG NER is not exercised here (ner=None): GLiNER recall is measured by
scripts/eval_recall.py against the real model.
"""

import json

import pytest

from app.schemas import EntityType
from app.scrubber import merge_spans, scrub_messages
from app.scrubber.gazetteer import find_persons
from app.scrubber.patterns import Span, pattern_spans

PT = EntityType.PERSON
PH = EntityType.PHONE
BV = EntityType.BVN
NI = EntityType.NIN
AC = EntityType.ACCOUNT_NO
EM = EntityType.EMAIL


class FakeSessionMap:
    """Reverse-lookup map, no Redis: same original → same Placeholder."""

    def __init__(self) -> None:
        self._rev: dict[tuple[EntityType, str], str] = {}
        self._ctr: dict[EntityType, int] = {}

    async def get_or_create_placeholder(self, entity_type: EntityType, original: str) -> str:
        key = (entity_type, original)
        if key not in self._rev:
            self._ctr[entity_type] = self._ctr.get(entity_type, 0) + 1
            self._rev[key] = f"[[{entity_type.value}_{self._ctr[entity_type]}]]"
        return self._rev[key]


def _spans(text: str) -> list[tuple[str, str]]:
    return [(span.type.name, span.text) for span in pattern_spans(text)]


def _one_type(text: str) -> str:
    found = _spans(text)
    assert len(found) == 1, found
    return found[0][0]


# ---------------------------------------------------------------- PHONE (PRD 6)
def test_phone_all_prefix_forms() -> None:
    for text in (
        "call 0803 123 4567 now",
        "call 08031234567 now",
        "call 0803-123-4567 now",
        "call +234 803 123 4567 now",
        "call +2348031234567 now",
        "call 2348031234567 now",
        "call 234 803 123 4567 now",
        "call 803 123 4567 now",
    ):
        assert _one_type(text) == "PHONE", text


def test_phone_spaced_digits() -> None:
    assert _spans("0 8 0 3 1 2 3 4 5 6 7") == [("PHONE", "0 8 0 3 1 2 3 4 5 6 7")]


def test_11_digit_phone_is_phone_not_bvn() -> None:
    assert _one_type("please verify 08031234567 with the bank") == "PHONE"
    assert _one_type("call 09023456789") == "PHONE"


def test_amounts_are_left_alone() -> None:
    assert pattern_spans("Transfer 50000 now") == []
    assert _spans("Transfer 5000000000 to the account") == []
    assert _spans("send 4500000000 later") == []


# ------------------------------------------------------------------ BVN (PRD 6)
def test_bvn_default_for_11_digit_numbers() -> None:
    assert _one_type(" BVN 22334455667") == "BVN"
    assert _one_type("please check 98765432109 in the ledger") == "BVN"


def test_spaced_bvn() -> None:
    assert _spans("BVN 2 2 3 3 4 4 5 5 6 6 7 is needed") == [("BVN", "2 2 3 3 4 4 5 5 6 6 7")]


def test_bvn_with_dashes() -> None:
    assert _spans("BVN 2-2-3-3-4-4-5-5-6-6-7") == [("BVN", "2-2-3-3-4-4-5-5-6-6-7")]


def test_12_digits_are_not_bvn() -> None:
    assert pattern_spans("code 223344556671 is here") == []


# ------------------------------------------------------------------ NIN (PRD 6)
def test_nin_label_forms() -> None:
    assert _one_type("NIN: 22334455667") == "NIN"
    assert _one_type("nin 22334455667") == "NIN"
    assert _one_type("National Identification Number is 22334455667") == "NIN"
    assert _one_type("NIN 08031234567 remains phone") == "PHONE"


def test_nin_window_is_40_chars() -> None:
    # digits start at 34: label is inside the 40-char window → NIN
    assert _one_type("NIN" + "-" * 30 + " 22334455667") == "NIN"
    # digits start at 48: label fell out of the window → falls back to BVN
    assert _one_type("NIN" + "-" * 44 + " 22334455667") == "BVN"


# ----------------------------------------------------------- ACCOUNT_NO (PRD 6)
def test_account_labels() -> None:
    for text in (
        "account 0123456789",
        "Acct: 0123456789",
        "pay to a/c 0123456789",
        "NUBAN 0123456789",
        "account_no 0123456789",
    ):
        assert _one_type(text) == "ACCOUNT_NO", text
    assert _spans("account 0123 4567 89") == [("ACCOUNT_NO", "0123 4567 89")]


def test_bare_10_digits_are_not_account() -> None:
    assert pattern_spans("Transfer 0123456789 raw") == []


def test_account_window_is_40_chars() -> None:
    far = "account:" + " x" * 22 + " 0123456789"
    assert pattern_spans(far) == []


# ----------------------------------------------------------------- EMAIL (PRD 6)
def test_email_forms() -> None:
    assert _spans("mail ada.obi@gtbank.ng") == [("EMAIL", "ada.obi@gtbank.ng")]
    assert _spans("ada+zzz@mail2.aegis.ng") == [("EMAIL", "ada+zzz@mail2.aegis.ng")]
    assert _spans("write to tolu.o@x.ng and ada@y.com.ng") == [
        ("EMAIL", "tolu.o@x.ng"),
        ("EMAIL", "ada@y.com.ng"),
    ]


# ----------------------------------------------------------- PERSON: gazetteer
def test_gazetteer_title_and_allcaps_and_lower_pairs() -> None:
    assert _persons("Chinedu Okafor") == [(PT, "Chinedu Okafor")]
    assert _persons("CHINEDU OKAFOR") == [(PT, "CHINEDU OKAFOR")]
    assert _persons("chinedu okafor") == [(PT, "chinedu okafor")]
    assert _persons("Chinedu Kelechi Okafor") == [(PT, "Chinedu Kelechi Okafor")]


def _persons(text: str) -> list[tuple[EntityType, str]]:
    return [(span.type, span.text) for span in find_persons(text)]


def test_gazetteer_single_names() -> None:
    assert _persons("ask Ada Obi") == [(PT, "Ada Obi")]
    assert _persons("ask Chidi alone") == [(PT, "Chidi")]
    assert _persons(" quaint ") == []


def test_gazetteer_lowercase_single_not_a_span() -> None:
    assert _persons("say chidi to me") == []


def test_gazetteer_runs_break_on_names_not_words() -> None:
    # "and" is not a name: no run across it; possessives not glued.
    assert _persons("Chinedu and Okafor") == [(PT, "Chinedu"), (PT, "Okafor")]


# ------------------------------------------------------------------ merging 5.2
def test_merge_longest_wins() -> None:
    merged = merge_spans(
        [
            Span(0, 4, PT, "Musa"),
            Span(0, 15, PT, "Musa Danjuma"),  # longest
            Span(6, 15, PT, "Danjuma"),
        ]
    )
    assert merged == [Span(0, 15, PT, "Musa Danjuma")]


def test_merge_priority_on_ties() -> None:
    # Same 11-digit range reached as PHONE and BVN: PHONE wins (PRD 6 order).
    merged = merge_spans(
        [Span(0, 11, BV, "08031234567"), Span(0, 11, PH, "08031234567")]
    )
    assert merged[0].type == PH


def test_email_protects_digits_inside_it() -> None:
    assert _spans("contact b22334455667@x.ng") == [("EMAIL", "b22334455667@x.ng")]


# ------------------------------------------------------- scrub_messages (Step 3)
def _msg(role: str, content: object, **extra: object) -> dict[str, object]:
    return {"role": role, "content": content, **extra}


async def test_scrub_messages_string_and_counts_and_ms() -> None:
    fake = FakeSessionMap()
    messages = [_msg("user", "Transfer 50000 to Chinedu Okafor, phone 0803 123 4567")]
    new, counts, ms = await scrub_messages(messages, fake, None)
    assert new[0]["content"] == "Transfer 50000 to [[PERSON_1]], phone [[PHONE_1]]"
    assert counts == {entity_type: 0 for entity_type in EntityType} | {
        PT: 1, PH: 1, BV: 0, NI: 0, AC: 0, EM: 0
    }
    assert ms > 0


async def test_scrub_messages_placeholder_stability() -> None:
    fake = FakeSessionMap()
    messages = [_msg("user", "Ada Obi? no Ada Obi again")]  # same value twice
    new, counts, _ = await scrub_messages(messages, fake, None)
    assert new[0]["content"] == "[[PERSON_1]]? no [[PERSON_1]] again"
    assert counts[PT] == 2


async def test_scrub_list_of_parts_content() -> None:
    fake = FakeSessionMap()
    messages = [
        _msg(
            "user",
            [
                {"type": "text", "text": "Uche called, BVN 22334455667"},
                {"type": "image_url", "image_url": {"url": "https://x/y.png"}},
            ],
        )
    ]
    new, counts, _ = await scrub_messages(messages, fake, None)
    parts = new[0]["content"]
    assert parts[0]["text"] == "[[PERSON_1]] called, BVN [[BVN_1]]"
    assert parts[1] == {"type": "image_url", "image_url": {"url": "https://x/y.png"}}
    assert counts[PT] == 1 and counts[BV] == 1


async def test_scrub_assistant_tool_calls_arguments_json() -> None:
    fake = FakeSessionMap()
    arguments = json.dumps(
        {"account_no": "0123456789", "amount": 50000, "to": "Chinedu Okafor"}
    )
    messages = [
        _msg(
            "assistant",
            None,
            tool_calls=[
                {
                    "id": "call_1",
                    "type": "function",
                    "function": {"name": "initiate_transfer", "arguments": arguments},
                }
            ],
        )
    ]
    new, counts, _ = await scrub_messages(messages, fake, None)
    scrubbed = json.loads(new[0]["tool_calls"][0]["function"]["arguments"])
    assert scrubbed == {
        "account_no": "[[ACCOUNT_NO_1]]",
        "amount": 50000,
        "to": "[[PERSON_1]]",
    }
    assert counts[AC] == 1 and counts[PT] == 1


async def test_scrub_arguments_invalid_json_scrubs_as_text() -> None:
    fake = FakeSessionMap()
    messages = [
        _msg(
            "assistant",
            None,
            tool_calls=[
                {
                    "id": "call_1",
                    "type": "function",
                    "function": {"name": "f", "arguments": "{bad json"},
                }
            ],
        )
    ]
    new, _, _ = await scrub_messages(messages, fake, None)
    assert new[0]["tool_calls"][0]["function"]["arguments"] == "{bad json"


async def test_scrub_tool_message_content() -> None:
    fake = FakeSessionMap()
    messages = [_msg("tool", "Customer is Musa Danjuma, BVN 22334455667")]
    new, counts, _ = await scrub_messages(messages, fake, None)
    assert new[0]["content"] == "Customer is [[PERSON_1]], BVN [[BVN_1]]"
    assert counts[PT] == 1 and counts[BV] == 1


async def test_scrub_nested_json_values() -> None:
    fake = FakeSessionMap()
    arguments = json.dumps(
        {
            "nested": {"note": "call Ada Obi", "amount": 12.5},
            "list": ["Ngozi Eze", 1, None, True],
            "nin": "22334455667",
        }
    )
    messages = [
        _msg("assistant", None, tool_calls=[
            {"id": "c", "type": "function", "function": {"name": "t", "arguments": arguments}}
        ])
    ]
    new, counts, _ = await scrub_messages(messages, fake, None)
    data = json.loads(new[0]["tool_calls"][0]["function"]["arguments"])
    assert data == {
        "nested": {"note": "call [[PERSON_1]]", "amount": 12.5},
        "list": ["[[PERSON_2]]", 1, None, True],
        "nin": "[[NIN_1]]",
    }
    assert counts[PT] == 2 and counts[NI] == 1
