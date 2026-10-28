"""Aegis Proxy (Step 4): Scrubber → Wire Tap → Upstream → Reinjector → Telemetry."""

import asyncio
import hashlib
import hmac
import json
import logging as _logging
import time
import uuid
from collections.abc import AsyncIterator, Callable
from contextlib import asynccontextmanager
from typing import Any

import httpx
from fastapi import Depends, FastAPI, Request, Response
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, StreamingResponse
from redis.asyncio import Redis
from redis.exceptions import RedisError

from app.anthropic_adapter import reinject_response, scrub_request, usage_tokens
from app.audit import AuditError, AuditLog
from app.auth import AuthError, load_keys, require_tenant
from app.config import settings
from app.errors import ScrubError, aegis_error, anthropic_error
from app.limits import BodySizeLimitMiddleware, consume_rate_limit
from app.logs import log_request, log_telemetry
from app.schemas import ChatRequest, MessagesRequest
from app.session_map import SessionMap
from app.scrubber import scrub_messages
from app.scrubber.ner import warm_ner
from app.reinjector import Reinjector
from app.streaming import (
    AnthropicStreamRewriter,
    OpenAIStreamRewriter,
    format_sse,
    sse_events,
)
from app.telemetry import (
    HEARTBEAT_SECONDS,
    PUBSUB_CHANNEL,
    TelemetryEvent,
    make_event,
    record as record_event,
    seed_events,
    stats as telemetry_stats,
)
from app.tickets import TICKET_TTL_SECONDS, TicketSigner
from app.upstream import Upstream, outbound_body

WIRETAP_TTL_SECONDS = 600


_startup_logger = _logging.getLogger("aegis.startup")


def _is_loopback(host: str) -> bool:
    """True for 127.x.x.x, ::1, localhost, and the 0.0.0.0 default (listens locally too)."""
    return host in ("127.0.0.1", "::1", "localhost", "0.0.0.0")


def build_upstream() -> Upstream:
    return Upstream()


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    tenants = load_keys(settings.aegis_keys_file)
    auth_enabled = tenants is not None

    # Startup guard: refuse non-loopback without auth unless AEGIS_INSECURE_DEV
    if not _is_loopback(settings.bind_host) and not auth_enabled:
        if not settings.aegis_insecure_dev:
            raise RuntimeError(
                "Refusing to start: BIND_HOST is not loopback and AEGIS_KEYS_FILE "
                "is not set. Set AEGIS_KEYS_FILE for production, or "
                "AEGIS_INSECURE_DEV=1 for local development."
            )
        _startup_logger.warning(
            "AEGIS_INSECURE_DEV=1: running without authentication on a "
            "non-loopback bind. Do not use this in production."
        )

    # Ticket secret: require a dedicated secret when auth is enabled
    if auth_enabled and not settings.aegis_ticket_secret:
        raise RuntimeError(
            "AEGIS_TICKET_SECRET must be set when AEGIS_KEYS_FILE is configured. "
            "Tickets cannot fall back to the demo token in authenticated mode."
        )

    ticket_secret = settings.aegis_ticket_secret or settings.aegis_demo_token
    app.state.tenants = tenants
    app.state.redis = Redis.from_url(settings.redis_url, decode_responses=True)
    app.state.tickets = TicketSigner.from_settings(ticket_secret)
    app.state.audit = AuditLog(settings.audit_db_path)
    app.state.ner = await warm_ner()  # PRD 5.2: built and warmed in lifespan
    app.state.upstream = build_upstream()
    yield
    await app.state.upstream.aclose()
    await app.state.redis.aclose()


