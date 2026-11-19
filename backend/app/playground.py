"""Opt-in scrub-only playground: ephemeral Sessions, no Telemetry Events."""

import asyncio
import hashlib
import hmac
import ipaddress
import secrets
from contextlib import suppress
from time import time
from uuid import uuid4

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field, field_validator
from redis.asyncio import Redis
from redis.exceptions import RedisError

from app.config import settings
from app.errors import ScrubError, aegis_error
from app.scrubber import scrub_messages
from app.session_map import SessionMap

PLAYGROUND_PATH = "/v1/playground/scrub"
router = APIRouter()
_RATE = """
local count = redis.call('INCR', KEYS[1])
if count == 1 then redis.call('EXPIRE', KEYS[1], 70) end
return count
"""


class PlaygroundRequest(BaseModel):
    text: str = Field(min_length=1)

    @field_validator("text")
    @classmethod
    def bounded_text(cls, value: str) -> str:
        if len(value) > settings.playground_max_chars:
            raise ValueError("Text exceeds the configured character limit.")
        return value


def _client_ip(request: Request) -> str:
    peer = request.client.host if request.client else "unknown"
    if settings.playground_trust_proxy:
        forwarded = request.headers.get("x-forwarded-for", "").split(",", 1)[0].strip()
        try:
            return str(ipaddress.ip_address(forwarded))
        except ValueError:
            pass
    return peer


async def _rate_limit(redis: Redis, ip: str) -> int:
    now = int(time())
    salt_key = f"aegis:pg:salt:{now // 86400}"
    await redis.set(salt_key, secrets.token_hex(32), nx=True, ex=86400 - now % 86400 + 70)
    salt = await redis.get(salt_key)
    if not salt:
        raise RedisError("Playground rate state unavailable.")
    digest = hmac.new(salt.encode(), ip.encode(), hashlib.sha256).hexdigest()[:32]
    count = await redis.eval(_RATE, 1, f"aegis:pg:rl:{digest}:{now // 60}")
    return 60 - now % 60 if count > settings.playground_rate_per_minute else 0


async def _destroy(session: SessionMap) -> None:
    cleanup = asyncio.create_task(asyncio.wait_for(session.destroy(), timeout=2))
    try:
        await asyncio.shield(cleanup)
    except asyncio.CancelledError:
        with suppress(RedisError, TimeoutError):
            await cleanup
        raise


def _error(status: int, message: str, code: str, retry: int = 0) -> JSONResponse:
    headers = {"Cache-Control": "no-store"}
    if retry:
        headers["Retry-After"] = str(retry)
    kind = {503: "api_error", 429: "rate_limit_error"}.get(status, "invalid_request_error")
    return JSONResponse(aegis_error(message, code, kind), status_code=status, headers=headers)


@router.post(PLAYGROUND_PATH)
async def scrub(body: PlaygroundRequest, request: Request) -> JSONResponse:
    if not settings.playground_enabled:
        return _error(404, "Not found.", "aegis_not_found")
    state = request.app.state
    try:
        retry = await _rate_limit(state.redis, _client_ip(request))
        if retry:
            return _error(429, "Rate limit exceeded.", "aegis_rate_limited", retry)
        session = SessionMap(state.redis, "pg-" + uuid4().hex, ttl=60)
        try:
            messages, counts, ms = await scrub_messages(
                [{"role": "user", "content": body.text}], session, state.ner,
            )
            placeholders = list(await session.forward_map())
            entities = [
                {"type": ph[2:-2].rsplit("_", 1)[0], "placeholder": ph}
                for ph in placeholders
            ]
            reply = (
                "Request received for " + " and ".join(placeholders) + "."
                if placeholders else "No sensitive identifiers detected."
            )
            result = {
                "scrubbed": messages[0]["content"], "entities": entities,
                "counts": {kind.value: count for kind, count in counts.items()},
                "simulated_reply": reply, "overhead_ms": round(ms, 2),
                "mode": (
                    "full" if settings.ner_enabled and getattr(state.ner, "ready", False)
                    else "lite"
                ),
            }
        finally:
            await _destroy(session)
    except ScrubError:
        return _error(503, "Scrubber unavailable.", "aegis_scrub_failed")
    except (RedisError, TimeoutError):
        return _error(503, "State unavailable.", "aegis_state_unavailable")
    return JSONResponse(result, headers={"Cache-Control": "no-store"})
