"""Recall eval (PRD 5.7): per-type precision and recall of the Scrubber
(pattern + gazetteer + GLiNER) over demo/labeled_eval.jsonl.

A labeled span counts as a true positive when a detected span of the same
type overlaps at least half of the labeled span; matching is one-to-one.
Runs the NER layer when NER_ENABLED, exactly as the proxy runs it.
"""

import asyncio
import json
from collections import Counter
from pathlib import Path

from app.config import settings
from app.scrubber import detect_spans
from app.scrubber.ner import warm_ner

_PRED_FILE = Path(__file__).resolve().parents[2] / "demo" / "labeled_eval.jsonl"


def _overlaps_half(labeled: dict, detected: dict) -> bool:
    start = max(labeled["start"], detected["start"])
    end = min(labeled["end"], detected["end"])
    return max(0, end - start) >= 0.5 * (labeled["end"] - labeled["start"])


def _score(rows: list[dict]) -> dict[str, tuple[int, int, int]]:
    """(gold, detected, true positives) per type."""
    gold = Counter(span["type"] for row in rows for span in row["spans"])
    found: Counter[str] = Counter()
    tp: Counter[str] = Counter()
    for row in rows:
        detected = [
            {"start": s.start, "end": s.end, "type": s.type.name} for s in row["detected"]
        ]
        for etype in gold:
            found[etype] += sum(1 for d in detected if d["type"] == etype)
        for labeled in row["spans"]:
            match = next(
                (
                    d
                    for d in detected
                    if d["type"] == labeled["type"] and _overlaps_half(labeled, d)
                ),
                None,
            )
            if match is not None:
                detected.remove(match)
                tp[labeled["type"]] += 1
    return {
        etype: (gold[etype], found[etype], tp[etype])
        for etype in sorted(gold | found)
    }


async def main() -> None:
    rows = [json.loads(line) for line in _PRED_FILE.read_text(encoding="utf-8").splitlines()]
    ner = await warm_ner()
    mode = "pattern + gazetteer + GLiNER" if ner else "pattern + gazetteer (NER off)"
    print(f"eval: {len(rows)} sentences from demo/labeled_eval.jsonl; layers: {mode}")
    scored = [
        {"spans": row["spans"], "detected": await detect_spans(row["text"], ner)}
        for row in rows
    ]
    header = f"{'type':<12}{'gold':>5}{'found':>7}{'tp':>5}{'precision':>11}{'recall':>9}"
    print(header)
    print("-" * len(header))
    totals = [0, 0]
    for etype, (gold, find, hits) in _score(scored).items():
        precision = hits / find if find else 0.0
        recall = hits / gold if gold else 0.0
        totals[0] += gold
        totals[1] += find
        print(
            f"{etype:<12}{gold:>5}{find:>7}{hits:>5}{precision:>10.0%}{recall:>9.0%}"
        )
    print("-" * len(header))
    joint = sum(h for _, _, h in _score(scored).values())
    precision = joint / totals[1] if totals[1] else 0.0
    recall = joint / totals[0] if totals[0] else 0.0
    print(f"{'TOTAL':<12}{totals[0]:>5}{totals[1]:>7}{joint:>5}{precision:>10.0%}{recall:>9.0%}")


if __name__ == "__main__":
    asyncio.run(main())
