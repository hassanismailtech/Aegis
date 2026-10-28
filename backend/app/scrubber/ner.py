"""GLiNER layer of the Scrubber (PRD 5.2): person detection in a thread pool.

The model (settings NER_MODEL, label "person", NER_THRESHOLD) is loaded and
warmed once via warm_ner() from the FastAPI lifespan, never on first request.
Heavy calls run in a thread; the caller enforces NER_TIMEOUT_MS with
asyncio.wait_for — on timeout or error the Scrubber raises ScrubError and the
request fails closed (PRD 8). Inputs are pre-chunked to NER_CHUNK_CHARS by
the Scrubber; one batched inference call covers the whole request.

Phase 2 speed work: NER_RUNTIME=onnx loads the int8 export from NER_ONNX_DIR,
chunks with no candidate name letters skip the model entirely, and successful
results are cached in memory by SHA-256(content), with TTL and an LRU bound.
The cache never stores raw text and is never persisted.
"""

from __future__ import annotations

import asyncio
import hashlib
import logging
import re
import threading
import time
from collections import OrderedDict
from pathlib import Path
from typing import Any

from app.config import settings
from app.detectors.base import Span
from app.errors import ScrubError
from app.schemas import EntityType

LABEL = "person"
CHUNK_CHARS = 2_000  # cap per message (PRD 9 fallback)
_BACKEND = Path(__file__).resolve().parents[2]
_CANDIDATE = re.compile(r"[A-Za-z][A-Za-z'’\-]{2,}")

logger = logging.getLogger("aegis.ner")


def has_name_candidate(text: str) -> bool:
    """Cheap skip gate: no 3+ letter word means GLiNER cannot find a name."""
    return _CANDIDATE.search(text) is not None


class _SpanCache:
    """Bounded in-memory TTL cache keyed by a content hash."""

    def __init__(self, ttl_seconds: int, max_entries: int) -> None:
        self._ttl = ttl_seconds
        self._max = max_entries
        self._items: OrderedDict[str, tuple[float, list[Span]]] = OrderedDict()

    def get(self, key: str, now: float) -> list[Span] | None:
        if self._ttl <= 0:
            return None
        item = self._items.get(key)
        if item is None:
            return None
        stored_at, spans = item
        if now - stored_at > self._ttl:
            del self._items[key]
            return None
        self._items.move_to_end(key)
        return spans

    def put(self, key: str, spans: list[Span], now: float) -> None:
        if self._ttl <= 0:
            return
        self._items[key] = (now, list(spans))
        self._items.move_to_end(key)
        while len(self._items) > self._max:
            self._items.popitem(last=False)


def _cache_key(chunk: str, threshold: float) -> str:
    return hashlib.sha256(f"{threshold}\0{chunk}".encode()).hexdigest()


class GlinerNer:
    """Lazy GLiNER wrapper; predict() only ever runs inside worker threads."""

    def __init__(
        self,
        model_name: str | None = None,
        threshold: float | None = None,
    ) -> None:
        self.model_name = model_name or settings.ner_model
        self.threshold = settings.ner_threshold if threshold is None else threshold
        self._model: Any = None  # UniEncoderSpanGLiNER or ONNX runtime model
        self._predict_lock = threading.Lock()  # serialize inference: no thread races
        self._cache = _SpanCache(
            settings.ner_cache_ttl_seconds, settings.ner_cache_max_entries
        )

    def _onnx_path(self) -> Path:
        directory = Path(settings.ner_onnx_dir)
        if not directory.is_absolute():
            directory = _BACKEND / directory
        return directory / settings.ner_onnx_file

    def _load_model(self) -> Any:
        from gliner import GLiNER

        if settings.ner_runtime == "onnx":
            path = self._onnx_path()
            if not path.is_file():
                raise FileNotFoundError(f"ONNX NER model not found: {path}")
            return GLiNER.from_pretrained(
                str(path.parent),
                runtime="onnxruntime",
                runtime_model_file=path.name,
            )
        return GLiNER.from_pretrained(self.model_name)

    def warm(self) -> None:
        """Blocking load + dummy call; lifespan runs it via asyncio.to_thread."""
        if settings.ner_runtime == "torch":
            import os

            import torch

            # 4 logical cores on the demo box: full oversubscription makes p95 2-3x worse
            # (measured in scripts/bench_scrub.py), so pin threads to the core count.
            torch.set_num_threads(min(4, os.cpu_count() or 1))
        model = self._load_model()
        model.predict_entities("Warm up the Scrubber", [LABEL], threshold=self.threshold)
        self._model = model

    @property
    def ready(self) -> bool:
        return self._model is not None

    def find_persons(
        self, chunks: list[str], use_cache: bool = True
    ) -> list[list[Span]]:
        """Blocking batch call over pre-chunked inputs (≤ CHUNK_CHARS each).

        Returns one list of Spans per input chunk. Callers must wrap this in a
        thread with a timeout; a failure here raises ScrubError (PRD 8).
        `use_cache=False` measures the model itself (bench_scrub.py).
        """
        if not chunks:
            return []
        if self._model is None:
            raise ScrubError("NER layer is not warmed up.")
        with self._predict_lock:
            results: list[list[Span] | None] = [None] * len(chunks)
            pending: list[tuple[int, str, str]] = []
            now = time.monotonic()
            for index, chunk in enumerate(chunks):
                if not has_name_candidate(chunk):
                    results[index] = []  # skip: digits/punctuation only
                    continue
                key = _cache_key(chunk, self.threshold)
                cached = self._cache.get(key, now) if use_cache else None
                if cached is not None:
                    results[index] = cached
                else:
                    pending.append((index, chunk, key))
            if pending:
                try:
                    predictions = self._model.inference(
                        [chunk for _, chunk, _ in pending],
                        [LABEL],
                        threshold=self.threshold,
                    )
                except Exception as exc:  # noqa: BLE001 — fail closed, no leak of inputs
                    raise ScrubError("NER layer failed.") from exc
                stored_at = time.monotonic()
                for (index, _, key), found in zip(pending, predictions, strict=True):
                    spans = [
                        Span(
                            entity["start"],
                            entity["end"],
                            EntityType.PERSON,
                            entity["text"],
                        )
                        for entity in found
                    ]
                    if use_cache:
                        self._cache.put(key, spans, stored_at)
                    results[index] = spans
            return [spans if spans is not None else [] for spans in results]


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
