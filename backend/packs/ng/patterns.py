"""Pattern layer of the Nigerian pack (PRD 6): regex entities with context windows.

Order matters: PHONE is matched before the 11-digit IDs because a national
phone number is 11 digits starting with 0. ACCOUNT_NO needs a label
(account/acct/a/c/NUBAN) within 40 chars before the digits; bare 10-digit
numbers are usually amounts and stay untouched. Labels for NIN/ACCOUNT_NO
are searched case-insensitively in the 40-char window before a digit run.
Digits separated by spaces or dashes (item "2 2 3 3 4 4 5 5 6 6 7") count as
one run for every digit type.
"""

from __future__ import annotations

import re
from collections.abc import Sequence

from app.detectors.base import Span
from app.schemas import EntityType

_WINDOW = 40  # chars of context checked before a digit run (PRD 6)
_SEP = r"[ \t\u00a0-]"  # spaces or dashes allowed between digit groups

# 11/10 digit runs with optional spaces or dashes between every pair (PRD 6).
_DIG11 = re.compile(rf"(?<!\d)(?:\d{_SEP}?){{10}}\d(?!\d)")
_DIG10 = re.compile(rf"(?<!\d)(?:\d{_SEP}?){{9}}\d(?!\d)")
_PHONE = re.compile(
    rf"(?<!\d)(?:\+234{_SEP}*|234{_SEP}*|0{_SEP}?)?"
    rf"[789]{_SEP}?[01](?:{_SEP}*\d){{8}}(?!\d)"
)
_PHONE_CONTEXT = re.compile(r"(?i)(?:call|phone|tel(?:ephone)?|mobile|contact)\s*$")
_EMAIL = re.compile(r"[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}")
# Labels tolerate JSON key spellings ("nin", "account_no") around underscores.
_NIN_LABEL = re.compile(r"(?i)(?<![a-z])nin(?![a-z])|national identification")
_ACCOUNT_LABEL = re.compile(
    r"(?i)(?<![a-z])(?:accounts?[_ ]?no|accounts?[_ ]?number|accounts?|acct|a/c|nuban)(?![a-z])"
)


def _window_has(text: str, start: int, label: re.Pattern[str]) -> bool:
    """True when `label` matches within the _WINDOW chars before `start`."""
    window_start = max(0, start - _WINDOW)
    return label.search(text[window_start:start]) is not None


def _overlaps_any(start: int, end: int, taken: list[Span]) -> bool:
    return any(start < span.end and span.start < end for span in taken)


def pattern_spans(text: str) -> list[Span]:
    """All regex entities (PRD 6): EMAIL, PHONE, NIN, ACCOUNT_NO, BVN."""
    spans: list[Span] = [
        Span(match.start(), match.end(), EntityType.EMAIL, match.group(0))
        for match in _EMAIL.finditer(text)
    ]
    spans.extend(
        Span(match.start(), match.end(), EntityType.PHONE, match.group(0))
        for match in _PHONE.finditer(text)
        if (
            match.group(0).lstrip().startswith(("0", "234", "+234"))
            or _PHONE_CONTEXT.search(text[max(0, match.start() - _WINDOW):match.start()])
        )
    )
    for match in _DIG11.finditer(text):
        if _overlaps_any(match.start(), match.end(), spans):
            continue  # phone digits are 11: never also BVN/NIN (PRD 6)
        label = (
            EntityType.NIN
            if _window_has(text, match.start(), _NIN_LABEL)
            else EntityType.BVN  # default label for unlabeled 11-digit numbers
        )
        spans.append(Span(match.start(), match.end(), label, match.group(0)))
    for match in _DIG10.finditer(text):
        if _overlaps_any(match.start(), match.end(), spans):
            continue  # bare 10-digit numbers are usually amounts: leave alone
        if _window_has(text, match.start(), _ACCOUNT_LABEL):
            spans.append(
                Span(match.start(), match.end(), EntityType.ACCOUNT_NO, match.group(0))
            )
    spans.sort(key=lambda span: (span.start, span.end))
    return spans


class PatternDetector:
    """Detector adapter for the regex layer."""

    async def detect(self, text: str, prior: Sequence[Span]) -> list[Span]:
        return pattern_spans(text)
