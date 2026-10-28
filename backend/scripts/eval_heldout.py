"""Held-out recall eval (Phase 2): per-type precision/recall with Wilson 95%
confidence intervals over demo/heldout_eval.jsonl.

The set is separate from demo/labeled_eval.jsonl, which was used while tuning
NER_THRESHOLD. The CI floor applies to PERSON recall by default: if the model
layer falls below --floor (or EVAL_RECALL_FLOOR), the process exits 1 and the
build fails. Only counts are printed; no source text or PII is written.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))  # backend/: `app` package

import argparse
import asyncio
import json
import math
from collections import Counter
from dataclasses import dataclass
from datetime import date

from app.config import settings
from app.errors import ScrubError
from app.schemas import EntityType
from app.scrubber import detect_spans
from app.scrubber.ner import warm_ner

_REPO = Path(__file__).resolve().parents[2]
_DEFAULT_FILE = _REPO / "demo" / "heldout_eval.jsonl"
_Z = 1.96


@dataclass(frozen=True)
class TypeScore:
    gold: int
    found: int
    tp: int

    @property
    def precision(self) -> float:
        return self.tp / self.found if self.found else 0.0

    @property
    def recall(self) -> float:
        return self.tp / self.gold if self.gold else 0.0


def wilson_interval(successes: int, total: int, z: float = _Z) -> tuple[float, float]:
    """95% Wilson score interval for a binomial proportion."""
    if total <= 0:
        return (0.0, 0.0)
    p = successes / total
    denominator = 1 + z * z / total
    centre = (p + z * z / (2 * total)) / denominator
    margin = z * math.sqrt(p * (1 - p) / total + z * z / (4 * total * total)) / denominator
    return (max(0.0, centre - margin), min(1.0, centre + margin))


def _overlaps_half(labeled: dict, detected_start: int, detected_end: int) -> bool:
    start = max(labeled["start"], detected_start)
    end = min(labeled["end"], detected_end)
    return max(0, end - start) >= 0.5 * (labeled["end"] - labeled["start"])


def score_rows(rows: list[dict]) -> dict[str, TypeScore]:
    """One-to-one half-overlap matching, per type.

    `found` counts every detection of that type, so unmatched detections lower
    precision. Labeled spans without a match lower recall.
    """
    gold: Counter[str] = Counter()
    found: Counter[str] = Counter()
    tp: Counter[str] = Counter()
    for row in rows:
        detected = list(row["detected"])
        for span in detected:
            found[span.type.name] += 1
        for labeled in row["spans"]:
            gold[labeled["type"]] += 1
            match = next(
                (
                    span
                    for span in detected
                    if span.type.name == labeled["type"]
                    and _overlaps_half(labeled, span.start, span.end)
                ),
                None,
            )
            if match is not None:
                detected.remove(match)
                tp[labeled["type"]] += 1
    return {
        etype: TypeScore(gold[etype], found[etype], tp[etype])
        for etype in sorted(gold | found)
    }


def validate_rows(rows: list[dict]) -> None:
    """Reject a malformed labeled file before spending time on the model."""
    valid_types = {entity_type.value for entity_type in EntityType}
    for number, row in enumerate(rows, start=1):
        text = row.get("text")
        spans = row.get("spans")
        if not isinstance(text, str) or not isinstance(spans, list):
            raise ValueError(f"row {number}: expected text and spans")
        previous_end = -1
        for span in spans:
            if span.get("type") not in valid_types:
                raise ValueError(f"row {number}: unknown type")
            start, end = span.get("start"), span.get("end")
            if not isinstance(start, int) or not isinstance(end, int) or start < 0 or end <= start:
                raise ValueError(f"row {number}: bad offsets")
            if text[start:end] != span.get("text"):
                raise ValueError(f"row {number}: span text does not match offsets")
            if start < previous_end:
                raise ValueError(f"row {number}: overlapping spans")
            previous_end = end


def _format_rate(value: float, interval: tuple[float, float]) -> str:
    low, high = interval
    return f"{value:6.1%} [{low:.1%}, {high:.1%}]"


def render(scores: dict[str, TypeScore], floor_type: str, floor: float) -> str:
    header = (
        f"{'type':<12}{'gold':>6}{'found':>7}{'tp':>5}"
        f"{'precision (95% CI)':>25}{'recall (95% CI)':>25}"
    )
    lines = [header, "-" * len(header)]
    total_gold = total_found = total_tp = 0
    for etype, score in scores.items():
        total_gold += score.gold
        total_found += score.found
        total_tp += score.tp
        lines.append(
            f"{etype:<12}{score.gold:>6}{score.found:>7}{score.tp:>5}"
            f"{_format_rate(score.precision, wilson_interval(score.tp, score.found)):>25}"
            f"{_format_rate(score.recall, wilson_interval(score.tp, score.gold)):>25}"
        )
    total = TypeScore(total_gold, total_found, total_tp)
    lines.append("-" * len(header))
    lines.append(
        f"{'TOTAL':<12}{total.gold:>6}{total.found:>7}{total.tp:>5}"
        f"{_format_rate(total.precision, wilson_interval(total.tp, total.found)):>25}"
        f"{_format_rate(total.recall, wilson_interval(total.tp, total.gold)):>25}"
    )
    selected = scores.get(floor_type, TypeScore(0, 0, 0))
    result = "PASS" if selected.recall >= floor and selected.gold else "FAIL"
    lines.append(
        f"floor: {floor_type} recall {selected.recall:.1%} "
        f"(95% CI {wilson_interval(selected.tp, selected.gold)[0]:.1%}"
        f"-{wilson_interval(selected.tp, selected.gold)[1]:.1%}) "
        f">= {floor:.1%}: {result}"
    )
    return "\n".join(lines)


def _load(path: Path) -> list[dict]:
    rows = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line]
    validate_rows(rows)
    return rows


async def _evaluate(rows: list[dict], ner) -> tuple[list[dict], int]:
    """Detect each row; a timeout is a miss and is counted, never retried."""
    scored: list[dict] = []
    timeouts = 0
    for row in rows:
        try:
            detected = await detect_spans(row["text"], ner)
        except ScrubError:
            detected = []
            timeouts += 1
        scored.append({"spans": row["spans"], "detected": detected})
    return scored, timeouts


async def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--file", type=Path, default=_DEFAULT_FILE)
    parser.add_argument("--floor", type=float, default=settings.eval_recall_floor)
    parser.add_argument("--type", default="PERSON", dest="floor_type")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    if not 0 <= args.floor <= 1:
        parser.error("--floor must be between 0 and 1")
    if args.floor_type not in {entity_type.value for entity_type in EntityType}:
        parser.error(f"--type must be one of {', '.join(t.value for t in EntityType)}")

    rows = _load(args.file)
    ner = await warm_ner()
    if ner is not None:
        # First inference is cold (JIT); measure the model, not startup.
        await asyncio.to_thread(ner.find_persons, ["Warm up Chinedu Okafor."])
    mode = "pattern + gazetteer + GLiNER" if ner else "pattern + gazetteer (NER off)"
    scored, timeouts = await _evaluate(rows, ner)
    scores = score_rows(scored)
    report = render(scores, args.floor_type, args.floor)
    print(
        f"held-out eval: {len(rows)} sentences from {args.file.name}; "
        f"layers: {mode}; runtime={settings.ner_runtime}; "
        f"ner_timeout_ms={settings.ner_timeout_ms}"
    )
    if timeouts:
        print(f"NER timeouts counted as misses: {timeouts}")
    print(report)
    if args.output is not None:
        header = (
            f"# Aegis held-out evaluation ({date.today().isoformat()})\n"
            f"# file={args.file.name} sentences={len(rows)} layers={mode} "
            f"model={settings.ner_model} runtime={settings.ner_runtime} "
            f"timeout_ms={settings.ner_timeout_ms}\n"
            f"# floor={args.floor_type}>={args.floor:.2f}\n"
        )
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(header + report + "\n", encoding="utf-8")
    selected = scores.get(args.floor_type)
    return 0 if selected is not None and selected.gold and selected.recall >= args.floor else 1


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
