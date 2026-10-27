"""Detector interface and pack composition (Task 1)."""

from __future__ import annotations

import pytest

from app import scrubber
from app.detectors import load_detectors
from app.detectors.base import Detector, Span
from app.schemas import EntityType
from app.scrubber import detect_spans
from app.scrubber.gazetteer import find_persons
from app.scrubber.patterns import pattern_spans


async def test_ng_pack_detectors_match_legacy_layers() -> None:
    detectors = load_detectors(("ng",))
    assert len(detectors) == 2
    assert all(isinstance(detector, Detector) for detector in detectors)

    text = "Chinedu Okafor, BVN 22334455667, ada@obi.ng"
    spans: list[Span] = []
    for detector in detectors:
        spans.extend(await detector.detect(text, spans))
    assert spans == [*pattern_spans(text), *find_persons(text)]


async def test_invalid_pack_name_is_rejected() -> None:
    with pytest.raises(ValueError):
        load_detectors(("../ng",))


async def test_scrubber_composes_pack_detectors_in_order(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class FakeDetector:
        def __init__(self) -> None:
            self.calls: list[list[Span]] = []

        async def detect(self, text: str, prior: list[Span]) -> list[Span]:
            self.calls.append(list(prior))
            return [Span(0, 4, EntityType.EMAIL, text[:4])]

    fake = FakeDetector()
    monkeypatch.setattr(scrubber, "_PACK_DETECTORS", (fake,))
    assert await detect_spans("test", None) == [Span(0, 4, EntityType.EMAIL, "test")]
    assert fake.calls == [[]]


async def test_ner_detector_ignores_missing_model() -> None:
    detector = scrubber._NerPersonDetector(None)
    assert isinstance(detector, Detector)
    assert await detector.detect("Chinedu Okafor", []) == []
