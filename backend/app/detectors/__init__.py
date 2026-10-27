"""Compose detection layers from the packs listed in DETECTOR_PACKS."""

from __future__ import annotations

import importlib
import re
from functools import lru_cache

from app.detectors.base import Detector, Span

_PACK_NAME = re.compile(r"[a-z][a-z0-9_]*")


@lru_cache(maxsize=8)
def load_detectors(packs: tuple[str, ...]) -> tuple[Detector, ...]:
    """Import each `packs.<name>` module and concatenate its detectors in order."""
    detectors: list[Detector] = []
    for name in packs:
        if _PACK_NAME.fullmatch(name) is None:
            raise ValueError(f"Invalid detector pack name: {name!r}")
        module = importlib.import_module(f"packs.{name}")
        detectors.extend(module.detectors())
    return tuple(detectors)


__all__ = ["Detector", "Span", "load_detectors"]
