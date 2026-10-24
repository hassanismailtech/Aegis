"""Scrubber bench (PRD 5.7, 9): 100 runs on a 60-word and a 500-word prompt,
p50/p95 for the pattern layer and the NER layer reported separately.

The pattern layer is the deterministic part (regex + gazetteer). The NER layer
follows PRD 9's fallback: GLiNER only on text left after pattern + gazetteer,
capped at 2000 characters per chunk, with the NER_TIMEOUT_MS budget enforced.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))  # backend/: `app` package

import asyncio
import time

from app.config import settings
from app.scrubber import ner_leftover
from app.scrubber.gazetteer import find_persons as gazetteer_persons
from app.scrubber.ner import get_ner, warm_ner
from app.scrubber.patterns import pattern_spans

RUNS = 100
NER_BUDGET_MS = 250.0

_WORDS_60 = (
    "Good afternoon, my name is Chinedu Okafor. I bank at the Ojota branch "
    "and yesterday I sent 50000 naira to Ada Obi. The recipient account is "
    "0123456789, my BVN is 22334455667, and I can be reached on 0803 123 4567. "
    "Also email ada.obi@gtbank.ng for the receipt copy. Our compliance team "
    "reviews every flagged transaction before the month end audit records."
)

_FILLER = (
    "the customer service rep explained that standing instructions and card "
    "controls process overnight while limits regenerate each morning for "
    "every branch officer and the data desk waits for the compliance chief "
)
_PLANTED = [
    "Musa Danjuma wires 250000 from account 3114327650.",
    "Call 0705 442 1189 after five to confirm.",
    "The NUBAN 0765432109 belongs to Funmi Oladiji.",
    "NIN 18938412239 sits on the KYC file.",
    "Mail ada.obi@gtbank.ng for the receipts.",
    "BVN 22334455667 must stay private.",
]


def _words(text: str) -> list[str]:
    return text.split()


assert len(_WORDS_60.split()) == 60, "PRD bench prompt must be a 60-word prompt"


def _prompt_500() -> str:
    out: list[str] = []
    filler = _FILLER.split()
    index = 0
    while len(out) < 500:
        out.extend(_PLANTED[index % len(_PLANTED)].split())
        out.extend(filler)
        index += 1
    del out[500:]
    return " ".join(out)


def percentile(samples: list[float], q: float) -> float:
    ordered = sorted(samples)
    rank = (len(ordered) - 1) * q
    below = int(rank)
    weight = rank - below
    top = min(below + 1, len(ordered) - 1)
    return ordered[below] + (ordered[top] - ordered[below]) * weight


def pattern_layer_ms(text: str) -> float:
    started = time.perf_counter()
    pattern_spans(text)
    gazetteer_persons(text)
    return (time.perf_counter() - started) * 1000


async def bench() -> None:
    ner = None
    if settings.ner_enabled:
        ner = await warm_ner()
    ner_state = "on" if ner is not None else "OFF (NER_ENABLED=false or warm failed)"
    print(f"bench: NER {ner_state}; model={settings.ner_model}; timeout_ms={settings.ner_timeout_ms}")
    if ner is not None:
        chunks = ner_leftover(_WORDS_60, pattern_spans(_WORDS_60))
        for _ in range(3):  # warm jit paths before timing
            await asyncio.to_thread(ner.find_persons, [c for c in chunks if c.strip()])
    for label, prompt in (("60-word", _WORDS_60), ("500-word", _prompt_500())):
        words = len(prompt.split())
        patterns = [pattern_layer_ms(prompt) for _ in range(RUNS)]
        print(f"{label:>9} prompt ({words} words)")
        print(
            f"  pattern layer (regex + gazetteer): "
            f"p50={percentile(patterns, 0.5):.2f}ms p95={percentile(patterns, 0.95):.2f}ms"
        )
        if ner is None:
            print("  NER layer: skipped (disabled)")
            continue
        chunks = [c for c in ner_leftover(prompt, pattern_spans(prompt)) if c.strip()]
        timings = []
        for _ in range(RUNS):
            started = time.perf_counter()
            await asyncio.to_thread(ner.find_persons, list(chunks))
            timings.append((time.perf_counter() - started) * 1000)
        p50, p95 = percentile(timings, 0.5), percentile(timings, 0.95)
        marker = "" if p95 <= NER_BUDGET_MS else f"  (over the {NER_BUDGET_MS:.0f}ms budget: PRD 9 fallback is ACTIVE)"
        print(
            f"  NER layer (GLiNER on leftovers, {len(chunks)} chunk(s), "
            f"uncapped for this report): p50={p50:.1f}ms p95={p95:.1f}ms{marker}"
        )


if __name__ == "__main__":
    asyncio.run(bench())
