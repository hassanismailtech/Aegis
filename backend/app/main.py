"""Aegis Proxy (Step 4): Scrubber → Wire Tap → Upstream → Reinjector → Telemetry."""

import hashlib
import json
import time
import uuid
from collections.abc import AsyncIterator, Iterator
from contextlib import asynccontextmanager
from typing import Any

from fastapi import FastAPI, Request, Response
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, StreamingResponse
from redis.asyncio import Redis
from redis.exceptions import RedisError

from app.config import settings
from app.errors import ScrubError, aegis_error
from app.schemas import ChatRequest
from app.session_map import SessionMap
from app.scrubber import scrub_messages
from app.scrubber.ner import warm_ner
from app.reinjector import Reinjector
from app.telemetry import (
    HEARTBEAT_SECONDS,
    PUBSUB_CHANNEL,
    TelemetryEvent,
    make_event,
    record as record_event,
    seed_events,
    stats as telemetry_stats,
)
from app.upstream import Upstream, outbound_body

WIRETAP_TTL_SECONDS = 600


def build_upstream() -> Upstream:
    return Upstream()


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    app.state.redis = Redis.from_url(settings.redis_url, decode_responses=True)
    app.state.ner = await warm_ner()  # PRD 5.2: built and warmed in lifespan
    app.state.upstream = build_upstream()
    yield
    await app.state.upstream.aclose()
    await app.state.redis.aclose()


