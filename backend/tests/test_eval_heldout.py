"""Held-out eval scoring, dataset validation and CI floor (Task 2.3)."""

from __future__ import annotations

import sys

import pytest

from app.detectors.base import Span
from app.schemas import EntityType
from scripts import eval_heldout


def _row(text: str, *spans: tuple[int, int, EntityType, str]) -> dict:
    return {
        "text": text,
        "spans": [
            {"start": start, "end": end, "type": entity.name, "text": text[start:end]}
            for start, end, entity, _ in spans
        ],
    }


def test_wilson_interval_bounds() -> None:
    assert eval_heldout.wilson_interval(0, 0) == (0.0, 0.0)
    low, high = eval_heldout.wilson_interval(8, 10)
    assert low < 0.8 < high
    assert 0.0 <= low <= high <= 1.0


def test_validate_rows_catches_bad_offsets() -> None:
    good = _row("Ada Obi", (0, 7, EntityType.PERSON, "Ada Obi"))
    eval_heldout.validate_rows([good])
    with pytest.raises(ValueError):
        eval_heldout.validate_rows(
            [{"text": "Ada Obi", "spans": [{"start": 0, "end": 7, "type": "PERSON", "text": "Ada"}]}]
        )
    with pytest.raises(ValueError):
        eval_heldout.validate_rows(
            [{"text": "Ada Obi", "spans": [{"start": 0, "end": 7, "type": "NOPE", "text": "Ada Obi"}]}]
        )


def test_score_rows_one_to_one_half_overlap() -> None:
    text = "Ada Obi and Musa Danjuma"
    rows = [
        {
            "spans": [
                {"start": 0, "end": 7, "type": "PERSON", "text": "Ada Obi"},
                {"start": 12, "end": 24, "type": "PERSON", "text": "Musa Danjuma"},
            ],
            "detected": [
                Span(0, 3, EntityType.PERSON, "Ada"),  # < half: no match
                Span(12, 24, EntityType.PERSON, "Musa Danjuma"),
                Span(25, 28, EntityType.PERSON, "xxx"),
            ],
        }
    ]
    score = eval_heldout.score_rows(rows)["PERSON"]
    assert (score.gold, score.found, score.tp) == (2, 3, 1)
    assert score.precision == pytest.approx(1 / 3)
    assert score.recall == pytest.approx(1 / 2)


def test_render_floor_pass_and_fail() -> None:
    scores = {"PERSON": eval_heldout.TypeScore(10, 10, 9)}
    assert "PASS" in eval_heldout.render(scores, "PERSON", 0.8)
    assert "FAIL" in eval_heldout.render(scores, "PERSON", 0.95)


async def test_main_exits_nonzero_below_floor(
    monkeypatch: pytest.MonkeyPatch, tmp_path
) -> None:
    rows = [_row("Ada Obi", (0, 7, EntityType.PERSON, "Ada Obi"))]

    async def fake_evaluate(loaded: list[dict], ner: object) -> tuple[list[dict], int]:
        return [{"spans": row["spans"], "detected": []} for row in loaded], 0

    async def fake_warm() -> None:
        return None

    monkeypatch.setattr(eval_heldout, "_load", lambda path: rows)
    monkeypatch.setattr(eval_heldout, "_evaluate", fake_evaluate)
    monkeypatch.setattr(eval_heldout, "warm_ner", fake_warm)
    output = tmp_path / "metrics.txt"
    monkeypatch.setattr(
        sys,
        "argv",
        ["eval_heldout", "--floor", "1.0", "--output", str(output)],
    )
    assert await eval_heldout.main() == 1
    assert "FAIL" in output.read_text(encoding="utf-8")
