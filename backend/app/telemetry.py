"""Telemetry (PRD 5.5, 7.2, 7.3): per-request event → Redis stream + stats.

Events carry counts, ids and timings only — never pre-scrub text and never
Session Map contents. Redis writes are best-effort: a telemetry failure must
never change the client response.
"""

from __future__ import annotations

import json
import math
from collections.abc import Mapping
from datetime import datetime, timezone
from typing import Any

from redis.asyncio import Redis
from redis.exceptions import RedisError

from app.config import settings
from app.schemas import EntityType, TelemetryEvent

EVENTS_KEY = "aegis:events"  # STREAM, MAXLEN ~ 1000 (PRD 7.2)
STATS_KEY = "aegis:stats"  # HASH counters (PRD 7.2)
OVERHEAD_KEY = "aegis:overhead"  # LIST of last 500 overhead_ms values
LEAKTEST_KEY = "aegis:leaktest"  # JSON result of the last `pytest --report` run
PUBSUB_CHANNEL = "aegis:live"  # PUBLISH target for the SSE feed
MAXLEN = 1000
OVERHEAD_WINDOW = 500
HEARTBEAT_SECONDS = 15.0  # SSE comment cadence when no event arrives


def _ts() -> str:
    """PRD 7.3 timestamp shape: 2026-10-24T09:00:00Z."""
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def fee_usd(usage: Mapping[str, Any] | None) -> float:
    """PRD 7.3: (prompt + completion tokens) / 1000 * FEE_USD_PER_1K_TOKENS."""
    if not usage:
        return 0.0
    tokens = int(usage.get("prompt_tokens") or 0) + int(usage.get("completion_tokens") or 0)
    return tokens / 1000 * settings.fee_usd_per_1k_tokens


def make_event(
    request_id: str,
    session: str,
    model: str,
    stream_requested: bool,
    entities: Mapping[str, int],
    scrub_ms: float,
    reinject_ms: float,
    upstream_ms: float,
    unresolved: int,
    status: str,
    usage: Mapping[str, Any] | None,
) -> TelemetryEvent:
    """TelemetryEvent per PRD 7.3; overhead_ms = scrub_ms + reinject_ms."""
    counts: dict[str, int] = {
        entity_type.value: int(entities.get(entity_type.value, 0)) for entity_type in EntityType
    }
    return TelemetryEvent(
        request_id=request_id,
        ts=_ts(),
        session=session,
        model=model,
        stream_requested=stream_requested,
        entities=counts,  # type: ignore[arg-type] — str keys coerce into EntityType
        entities_total=sum(counts.values()),
        scrub_ms=round(scrub_ms, 1),
        reinject_ms=round(reinject_ms, 1),
        upstream_ms=round(upstream_ms, 1),
        overhead_ms=round(round(scrub_ms, 1) + round(reinject_ms, 1), 1),
        unresolved=unresolved,
        status=status,  # type: ignore[arg-type]
        fee_usd=round(fee_usd(usage), 6),
    )


def fields(event: TelemetryEvent) -> dict[str, str]:
    """Flat Redis stream fields for one event (values stringified by redis-py)."""
    payload: dict[str, str] = {
        "request_id": event.request_id,
        "ts": event.ts,
        "session": event.session,
        "model": event.model,
        "stream_requested": str(event.stream_requested).lower(),
        "entities": json.dumps({t.value: n for t, n in event.entities.items()}),
        "entities_total": str(event.entities_total),
        "scrub_ms": f"{event.scrub_ms:.1f}",
        "reinject_ms": f"{event.reinject_ms:.1f}",
        "upstream_ms": f"{event.upstream_ms:.1f}",
        "overhead_ms": f"{event.overhead_ms:.1f}",
        "unresolved": str(event.unresolved),
        "status": event.status,
        "fee_usd": f"{event.fee_usd:.6f}",
    }
    return payload