app = FastAPI(lifespan=lifespan)
app.add_middleware(BodySizeLimitMiddleware)
app.add_middleware(
    CORSMiddleware,
    allow_origins=[o.strip() for o in settings.cors_origins.split(",") if o.strip()],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.exception_handler(RequestValidationError)
async def openai_validation_error(request: Request, exc: RequestValidationError) -> JSONResponse:
    message = f"Invalid request body: {exc}"
    if request.url.path == "/v1/messages":
        return JSONResponse(status_code=400, content=anthropic_error(message))
    return JSONResponse(
        status_code=400,
        content=aegis_error(message, "aegis_invalid_request"),
    )


@app.exception_handler(AuthError)
async def openai_auth_error(request: Request, __: AuthError) -> JSONResponse:
    log_request(status="rejected", http_status=401, reason="unauthorized")
    if request.url.path == "/v1/messages":
        return _auth_error(anthropic=True)
    return _auth_error()


def _wiretap_key(request_id: str) -> str:
    return f"aegis:wiretap:{request_id}"


@app.get("/healthz")
async def healthz() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/readyz")
async def readyz(request: Request) -> Response:
    """Ready only when Redis answers and, if enabled, the NER model is warm."""
    ner = getattr(request.app.state, "ner", None)
    ner_ready = not settings.ner_enabled or bool(getattr(ner, "ready", False))
    try:
        redis_ready = bool(
            await asyncio.wait_for(request.app.state.redis.ping(), timeout=2.0)
        )
    except (RedisError, ConnectionError, asyncio.TimeoutError):
        redis_ready = False
    if redis_ready and ner_ready:
        return JSONResponse(
            {
                "status": "ready",
                "redis": "ok",
                "ner": "warm" if settings.ner_enabled else "disabled",
            }
        )
    return JSONResponse(
        status_code=503,
        content={
            "status": "not_ready",
            "redis": "ok" if redis_ready else "unavailable",
            "ner": (
                "warm"
                if settings.ner_enabled and ner_ready
                else "disabled"
                if not settings.ner_enabled
                else "not_warm"
            ),
        },
    )


def _session_id(request: Request, tenant_id: str) -> str:
    """Tenant-scoped Session id: sha256(tenant + client Session or uuid), 16 hex."""
    client_session = request.headers.get("X-Aegis-Session") or uuid.uuid4().hex
    return hashlib.sha256((tenant_id + client_session).encode()).hexdigest()[:16]


def _authorized(request: Request) -> bool:
    """Optional deployment guard for the proxy and operational endpoints."""
    expected = settings.aegis_demo_token
    if not expected:
        return True
    supplied = request.headers.get("X-Aegis-Demo-Token")
    if supplied is None and request.headers.get("Authorization", "").startswith("Bearer "):
        supplied = request.headers["Authorization"][7:]
    return supplied is not None and hmac.compare_digest(supplied, expected)


def _auth_error(*, anthropic: bool = False) -> JSONResponse:
    return JSONResponse(
        status_code=401,
        headers={"WWW-Authenticate": "Bearer"},
        content=(
            anthropic_error("Aegis access token required.", "authentication_error")
            if anthropic
            else aegis_error("Aegis access token required.", "aegis_unauthorized")
        ),
    )


async def _emit(state: Any, event: TelemetryEvent, http_status: int) -> None:
    """Record one event in Redis, logs, the audit chain and metrics.

    Audit append failures are reported as a metadata-only log line and never
    change the client response: the Upstream call may already have completed.
    """
    await record_event(state.redis, event)
    log_telemetry(event, http_status)
    try:
        await state.audit.append(event)
    except AuditError:
        log_request(
            request_id=event.request_id,
            status="audit_error",
            http_status=http_status,
        )


async def _blocked(
    state: Any,
    request_id: str,
    session: str,
    model: str,
    stream_requested: bool,
    scrub_ms: float,
    code: str,
    message: str,
    error: Callable[[str, str], dict[str, Any]] | None = None,
) -> JSONResponse:
    """503 fail-closed (PRD 8) plus a Telemetry Event with status scrub_blocked."""
    event = make_event(
        request_id=request_id,
        session=session,
        model=model,
        stream_requested=stream_requested,
        entities={},
        scrub_ms=scrub_ms,
        reinject_ms=0.0,
        upstream_ms=0.0,
        unresolved=0,
        status="scrub_blocked",
        usage=None,
    )
    await _emit(state, event, 503)
    body = (
        error(message, code)
        if error is not None
        else aegis_error(message, code, err_type="api_error")
    )
    return JSONResponse(
        status_code=503,
        headers={"X-Aegis-Request-Id": request_id},
        content=body,
    )


def _anthropic_api_error(message: str, _code: str) -> dict[str, Any]:
    """Anthropic-shaped fail-closed body (the Messages API has no error code field)."""
    return anthropic_error(message, "api_error")


@app.post("/v1/chat/completions")
async def chat_completions(
    chat: ChatRequest, request: Request, tenant_id: str = Depends(require_tenant)
) -> Response:
    # With keys configured, the tenant key is the chat credential; otherwise
    # keep the existing optional AEGIS_DEMO_TOKEN guard (local-dev behaviour).
    if not tenant_id and not _authorized(request):
        return _auth_error()
    request_id = "req_" + uuid.uuid4().hex
    headers = {"X-Aegis-Request-Id": request_id}
    state = request.app.state
    redis: Redis = state.redis
    session = _session_id(request, tenant_id)
    session_map = SessionMap(redis, session)

    if len(chat.messages) > settings.max_messages:
        log_request(
            request_id=request_id,
            session=session,
            status="rejected",
            http_status=400,
            reason="too_many_messages",
        )
        return JSONResponse(
            status_code=400,
            headers=headers,
            content=aegis_error(
                f"Too many messages: limit {settings.max_messages}.",
                "aegis_too_many_messages",
            ),
        )

    if tenant_id:
        try:
            limit = await consume_rate_limit(redis, tenant_id)
        except RedisError:
            return await _blocked(
                redis, request_id, session, chat.model, chat.stream, 0.0,
                "aegis_state_unavailable", "Redis unavailable; request blocked fail-closed.",
            )
        headers["X-RateLimit-Limit"] = str(settings.rate_limit_capacity)
        headers["X-RateLimit-Remaining"] = str(limit.remaining)
        if not limit.allowed:
            headers["Retry-After"] = str(limit.retry_after)
            log_request(
                request_id=request_id,
                session=session,
                status="rejected",
                http_status=429,
                reason="rate_limited",
            )
            return JSONResponse(
                status_code=429,
                headers=headers,
                content=aegis_error(
                    f"Rate limit exceeded; retry after {limit.retry_after} s.",
                    "aegis_rate_limited",
                    err_type="rate_limit_error",
                ),
            )

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
            state, request_id, session, chat.model, chat.stream,
            (time.perf_counter() - started) * 1000,
            "aegis_scrub_failed", "Scrubber failed; request blocked fail-closed.",
        )
    except RedisError:
        return await _blocked(
            state, request_id, session, chat.model, chat.stream,
            (time.perf_counter() - started) * 1000,
            "aegis_state_unavailable", "Redis unavailable; request blocked fail-closed.",
        )
    started = time.perf_counter()
    headers["X-Aegis-Entities"] = str(sum(entity_counts.values()))
    headers["X-Aegis-Overhead-Ms"] = f"{round(scrub_ms, 1):.1f}"

    outbound = outbound_body(chat.model_dump())
    outbound["messages"] = messages
    outbound["stream"] = chat.stream
    try:
        # Wire Tap = exact outbound body, before Upstream: Redis down blocks fail-closed (PRD 8).
        await redis.set(_wiretap_key(request_id), json.dumps(outbound), ex=WIRETAP_TTL_SECONDS)
    except RedisError:
        return await _blocked(
            state, request_id, session, chat.model, chat.stream, scrub_ms,
            "aegis_state_unavailable", "Redis unavailable; request blocked fail-closed.",
        )

    started = time.perf_counter()
    # The tenant key authenticates with Aegis and must never reach Upstream.
    # BYOK clients can supply a separate Upstream key in X-Upstream-Authorization.
    forwarded_authorization = (
        request.headers.get("X-Upstream-Authorization")
        if tenant_id
        else request.headers.get("Authorization")
    )

    if chat.stream:
        # Load the Session Map before opening the stream: the response headers
        # are already sent by the time the first chunk is rewritten.
        map_started = time.perf_counter()
        try:
            forward = await session_map.forward_map()
        except RedisError:
            forward = {}
        reinject_ms = (time.perf_counter() - map_started) * 1000
        open_started = time.perf_counter()
        status, result = await state.upstream.chat_completions_stream(
            outbound, forwarded_authorization
        )
        upstream_ms = (time.perf_counter() - open_started) * 1000
        if isinstance(result, dict):
            event = reported(
                "upstream_error", scrub_ms, 0.0, upstream_ms, 0, completion=result
            )
            await _emit(state, event, status)
            return JSONResponse(status_code=status, headers=headers, content=result)

        rewriter = OpenAIStreamRewriter(forward)
        stream_status = "ok"

        async def relay() -> AsyncIterator[bytes]:
            nonlocal reinject_ms, upstream_ms, stream_status
            first = True
            try:
                async for event_name, raw in sse_events(result.aiter_lines()):
                    if first:
                        upstream_ms = (time.perf_counter() - open_started) * 1000
                        first = False
                    if raw == "[DONE]":
                        work = time.perf_counter()
                        flushed = rewriter.flush_all()
                        reinject_ms += (time.perf_counter() - work) * 1000
                        for chunk in flushed:
                            yield format_sse(
                                event_name, json.dumps(chunk, separators=(",", ":"))
                            )
                        yield format_sse(None, "[DONE]")
                        break
                    try:
                        parsed = json.loads(raw)
                    except ValueError:
                        yield format_sse(event_name, raw)
                        continue
                    work = time.perf_counter()
                    chunks = (
                        rewriter.rewrite(parsed)
                        if isinstance(parsed, dict)
                        else [parsed]
                    )
                    reinject_ms += (time.perf_counter() - work) * 1000
                    for chunk in chunks:
                        yield format_sse(
                            event_name, json.dumps(chunk, separators=(",", ":"))
                        )
            except httpx.HTTPError:
                stream_status = "upstream_error"
            finally:
                await result.aclose()
                if rewriter.unresolved:
                    stream_status = "state_loss"
                event = reported(
                    stream_status,
                    scrub_ms,
                    reinject_ms,
                    upstream_ms,
                    rewriter.unresolved,
                    entity_counts,
                    {"usage": rewriter.usage},
                )
                await _emit(state, event, 200)

        headers["Cache-Control"] = "no-cache"
        headers["X-Accel-Buffering"] = "no"
        return StreamingResponse(
            relay(), media_type="text/event-stream", headers=headers
        )

    status, data = await state.upstream.chat_completions(outbound, forwarded_authorization)
    upstream_ms = (time.perf_counter() - started) * 1000
    if status >= 400:
        event = reported("upstream_error", scrub_ms, 0.0, upstream_ms, 0, completion=data)
        await _emit(state, event, status)
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
    event = reported(
        response_status, scrub_ms, reinject_ms, upstream_ms, unresolved, entity_counts, data
    )
    await _emit(state, event, status)
    return JSONResponse(status_code=status, headers=headers, content=data)


