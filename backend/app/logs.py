"""Structured Aegis logs: request ids, counts, types and timings only."""

from __future__ import annotations

import json
import logging
from typing import Any

from app.telemetry import TelemetryEvent

logger = logging.getLogger("aegis.request")


def log_request(**fields: Any) -> None:
    """One JSON log line; callers must pass metadata only, never request text."""
    logger.info(
        json.dumps({"event": "request", **fields}, separators=(",", ":"), sort_keys=True)
    )


def log_telemetry(event: TelemetryEvent, http_status: int) -> None:
    """Log the same safe counters/timings as a Telemetry Event."""
    log_request(
        request_id=event.request_id,
        session=event.session,
        stream=event.stream_requested,
        status=event.status,
        http_status=http_status,
        entities={entity.value: count for entity, count in event.entities.items()},
        entities_total=event.entities_total,
        unresolved=event.unresolved,
        scrub_ms=event.scrub_ms,
        reinject_ms=event.reinject_ms,
        upstream_ms=event.upstream_ms,
        overhead_ms=event.overhead_ms,
    )
