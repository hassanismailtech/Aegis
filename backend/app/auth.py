"""Per-tenant API key auth: hashed keys from AEGIS_KEYS_FILE (phase 0).

The file is a JSON list of ``{"tenant_id": "...", "key_sha256": "..."}``.
Only SHA-256 hashes are stored; the presented Bearer key is hashed once and
compared with :func:`hmac.compare_digest`. When the file is unset the proxy
stays open for local development and logs a startup warning.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import logging
import re
from dataclasses import dataclass
from pathlib import Path

from fastapi import Request

logger = logging.getLogger("aegis.auth")
_HEX64 = re.compile(r"[0-9a-f]{64}")


class AuthError(Exception):
    """Missing or invalid API key; mapped to an OpenAI-shaped 401 in main."""


@dataclass(frozen=True)
class TenantKeys:
    """Immutable key-hash → tenant table loaded once at startup."""

    entries: tuple[tuple[str, str], ...]  # (key_sha256, tenant_id)

    def match(self, presented_key: str) -> str | None:
        """Tenant for a presented key, or None; compares every entry in constant time."""
        presented_hash = hashlib.sha256(presented_key.encode("utf-8")).hexdigest()
        tenant_id = None
        for stored_hash, candidate in self.entries:
            if hmac.compare_digest(presented_hash, stored_hash):
                tenant_id = candidate
        return tenant_id


def load_keys(path: str | None) -> TenantKeys | None:
    """Load AEGIS_KEYS_FILE; None means authentication is disabled locally."""
    if not path or not path.strip():
        logger.warning(
            "AEGIS_KEYS_FILE is not set; per-tenant API key authentication is disabled. "
            "This is local development only."
        )
        return None
    try:
        raw = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise RuntimeError("AEGIS_KEYS_FILE could not be read as JSON.") from exc
    if not isinstance(raw, list):
        raise RuntimeError("AEGIS_KEYS_FILE must contain a JSON list.")

    entries: list[tuple[str, str]] = []
    seen: dict[str, str] = {}
    for item in raw:
        if not isinstance(item, dict):
            raise RuntimeError("AEGIS_KEYS_FILE entries must be JSON objects.")
        tenant_id = item.get("tenant_id")
        key_sha256 = item.get("key_sha256")
        if not isinstance(tenant_id, str) or not tenant_id.strip():
            raise RuntimeError("AEGIS_KEYS_FILE entry has an invalid tenant_id.")
        if not isinstance(key_sha256, str):
            raise RuntimeError("AEGIS_KEYS_FILE entry has an invalid key_sha256.")
        tenant_id = tenant_id.strip()
        normalized = key_sha256.strip().lower()
        if _HEX64.fullmatch(normalized) is None:
            raise RuntimeError("AEGIS_KEYS_FILE entry has an invalid key_sha256.")
        previous = seen.get(normalized)
        if previous is not None and previous != tenant_id:
            raise RuntimeError("AEGIS_KEYS_FILE reuses one key hash for two tenants.")
        seen[normalized] = tenant_id
        entries.append((normalized, tenant_id))
    return TenantKeys(tuple(entries))


def _bearer_key(request: Request) -> str | None:
    """Credential from ``Authorization: Bearer <key>``, or None."""
    header = request.headers.get("Authorization")
    if not header:
        return None
    scheme, separator, credential = header.partition(" ")
    if not separator or scheme.lower() != "bearer":
        return None
    key = credential.strip()
    return key or None


async def require_tenant(request: Request) -> str:
    """FastAPI dependency: validated tenant id, or "" in local-dev mode."""
    keys: TenantKeys | None = getattr(request.app.state, "tenants", None)
    if keys is None:
        return ""
    key = _bearer_key(request)
    if key is None:
        raise AuthError
    tenant_id = keys.match(key)
    if tenant_id is None:
        raise AuthError
    return tenant_id