@app.post("/v1/messages")
async def messages(
    payload: MessagesRequest, request: Request, tenant_id: str = Depends(require_tenant)
) -> Response:
    """Anthropic Messages API: same Scrubber/Reinjector pipeline, streaming included."""
    if not tenant_id and not _authorized(request):
        return _auth_error(anthropic=True)
    request_id = "req_" + uuid.uuid4().hex
    headers = {"X-Aegis-Request-Id": request_id}
    state = request.app.state
    redis: Redis = state.redis
    session = _session_id(request, tenant_id)
    session_map = SessionMap(redis, session)

    if len(payload.messages) > settings.max_messages:
        log_request(
            request_id=request_id,
            session=session,
            status="rejected",
            http_status=400,
            reason="too_many_messages",
        )
        return JSONResponse(
            status_code=400,
            headers=headers,
            content=anthropic_error(f"Too many messages: limit {settings.max_messages}."),
        )

    if tenant_id:
        try:
            limit = await consume_rate_limit(redis, tenant_id)
        except RedisError:
            return await _blocked(
                state, request_id, session, payload.model, payload.stream, 0.0,
                "aegis_state_unavailable", "Redis unavailable; request blocked fail-closed.",
                _anthropic_api_error,
            )
        headers["X-RateLimit-Limit"] = str(settings.rate_limit_capacity)
        headers["X-RateLimit-Remaining"] = str(limit.remaining)
        if not limit.allowed:
            headers["Retry-After"] = str(limit.retry_after)
            log_request(
                request_id=request_id,
                session=session,
                status="rejected",
                http_status=429,
                reason="rate_limited",
            )
            return JSONResponse(
                status_code=429,
                headers=headers,
                content=anthropic_error(
                    f"Rate limit exceeded; retry after {limit.retry_after} s.",
                    "rate_limit_error",
                ),
            )

    def reported(
        status: str,
        scrub: float,
        reinject: float,
        upstream: float,
        unresolved: int,
        entities: dict[Any, int] | None = None,
        response: dict[str, Any] | None = None,
    ) -> TelemetryEvent:
        return make_event(
            request_id=request_id,
            session=session,
            model=payload.model,
            stream_requested=payload.stream,
            entities=entities or {},
            scrub_ms=scrub,
            reinject_ms=reinject,
            upstream_ms=upstream,
            unresolved=unresolved,
            status=status,
            usage=usage_tokens(response.get("usage")) if response else None,
        )

    request_body = payload.model_dump()
    if request_body.get("system") is None:
        request_body.pop("system", None)
    started = time.perf_counter()
    try:
        outbound, entity_counts, scrub_ms = await scrub_request(
            request_body, session_map, state.ner
        )
    except ScrubError:
        return await _blocked(
            state, request_id, session, payload.model, payload.stream,
            (time.perf_counter() - started) * 1000,
            "aegis_scrub_failed", "Scrubber failed; request blocked fail-closed.",
            _anthropic_api_error,
        )
    except RedisError:
        return await _blocked(
            state, request_id, session, payload.model, payload.stream,
            (time.perf_counter() - started) * 1000,
            "aegis_state_unavailable", "Redis unavailable; request blocked fail-closed.",
            _anthropic_api_error,
        )
    outbound = outbound_body(outbound)
    outbound["stream"] = payload.stream
    headers["X-Aegis-Entities"] = str(sum(entity_counts.values()))
    headers["X-Aegis-Overhead-Ms"] = f"{round(scrub_ms, 1):.1f}"
    try:
        await redis.set(_wiretap_key(request_id), json.dumps(outbound), ex=WIRETAP_TTL_SECONDS)
    except RedisError:
        return await _blocked(
            state, request_id, session, payload.model, payload.stream, scrub_ms,
            "aegis_state_unavailable", "Redis unavailable; request blocked fail-closed.",
            _anthropic_api_error,
        )

    started = time.perf_counter()
    # A tenant key authenticates with Aegis and must never reach Upstream; BYOK
    # clients can supply the Anthropic key in X-Upstream-Api-Key instead.
    forwarded_api_key = (
        request.headers.get("X-Upstream-Api-Key")
        if tenant_id
        else request.headers.get("x-api-key")
    )

    if payload.stream:
        # As with OpenAI, resolve the Session Map before the stream starts.
        map_started = time.perf_counter()
        try:
            forward = await session_map.forward_map()
        except RedisError:
            forward = {}
        reinject_ms = (time.perf_counter() - map_started) * 1000
        open_started = time.perf_counter()
        status, result = await state.upstream.messages_stream(
            outbound,
            api_key=forwarded_api_key,
            version=request.headers.get("anthropic-version"),
            beta=request.headers.get("anthropic-beta"),
        )
        upstream_ms = (time.perf_counter() - open_started) * 1000
        if isinstance(result, dict):
            event = reported(
                "upstream_error", scrub_ms, 0.0, upstream_ms, 0, response=result
            )
            await _emit(state, event, status)
            return JSONResponse(status_code=status, headers=headers, content=result)

        rewriter = AnthropicStreamRewriter(forward)
        stream_status = "ok"

        async def relay() -> AsyncIterator[bytes]:
            nonlocal reinject_ms, upstream_ms, stream_status
            first = True
            try:
                async for event_name, raw in sse_events(result.aiter_lines()):
                    if first:
                        upstream_ms = (time.perf_counter() - open_started) * 1000
                        first = False
                    try:
                        parsed = json.loads(raw)
                    except ValueError:
                        yield format_sse(event_name, raw)
                        continue
                    if not isinstance(parsed, dict):
                        yield format_sse(event_name, raw)
                        continue
                    work = time.perf_counter()
                    rewritten = rewriter.rewrite(event_name, parsed)
                    reinject_ms += (time.perf_counter() - work) * 1000
                    for kind, out in rewritten:
                        yield format_sse(
                            kind, json.dumps(out, separators=(",", ":"))
                        )
            except httpx.HTTPError:
                stream_status = "upstream_error"
            finally:
                await result.aclose()
                if rewriter.unresolved:
                    stream_status = "state_loss"
                elif rewriter.failed:
                    stream_status = "upstream_error"
                event = reported(
                    stream_status,
                    scrub_ms,
                    reinject_ms,
                    upstream_ms,
                    rewriter.unresolved,
                    entity_counts,
                    {"usage": rewriter.usage()},
                )
                await _emit(state, event, 200)

        headers["Cache-Control"] = "no-cache"
        headers["X-Accel-Buffering"] = "no"
        return StreamingResponse(
            relay(), media_type="text/event-stream", headers=headers
        )

    status, data = await state.upstream.messages(
        outbound,
        api_key=forwarded_api_key,
        version=request.headers.get("anthropic-version"),
        beta=request.headers.get("anthropic-beta"),
    )
    upstream_ms = (time.perf_counter() - started) * 1000
    if not isinstance(data, dict):
        status, data = 502, anthropic_error(
            "Upstream returned a non-JSON Messages body.", "api_error"
        )
    if status >= 400:
        event = reported("upstream_error", scrub_ms, 0.0, upstream_ms, 0, response=data)
        await _emit(state, event, status)
        return JSONResponse(status_code=status, headers=headers, content=data)

    started = time.perf_counter()
    try:
        forward = await session_map.forward_map()
    except RedisError:
        forward = {}
    unresolved = reinject_response(data, forward)
    reinject_ms = (time.perf_counter() - started) * 1000
    response_status = "state_loss" if unresolved else "ok"
    overhead = round(round(scrub_ms, 1) + round(reinject_ms, 1), 1)
    headers["X-Aegis-Overhead-Ms"] = f"{overhead:.1f}"
    headers["X-Aegis-Unresolved"] = str(unresolved)
    event = reported(
        response_status, scrub_ms, reinject_ms, upstream_ms, unresolved, entity_counts, data
    )
    await _emit(state, event, status)
    return JSONResponse(status_code=status, headers=headers, content=data)


