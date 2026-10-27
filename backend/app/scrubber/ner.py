"""GLiNER layer of the Scrubber (PRD 5.2): person detection in a thread pool.

The model (settings NER_MODEL, label "person", NER_THRESHOLD) is loaded and
warmed once via warm_ner() from the FastAPI lifespan, never on first request.
Heavy calls run in a thread; the caller enforces NER_TIMEOUT_MS with
asyncio.wait_for — on timeout or error the Scrubber raises ScrubError and the
request fails closed (PRD 8). Inputs are pre-chunked to NER_CHUNK_CHARS by
the Scrubber; one batched inference call covers the whole request.
"""

from __future__ import annotations

import asyncio
import logging
import threading
from typing import Any

from app.config import settings
from app.detectors.base import Span
from app.errors import ScrubError
from app.schemas import EntityType

LABEL = "person"
CHUNK_CHARS = 2_000  # cap per message (PRD 9 fallback)

logger = logging.getLogger("aegis.ner")


class GlinerNer:
    """Lazy GLiNER wrapper; predict() only ever runs inside worker threads."""

    def __init__(
        self,
        model_name: str | None = None,
        threshold: float | None = None,
    ) -> None:
        self.model_name = model_name or settings.ner_model
        self.threshold = settings.ner_threshold if threshold is None else threshold
        self._model: Any = None  # UniEncoderSpanGLiNER after warm()
        self._predict_lock = threading.Lock()  # serialize inference: no thread races

    def warm(self) -> None:
        """Blocking load + dummy call; lifespan runs it via asyncio.to_thread."""
        import os

        import torch
        from gliner import GLiNER  # heavy import: paid once per process

        # 4 logical cores on the demo box: full oversubscription makes p95 2-3x worse
        # (measured in scripts/bench_scrub.py), so pin threads to the core count.
        torch.set_num_threads(min(4, os.cpu_count() or 1))
        model = GLiNER.from_pretrained(self.model_name)
        model.predict_entities("Warm up the Scrubber", [LABEL], threshold=self.threshold)
        self._model = model

    @property
    def ready(self) -> bool:
        return self._model is not None

    def find_persons(self, chunks: list[str]) -> list[list[Span]]:
        """Blocking batch call over pre-chunked inputs (≤ CHUNK_CHARS each).

        Returns one list of Spans per input chunk. Callers must wrap this in a
        thread with a timeout; a failure here raises ScrubError (PRD 8).
        """
        if not chunks:
            return []
        if self._model is None:
            raise ScrubError("NER layer is not warmed up.")
        with self._predict_lock:
            try:
                predictions = self._model.inference(chunks, [LABEL], threshold=self.threshold)
            except Exception as exc:  # noqa: BLE001 — fail closed, no leak of inputs
                raise ScrubError("NER layer failed.") from exc
        return [
            [
                Span(
                    entity["start"], entity["end"], EntityType.PERSON, entity["text"]
                )
                for entity in found
            ]
            for found in predictions
        ]


_instance: GlinerNer | None = None
_instance_lock = threading.Lock()


def get_ner() -> GlinerNer:
    """Process-wide instance so the model is built and warmed exactly once."""
    global _instance
    with _instance_lock:
        if _instance is None:
            _instance = GlinerNer()
        return _instance


async def warm_ner() -> GlinerNer | None:
    """Lifespan hook (PRD 5.2): load + warm off the event loop.

    Returns the warmed instance, or None when NER_ENABLED=false or the model
    failed to load (then the Scrubber runs pattern + gazetteer only).
    """
    if not settings.ner_enabled:
        return None
    ner = get_ner()
    if not ner.ready:
        try:
            await asyncio.to_thread(ner.warm)
        except Exception:  # noqa: BLE001 — deployment guard, never log inputs
            logger.warning("NER model failed to load; running without the NER layer.")
            return None
    return ner
