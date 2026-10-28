"""CBN NUBAN check-digit validation (CBN NUBAN guidelines, August 2010).

A NUBAN is a 10-digit account number: a 9-digit serial followed by one
check digit. The check digit is computed over the 3-digit CBN bank code
plus the serial, with weights 3, 7, 3 repeated:

    check = (10 - (sum(digit * weight) % 10)) % 10

The bank code is not part of the 10-digit account number. Validating a
bare number therefore needs a bank code from somewhere: trying every known
code would accept almost every 10-digit number (each code accepts about 10%
of serials), so `bank_code_in_context()` only returns a code when the text
names a bank or says "bank code 123" within the same 40-character window.
"""

from __future__ import annotations

import re

_WEIGHTS = (3, 7, 3)
_WINDOW = 40

# CBN codes for the banks this pack can recognise in text. Names are aliases
# mapped to the code; add a code only after checking it against CBN/Interswitch.
_BANK_CODE_BY_ALIAS: dict[str, str] = {
    "access bank": "044",
    "citibank": "023",
    "diamond bank": "063",
    "ecobank": "050",
    "fcmb": "214",
    "fidelity bank": "070",
    "first bank": "011",
    "first bank of nigeria": "011",
    "firstbank": "011",
    "first city monument bank": "214",
    "globus bank": "103",
    "gtb": "058",
    "gtbank": "058",
    "guaranty trust": "058",
    "guaranty trust bank": "058",
    "heritage bank": "030",
    "jaiz bank": "301",
    "keystone bank": "082",
    "lotus bank": "303",
    "mainstreet bank": "014",
    "optimus bank": "107",
    "parallex bank": "104",
    "polaris bank": "076",
    "premium trust bank": "105",
    "providus bank": "101",
    "signature bank": "106",
    "skye bank": "076",
    "stanbic": "221",
    "stanbic ibtc": "221",
    "stanbic ibtc bank": "221",
    "standard chartered": "068",
    "standard chartered bank": "068",
    "sterling bank": "232",
    "suntrust bank": "100",
    "titan trust bank": "102",
    "uba": "033",
    "union bank": "032",
    "union bank of nigeria": "032",
    "united bank for africa": "033",
    "unity bank": "215",
    "wema bank": "035",
    "zenith bank": "057",
}
KNOWN_BANK_CODES = frozenset(_BANK_CODE_BY_ALIAS.values())

_ALIASES = "|".join(
    re.escape(alias) for alias in sorted(_BANK_CODE_BY_ALIAS, key=len, reverse=True)
)
_BANK_NAME = re.compile(rf"(?i)(?<![a-z])(?:{_ALIASES})(?![a-z])")
_BANK_CODE_LABEL = re.compile(r"(?i)\bbank\s+code\s*[:#-]?\s*(\d{3})(?!\d)")
_ACCOUNT = re.compile(r"\d{10}")
_SERIAL = re.compile(r"\d{9}")
_CODE = re.compile(r"\d{3}")


def nuban_check_digit(bank_code: str, serial: str) -> int:
    """CBN check digit for a 3-digit bank code and 9-digit serial."""
    if _CODE.fullmatch(bank_code) is None or _SERIAL.fullmatch(serial) is None:
        raise ValueError("bank_code must be 3 digits and serial must be 9 digits")
    total = sum(
        int(digit) * _WEIGHTS[index % 3]
        for index, digit in enumerate(bank_code + serial)
    )
    return (10 - total % 10) % 10


def is_valid_nuban(account: str, bank_code: str) -> bool:
    """True when `account` is a 10-digit NUBAN for `bank_code`."""
    if _ACCOUNT.fullmatch(account) is None:
        return False
    try:
        return nuban_check_digit(bank_code, account[:9]) == int(account[9])
    except ValueError:
        return False


def bank_codes_for(account: str) -> tuple[str, ...]:
    """Known codes whose check digit matches `account` (may be several)."""
    return tuple(
        sorted(code for code in KNOWN_BANK_CODES if is_valid_nuban(account, code))
    )


def bank_code_in_context(text: str, start: int, window: int = _WINDOW) -> str | None:
    """Bank code named in the `window` characters before `start`, if any.

    The caller uses this only for bare account numbers. A code label is
    accepted ("bank code 011"); a bare 3-digit number is not, because it is
    indistinguishable from an amount or a date.
    """
    before = text[max(0, start - window) : start]
    label = _BANK_CODE_LABEL.search(before)
    if label is not None and label.group(1) in KNOWN_BANK_CODES:
        return label.group(1)
    name = _BANK_NAME.search(before)
    if name is not None:
        return _BANK_CODE_BY_ALIAS[name.group(0).casefold()]
    return None
