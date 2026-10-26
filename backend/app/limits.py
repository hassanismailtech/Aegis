"""Request limits: body size, message count and per-tenant Redis token bucket."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass

from redis.asyncio import Redis
from starlette.types import ASGIApp, Receive, Scope, Send

from app.config import settings
from app.errors import aegis_error

# KEYS = [bucket], ARGV = [capacity, refill_per_second].
# Tokens are stored as floats; TIME comes from Redis so replicas share a clock.
_TOKEN_BUCKET = """
local capacity = tonumber(ARGV[1])
local refill = tonumber(ARGV[2])
local now = redis.call('TIME')
local now_ms = tonumber(now[1]) * 1000 + math.floor(tonumber(now[2]) / 1000)
local values = redis.call('HMGET', KEYS[1], 'tokens', 'ts')
local tokens = tonumber(values[1])
local last_ms = tonumber(values[2])
if tokens == nil then tokens = capacity end
if last_ms == nil then last_ms = now_ms end
local elapsed_s = math.max(0, (now_ms - last_ms) / 1000)
tokens = math.min(capacity, tokens + elapsed_s * refill)
local allowed = tokens >= 1
local retry_after = 0
if allowed then
  tokens = tokens - 1
else
  retry_after = math.ceil((1 - tokens) / refill)
end
redis.call('HSET', KEYS[1], 'tokens', tokens, 'ts', now_ms)
redis.call('PEXPIRE', KEYS[1], math.ceil(capacity / refill * 1000) + 1000)
return {allowed and 1 or 0, math.floor(tokens), retry_after}
"""


@dataclass(frozen=True)
class RateLimitResult:
    allowed: bool
    remaining: int
    retry_after: int


def rate_key(tenant_id: str) -> str:
    """Hashed tenant key: tenant ids never become raw Redis keys."""
    return "aegis:rate:" + hashlib.sha256(tenant_id.encode("utf-8")).hexdigest()


async def consume_rate_limit(redis: Redis, tenant_id: str) -> RateLimitResult:
    """Atomically take one token from this tenant's bucket."""
    if not tenant_id:
        return RateLimitResult(True, 0, 0)
    allowed, remaining, retry_after = await redis.eval(
        _TOKEN_BUCKET,
        1,
        rate_key(tenant_id),
        settings.rate_limit_capacity,
        settings.rate_limit_refill_per_second,
    )
    return RateLimitResult(bool(int(allowed)), int(remaining), int(retry_after))


class BodySizeLimitMiddleware:
    """ASGI body-size guard; rejects before FastAPI parses a request body."""

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        limit = settings.max_body_bytes
        length = _content_length(scope)
        if length is not None and length > limit:
            await _reject(send, limit)
            return

        body = bytearray()
        while True:
            message = await receive()
            if message["type"] == "http.disconnect":
                return
            body.extend(message.get("body", b""))
            if len(body) > limit:
                await _reject(send, limit)
                return
            if not message.get("more_body", False):
                break

        delivered = False

        async def replay() -> dict:
            nonlocal delivered
            if not delivered:
                delivered = True
                return {"type": "http.request", "body": bytes(body), "more_body": False}
            return await receive()  # keep SSE disconnect detection working

        await self.app(scope, replay, send)


def _content_length(scope: Scope) -> int | None:
    for name, value in scope.get("headers", []):
        if name.lower() == b"content-length":
            try:
                return int(value)
            except ValueError:
                return None
    return None


async def _reject(send: Send, limit: int) -> None:
    body = json.dumps(
        aegis_error(
            f"Request body exceeds {limit} bytes.", "aegis_request_too_large"
        ),
        separators=(",", ":"),
    ).encode()
    await send(
        {
            "type": "http.response.start",
            "status": 413,
            "headers": [
                (b"content-type", b"application/json"),
                (b"content-length", str(len(body)).encode()),
            ],
        }
    )
    await send({"type": "http.response.body", "body": body})
