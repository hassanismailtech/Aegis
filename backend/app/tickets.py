"""Short-lived HMAC-signed tickets for the browser SSE feed (60 s)."""

from __future__ import annotations

import base64
import binascii
import hashlib
import hmac
import json
import secrets
import time
from dataclasses import dataclass

TICKET_TTL_SECONDS = 60
_MAX_TICKET_LENGTH = 256


def _b64encode(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).rstrip(b"=").decode("ascii")


def _b64decode(value: str) -> bytes:
    padding = "=" * (-len(value) % 4)
    return base64.urlsafe_b64decode(value + padding)


@dataclass(frozen=True)
class TicketSigner:
    """Issues and verifies scoped tickets without storing server-side state."""

    secret: bytes

    @classmethod
    def from_settings(cls, configured_secret: str) -> TicketSigner:
        """Configured secret, else an ephemeral per-process one for local dev."""
        secret = configured_secret or secrets.token_urlsafe(32)
        return cls(secret.encode("utf-8"))

    def issue(self, now: int | None = None) -> tuple[str, int]:
        """Return ``(ticket, expires_at)``; ``now`` exists for tests."""
        issued_at = int(time.time()) if now is None else now
        expires_at = issued_at + TICKET_TTL_SECONDS
        payload = _b64encode(
            json.dumps(
                {"v": 1, "iat": issued_at, "exp": expires_at},
                separators=(",", ":"),
            ).encode("ascii")
        )
        signature = _b64encode(
            hmac.new(self.secret, payload.encode("ascii"), hashlib.sha256).digest()
        )
        return f"{payload}.{signature}", expires_at

    def verify(self, ticket: str, now: int | None = None) -> bool:
        """True only for an untampered, unexpired ticket signed by this key."""
        if not ticket or len(ticket) > _MAX_TICKET_LENGTH:
            return False
        try:
            payload, signature = ticket.split(".")
            expected = hmac.new(
                self.secret, payload.encode("ascii"), hashlib.sha256
            ).digest()
            if not hmac.compare_digest(_b64decode(signature), expected):
                return False
            claims = json.loads(_b64decode(payload))
        except (ValueError, binascii.Error, json.JSONDecodeError):
            return False
        if not isinstance(claims, dict) or claims.get("v") != 1:
            return False
        expires_at = claims.get("exp")
        if not isinstance(expires_at, int) or isinstance(expires_at, bool):
            return False
        current = int(time.time()) if now is None else now
        return expires_at > current
