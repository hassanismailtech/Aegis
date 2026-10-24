"""Aegis Proxy (Step 2): transparent passthrough + Wire Tap. No scrubbing yet."""

import json
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
from app.errors import aegis_error
from app.schemas import ChatRequest
from app.upstream import Upstream, outbound_body

WIRETAP_TTL_SECONDS = 600


def build_upstream() -> Upstream:
    return Upstream()


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    app.state.redis = Redis.from_url(settings.redis_url, decode_responses=True)
    # NER warm-up hook (Step 3): load + warm GLiNER here, never on first request (PRD 5.2).
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


@app.post("/v1/chat/completions")
async def chat_completions(chat: ChatRequest, request: Request) -> Response:
    request_id = "req_" + uuid.uuid4().hex
    headers = {"X-Aegis-Request-Id": request_id, "X-Aegis-Overhead-Ms": "0"}
    state = request.app.state

    outbound = outbound_body(chat.model_dump())
    outbound["stream"] = False  # Upstream is always called non-streaming; stream:true is pseudo-streamed.
    try:
        # Wire Tap = exact outbound body, before Upstream: Redis down blocks fail-closed (PRD 8).
        await state.redis.set(_wiretap_key(request_id), json.dumps(outbound), ex=WIRETAP_TTL_SECONDS)
    except RedisError:
        return JSONResponse(
            status_code=503,
            headers=headers,
            content=aegis_error(
                "Redis unavailable; request blocked fail-closed.",
                "aegis_state_unavailable",
                err_type="api_error",
            ),
        )

    status, data = await state.upstream.chat_completions(outbound, request.headers.get("Authorization"))
    if status >= 400:
        return JSONResponse(status_code=status, headers=headers, content=data)
    if chat.stream:
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