@app.get("/v1/aegis/wiretap/{request_id}")
async def wiretap(request_id: str, request: Request) -> Response:
    if not _authorized(request):
        return _auth_error()
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


@app.post("/v1/aegis/ticket")
async def issue_ticket(request: Request) -> Response:
    """Exchange the deployment token for a short-lived SSE ticket."""
    if not _authorized(request):
        return _auth_error()
    ticket, _ = request.app.state.tickets.issue()
    return JSONResponse(
        {"ticket": ticket, "expires_in": TICKET_TTL_SECONDS},
        headers={"Cache-Control": "no-store"},
    )


@app.get("/v1/aegis/events")
async def events(request: Request) -> StreamingResponse:
    """Live Telemetry Events as SSE (PRD 5.5): event name `telemetry`, heartbeats."""
    ticket = request.query_params.get("ticket", "")
    if not _authorized(request) and not request.app.state.tickets.verify(ticket):
        return _auth_error()

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

    return StreamingResponse(
        stream(),
        media_type="text/event-stream",
        headers={"X-Accel-Buffering": "no", "Cache-Control": "no-cache"},
    )


@app.get("/v1/aegis/stats")
async def stats(request: Request) -> Response:
    """Aggregates: totals, per-type counts, p50/p95 overhead, fee (PRD 5.5, 7.2)."""
    if not _authorized(request):
        return _auth_error()
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
    if not _authorized(request):
        return _auth_error()
    events = seed_events()
    for event in events:
        await record_event(request.app.state.redis, event)
    return JSONResponse(
        {"seeded": len(events), "events": [event.model_dump() for event in events]}
    )