async def record(redis: Redis, event: TelemetryEvent) -> None:
    """XADD + PUBLISH + HINCRBY (+ overhead push, LTRIM) in one pipeline.

    Swallows RedisError: telemetry is observability, never user-facing.
    """
    pipe = redis.pipeline(transaction=True)
    pipe.xadd(EVENTS_KEY, fields(event), maxlen=MAXLEN, approximate=True)
    pipe.publish(PUBSUB_CHANNEL, event.model_dump_json())
    pipe.hincrby(STATS_KEY, "requests", 1)
    pipe.hincrby(STATS_KEY, "entities_total", event.entities_total)
    for entity_type, count in event.entities.items():
        pipe.hincrby(STATS_KEY, f"entities:{entity_type.value}", count)
    if event.status == "state_loss":
        pipe.hincrby(STATS_KEY, "state_loss", 1)
    pipe.hincrby(STATS_KEY, "fee_micro_usd", round(event.fee_usd * 1_000_000))
    pipe.rpush(OVERHEAD_KEY, f"{event.overhead_ms:.1f}")
    pipe.ltrim(OVERHEAD_KEY, -OVERHEAD_WINDOW, -1)
    try:
        await pipe.execute()
    except RedisError:  # noqa: S110 — best-effort by contract
        pass


def percentile(values: list[float], quantile: float) -> float:
    """Nearest-rank percentile (PRD 9 style p50/p95); 0.0 when empty."""
    if not values:
        return 0.0
    ordered = sorted(values)
    rank = max(0, math.ceil(quantile * len(ordered)) - 1)
    return round(ordered[rank], 1)


async def stats(redis: Redis) -> dict[str, Any]:
    """Aggregates for GET /v1/aegis/stats (totals, per-type, p50/p95, fee)."""
    pipe = redis.pipeline(transaction=True)
    pipe.hgetall(STATS_KEY)
    pipe.lrange(OVERHEAD_KEY, 0, -1)
    pipe.get(LEAKTEST_KEY)
    counters, overhead, leaktest, *_ = await pipe.execute()
    values = [float(value) for value in overhead]
    leaks: dict[str, Any] | None = None
    if leaktest:
        try:
            parsed = json.loads(leaktest)
        except ValueError:
            parsed = None
        if isinstance(parsed, dict):
            leaks = {
                "leaks": int(parsed.get("leaks", 0)),
                "planted": int(parsed.get("planted", 0)),
                "ts": str(parsed.get("ts", "")),
            }
    return {
        "requests": int(counters.get("requests", 0)),
        "entities_total": int(counters.get("entities_total", 0)),
        "entities": {
            entity_type.value: int(counters.get(f"entities:{entity_type.value}", 0))
            for entity_type in EntityType
        },
        "state_loss": int(counters.get("state_loss", 0)),
        "overhead_ms_p50": percentile(values, 0.50),
        "overhead_ms_p95": percentile(values, 0.95),
        "fee_usd": int(counters.get("fee_micro_usd", 0)) / 1_000_000,
        "leaks": leaks,
    }


def seed_events() -> list[TelemetryEvent]:
    """PRD 11: 20 synthetic Telemetry Events so the dashboard is instantly populated.

    Synthetic only: no real PII text anywhere (AGENTS rule 7).
    """
    profiles: list[dict[EntityType, int]] = [
        {EntityType.PERSON: 2, EntityType.BVN: 1, EntityType.PHONE: 1},
        {EntityType.PERSON: 1, EntityType.ACCOUNT_NO: 1, EntityType.NIN: 1},
        {EntityType.PERSON: 1, EntityType.EMAIL: 1, EntityType.PHONE: 1},
        {EntityType.PERSON: 3, EntityType.BVN: 1},
        {EntityType.ACCOUNT_NO: 2, EntityType.EMAIL: 1, EntityType.PERSON: 1},
    ]
    return [
        TelemetryEvent(
            request_id=f"req_seed{i:02d}",
            ts=_ts(),
            session=f"seed-{i:02d}",
            model="gpt-5-mini",
            entities={t.value: profile.get(t, 0) for t in EntityType},
            entities_total=sum(profile.get(t, 0) for t in EntityType),
            scrub_ms=round(0.4 + (i * 0.7) % 4.1, 1),
            reinject_ms=round(0.1 + (i * 0.13) % 0.9, 1),
            upstream_ms=round(180 + (i * 173) % 1100, 1),
            overhead_ms=round(round(0.4 + (i * 0.7) % 4.1, 1) + round(0.1 + (i * 0.13) % 0.9, 1), 1),
            unresolved=0,
            status="ok",
            fee_usd=round(((i * 37) % 850 + 20) / 1_000_000, 6),
        )
        for i, profile in enumerate(profiles * 4)  # 5 profiles x 4 = 20 events
    ]
