"""Detector contract (PRD 5.2): one layer that returns Entity spans.

Detectors are composed by the Scrubber from the packs named in config.
`prior` carries the spans already found by earlier detectors for the same text:
most layers ignore it, while the GLiNER layer uses it to run only on text left
after the deterministic layers (PRD 9 fallback).
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from typing import Protocol, runtime_checkable

from app.schemas import EntityType


@dataclass(frozen=True)
class Span:
    """A detected PII span: half-open [start, end) offsets into the text."""

    start: int
    end: int
    type: EntityType
    text: str


@runtime_checkable
class Detector(Protocol):
    """One detection layer: returns spans found in `text`."""

    async def detect(self, text: str, prior: Sequence[Span]) -> list[Span]:
        """Return new spans; `prior` is read-only context from earlier layers."""
        ...
