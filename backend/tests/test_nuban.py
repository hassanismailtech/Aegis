"""CBN NUBAN check digit and bare-account gating (Task 2.2)."""

import pytest

from app.schemas import EntityType
from packs.ng.patterns import pattern_spans
from packs.ng.validators import (
    KNOWN_BANK_CODES,
    bank_code_in_context,
    bank_codes_for,
    is_valid_nuban,
    nuban_check_digit,
)


def test_cbn_worked_example_is_valid() -> None:
    # CBN NUBAN guidelines: First Bank (011) + 000001457 -> 0000014579.
    assert nuban_check_digit("011", "000001457") == 9
    assert is_valid_nuban("0000014579", "011")


def test_known_good_and_known_bad_accounts() -> None:
    assert is_valid_nuban("0000014570", "058")
    assert not is_valid_nuban("0000014571", "058")
    assert is_valid_nuban("0123456789", "050")
    assert not is_valid_nuban("0123456789", "058")
    assert not is_valid_nuban("012345678", "050")
    assert not is_valid_nuban("01234567890", "050")
    assert not is_valid_nuban("0123456789", "05")


def test_check_digit_rejects_bad_input() -> None:
    with pytest.raises(ValueError):
        nuban_check_digit("11", "000001457")
    with pytest.raises(ValueError):
        nuban_check_digit("011", "00000145")


def test_more_than_one_bank_can_match() -> None:
    assert bank_codes_for("0000014579") == ("011", "033", "044")
    assert "011" in KNOWN_BANK_CODES


def test_bank_code_only_from_named_bank_or_label() -> None:
    text = "First Bank 0000014579"
    assert bank_code_in_context(text, text.index("0000014579")) == "011"
    text = "bank code 058 0000014570"
    assert bank_code_in_context(text, text.index("0000014570")) == "058"
    text = "Transfer 011 0000014579"
    assert bank_code_in_context(text, text.index("0000014579")) is None


def _types(text: str) -> list[tuple[EntityType, str]]:
    return [(span.type, span.text) for span in pattern_spans(text)]


def test_bare_account_is_redacted_only_with_a_valid_named_bank() -> None:
    assert _types("First Bank 0000014579") == [
        (EntityType.ACCOUNT_NO, "0000014579")
    ]
    assert _types("First Bank 0 0 0 0 0 1 4 5 7 9") == [
        (EntityType.ACCOUNT_NO, "0 0 0 0 0 1 4 5 7 9")
    ]
    assert _types("GTB 0000014570") == [(EntityType.ACCOUNT_NO, "0000014570")]


def test_bare_invalid_account_and_unknown_bank_stay_untouched() -> None:
    assert pattern_spans("First Bank 0000014578") == []
    assert pattern_spans("GTB 0000014579") == []
    assert pattern_spans("Transfer 0000014579 raw") == []
    assert pattern_spans("Transfer 5000000000 raw") == []


def test_explicit_account_label_keeps_unvalidated_fallback() -> None:
    assert _types("account 0000014578") == [(EntityType.ACCOUNT_NO, "0000014578")]