app = FastAPI(lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=[o.strip() for o in settings.cors_origins.split(",") if o.strip()],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.exception_handler(RequestValidationError)
async def openai_validation_error(_: Request, exc: RequestValidationError) -> JSONResponse:
    return JSONResponse(
        status_code=400,
        content=aegis_error(f"Invalid request body: {exc}", "aegis_invalid_request"),
    )


def _wiretap_key(request_id: str) -> str:
    return f"aegis:wiretap:{request_id}"


@app.get("/healthz")
async def healthz() -> dict[str, str]:
    return {"status": "ok"}


def _sse_events(completion: dict[str, Any]) -> Iterator[bytes]:
    """Pseudo-stream (PRD 5.1): content chunk, finish chunk, [DONE], same id/model."""

    def chunk(delta: dict[str, Any], finish_reason: str | None) -> bytes:
        event = {
            "id": completion["id"],
            "object": "chat.completion.chunk",
            "created": completion.get("created"),
            "model": completion["model"],
            "choices": [{"index": 0, "delta": delta, "finish_reason": finish_reason}],
        }
        return b"data: " + json.dumps(event).encode() + b"\n\n"

    choice = completion["choices"][0]
    content = choice["message"].get("content") or ""
    yield chunk({"role": choice["message"].get("role", "assistant"), "content": content}, None)
    yield chunk({}, choice.get("finish_reason"))
    yield b"data: [DONE]\n\n"


def _session_id(request: Request) -> str:
    """PRD 2: X-Aegis-Session, else first 16 hex of sha256 of Authorization;
    with no Authorization header the empty string is hashed."""
    header = request.headers.get("X-Aegis-Session")
    if header:
        return header
    return hashlib.sha256(request.headers.get("Authorization", "").encode()).hexdigest()[:16]


async def _blocked(
    redis: Redis,
    request_id: str,
    session: str,
    chat: ChatRequest,
    scrub_ms: float,
    code: str,
    message: str,
) -> JSONResponse:
    """503 fail-closed (PRD 8) plus a Telemetry Event with status scrub_blocked."""
    await record_event(
        redis,
        make_event(
            request_id=request_id,
            session=session,
            model=chat.model,
            stream_requested=chat.stream,
            entities={},
            scrub_ms=scrub_ms,
            reinject_ms=0.0,
            upstream_ms=0.0,
            unresolved=0,
            status="scrub_blocked",
            usage=None,
        ),
    )
    return JSONResponse(
        status_code=503,
        headers={"X-Aegis-Request-Id": request_id},
        content=aegis_error(message, code, err_type="api_error"),
    )


@app.post("/v1/chat/completions")
async def chat_completions(chat: ChatRequest, request: Request) -> Response:
    request_id = "req_" + uuid.uuid4().hex
    headers = {"X-Aegis-Request-Id": request_id}
    state = request.app.state
    redis: Redis = state.redis
    session = _session_id(request)
    session_map = SessionMap(redis, session)

    def reported(
        status: str,
        scrub: float,
        reinject: float,
        upstream: float,
        unresolved: int,
        entities: dict[Any, int] | None = None,
        completion: dict[str, Any] | None = None,
    ) -> TelemetryEvent:
        return make_event(
            request_id=request_id,
            session=session,
            model=chat.model,
            stream_requested=chat.stream,
            entities=entities or {},
            scrub_ms=scrub,
            reinject_ms=reinject,
            upstream_ms=upstream,
            unresolved=unresolved,
            status=status,
            usage=completion.get("usage") if completion else None,
        )

    started = time.perf_counter()
    try:
        messages, entity_counts, scrub_ms = await scrub_messages(
            chat.messages, session_map, state.ner
        )
    except ScrubError:
        return await _blocked(
            redis, request_id, session, chat, (time.perf_counter() - started) * 1000,
            "aegis_scrub_failed", "Scrubber failed; request blocked fail-closed.",
        )
    except RedisError:
        return await _blocked(
            redis, request_id, session, chat, (time.perf_counter() - started) * 1000,
            "aegis_state_unavailable", "Redis unavailable; request blocked fail-closed.",
        )
    started = time.perf_counter()
    headers["X-Aegis-Entities"] = str(sum(entity_counts.values()))
    headers["X-Aegis-Overhead-Ms"] = f"{round(scrub_ms, 1):.1f}"

    outbound = outbound_body(chat.model_dump())
    outbound["messages"] = messages
    outbound["stream"] = False  # Upstream is always called non-streaming; stream:true is pseudo-streamed.
    try:
        # Wire Tap = exact outbound body, before Upstream: Redis down blocks fail-closed (PRD 8).
        await redis.set(_wiretap_key(request_id), json.dumps(outbound), ex=WIRETAP_TTL_SECONDS)
    except RedisError:
        return await _blocked(
            redis, request_id, session, chat, scrub_ms,
            "aegis_state_unavailable", "Redis unavailable; request blocked fail-closed.",
        )

    started = time.perf_counter()
    status, data = await state.upstream.chat_completions(
        outbound, request.headers.get("Authorization")
    )
    upstream_ms = (time.perf_counter() - started) * 1000
    if status >= 400:
        await record_event(redis, reported("upstream_error", scrub_ms, 0.0, upstream_ms, 0, completion=data))
        return JSONResponse(status_code=status, headers=headers, content=data)

    # Reinjector (PRD 5.4): tolerant Placeholder → original. A Redis outage here
    # cannot unsend Upstream, so an unavailable Session Map degrades the reply
    # to state_loss instead of guessing (PRD 8 integrity row).
    started = time.perf_counter()
    try:
        forward = await session_map.forward_map()
    except RedisError:
        forward = {}
    reinjector = Reinjector(forward)
    reinjector.inject(data)
    unresolved = reinjector.unresolved
    reinject_ms = (time.perf_counter() - started) * 1000
    response_status = "state_loss" if unresolved else "ok"
    overhead = round(round(scrub_ms, 1) + round(reinject_ms, 1), 1)
    headers["X-Aegis-Overhead-Ms"] = f"{overhead:.1f}"
    headers["X-Aegis-Unresolved"] = str(unresolved)
    await record_event(
        redis,
        reported(response_status, scrub_ms, reinject_ms, upstream_ms, unresolved, entity_counts, data),
    )
    if chat.stream:  # PRD 5.1: the reinjected completion feeds the pseudo-stream
        return StreamingResponse(_sse_events(data), media_type="text/event-stream", headers=headers)
    return JSONResponse(status_code=status, headers=headers, content=data)


@app.get("/v1/aegis/wiretap/{request_id}")
async def wiretap(request_id: str, request: Request) -> Response:
    try:
        raw = await request.app.state.redis.get(_wiretap_key(request_id))
    except RedisError:
        return JSONResponse(
            status_code=503,
            content=aegis_error(
                "Redis unavailable.", "aegis_state_unavailable", err_type="api_error"
            ),
        )
    if raw is None:
        return JSONResponse(
            status_code=404,
            content=aegis_error(f"No Wire Tap for {request_id}.", "aegis_not_found"),
        )
    return JSONResponse(content=json.loads(raw))


@app.get("/v1/aegis/events")
async def events(request: Request) -> StreamingResponse:
    """Live Telemetry Events as SSE (PRD 5.5): event name `telemetry`, heartbeats."""

    async def stream() -> AsyncIterator[bytes]:
        pubsub = request.app.state.redis.pubsub()
        await pubsub.subscribe(PUBSUB_CHANNEL)
        try:
            while not await request.is_disconnected():
                try:
                    message = await pubsub.get_message(
                        ignore_subscribe_messages=True, timeout=HEARTBEAT_SECONDS
                    )
                except (RedisError, ConnectionError):
                    break
                if message is None:
                    yield b": heartbeat\n\n"  # keeps proxies from closing idle SSE
                else:
                    yield f"event: telemetry\ndata: {message['data']}\n\n".encode()
        finally:
            await pubsub.aclose()

    return StreamingResponse(stream(), media_type="text/event-stream")


@app.get("/v1/aegis/stats")
async def stats(request: Request) -> Response:
    """Aggregates: totals, per-type counts, p50/p95 overhead, fee (PRD 5.5, 7.2)."""
    try:
        aggregate = await telemetry_stats(request.app.state.redis)
    except RedisError:
        return JSONResponse(
            status_code=503,
            content=aegis_error(
                "Redis unavailable.", "aegis_state_unavailable", err_type="api_error"
            ),
        )
    return JSONResponse(aggregate)


@app.post("/v1/aegis/_seed")
async def seed(request: Request) -> JSONResponse:
    """20 synthetic Telemetry Events for an instantly populated dashboard (PRD 11)."""
    for event in seed_events():
        await record_event(request.app.state.redis, event)
    return JSONResponse({"seeded": 20})
