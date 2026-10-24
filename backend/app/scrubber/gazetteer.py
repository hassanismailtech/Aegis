"""Gazetteer layer of the Scrubber (PRD 6, 11): Nigerian name sequences.

Reads backend/data/ng_names.json (~150 first names and surnames across
Yoruba, Igbo, Hausa). A span is a maximal run of up to 3 consecutive
name-words. Runs of 2+ words count in Title, ALL CAPS and lowercase form
("CHINEDU OKAFOR", "chinedu okafor"); a single word must be capitalized so
ordinary English text and pidgin words are not over-redacted.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

from app.schemas import EntityType
from .patterns import Span

_NAMES_PATH = Path(__file__).resolve().parents[2] / "data" / "ng_names.json"
_TOKEN = re.compile(r"[A-Za-z]+")
_MAX_RUN = 3


def _names() -> set[str]:
    """Lowercased union of first names and surnames (loaded once per process)."""
    data: dict[str, list[str]] = json.loads(_NAMES_PATH.read_text(encoding="utf-8"))
    return {name.casefold() for names in data.values() for name in names}


_NAMES = _names()


def find_persons(text: str) -> list[Span]:
    """Start..end of each gazetteer name sequence in `text` (PRD 6 PERSON)."""
    words = [
        ((word := m.group(0)).islower(), word.casefold() in _NAMES, m.start(), m.end())
        for m in _TOKEN.finditer(text)
    ]
    lower, name = 0, 1
    spans: list[Span] = []
    i = 0
    while i < len(words):
        if not words[i][name]:
            i += 1
            continue
        j = i + 1
        while j < len(words) and words[j][name] and j - i < _MAX_RUN:
            j += 1
        if j - i >= 2 or not words[i][lower]:
            start, end = words[i][2], words[j - 1][3]
            spans.append(Span(start, end, EntityType.PERSON, text[start:end]))
        i = j
    return spans
