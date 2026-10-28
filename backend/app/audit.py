"""Append-only, hash-chained audit log for Telemetry Events.

Stored in SQLite outside Redis. Rows contain counts, ids, model names and
timings only: never request text, Placeholder values or Session Map contents.
The chain is `event_hash = sha256(prev_hash + canonical_payload)` with a
64-zero genesis hash.
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import sqlite3
import threading
from dataclasses import dataclass
from datetime import date, timedelta
from pathlib import Path
from typing import Any

from app.schemas import TelemetryEvent

GENESIS_HASH = "0" * 64
SCHEMA_VERSION = 1
_WRITE_LOCK = threading.Lock()


class AuditError(Exception):
    """The audit log could not be opened, appended to or read."""


@dataclass(frozen=True)
class VerifyResult:
    ok: bool
    events: int
    head: str = GENESIS_HASH
    event_id: int | None = None
    reason: str = ""


def canonical_payload(event: TelemetryEvent) -> str:
    """Deterministic bytes-to-be-hashed for one Telemetry Event."""
    payload = {"v": SCHEMA_VERSION, **event.model_dump(mode="json")}
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def event_hash(prev_hash: str, payload: str) -> str:
    return hashlib.sha256((prev_hash + payload).encode()).hexdigest()


def _connect(path: str | Path) -> sqlite3.Connection:
    connection = sqlite3.connect(str(path), timeout=10.0)
    connection.execute("PRAGMA busy_timeout=10000")
    return connection


def _read_connection(path: str | Path) -> sqlite3.Connection:
    uri = f"{Path(path).resolve().as_uri()}?mode=ro"
    connection = sqlite3.connect(uri, uri=True, timeout=10.0)
    connection.execute("PRAGMA busy_timeout=10000")
    return connection


def _init(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        with _WRITE_LOCK, _connect(path) as connection:
            connection.execute("PRAGMA journal_mode=WAL")
            connection.executescript(
                """
                CREATE TABLE IF NOT EXISTS audit_events (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    ts TEXT NOT NULL,
                    payload TEXT NOT NULL,
                    prev_hash TEXT NOT NULL,
                    event_hash TEXT NOT NULL
                );
                CREATE INDEX IF NOT EXISTS audit_events_ts ON audit_events(ts);
                CREATE TRIGGER IF NOT EXISTS audit_events_no_update
                BEFORE UPDATE ON audit_events
                BEGIN
                    SELECT RAISE(ABORT, 'audit log is append-only');
                END;
                CREATE TRIGGER IF NOT EXISTS audit_events_no_delete
                BEFORE DELETE ON audit_events
                BEGIN
                    SELECT RAISE(ABORT, 'audit log is append-only');
                END;
                """
            )
    except sqlite3.Error as exc:
        raise AuditError("audit log could not be initialised") from exc


def append_sync(path: str | Path, event: TelemetryEvent) -> None:
    _init(Path(path))
    payload = canonical_payload(event)
    with _WRITE_LOCK:
        connection = _connect(path)
        try:
            connection.execute("BEGIN IMMEDIATE")
            row = connection.execute(
                "SELECT event_hash FROM audit_events ORDER BY id DESC LIMIT 1"
            ).fetchone()
            prev_hash = str(row[0]) if row else GENESIS_HASH
            digest = event_hash(prev_hash, payload)
            connection.execute(
                "INSERT INTO audit_events (ts, payload, prev_hash, event_hash)"
                " VALUES (?, ?, ?, ?)",
                (event.ts, payload, prev_hash, digest),
            )
            connection.commit()
        except sqlite3.Error as exc:
            connection.rollback()
            raise AuditError("audit log append failed") from exc
        finally:
            connection.close()


def verify_sync(path: str | Path) -> VerifyResult:
    if not Path(path).is_file():
        return VerifyResult(ok=False, events=0, reason="audit log not found")
    try:
        connection = _read_connection(path)
    except sqlite3.Error as exc:
        raise AuditError("audit log could not be opened") from exc
    try:
        rows = connection.execute(
            "SELECT id, ts, payload, prev_hash, event_hash"
            " FROM audit_events ORDER BY id"
        ).fetchall()
    except sqlite3.Error as exc:
        raise AuditError("audit log could not be read") from exc
    finally:
        connection.close()

    previous = GENESIS_HASH
    for expected_id, (row_id, ts, payload, prev_hash, digest) in enumerate(rows, start=1):
        if int(row_id) != expected_id:
            return VerifyResult(
                ok=False,
                events=len(rows),
                event_id=int(row_id),
                reason="event id gap (rows were removed)",
            )
        try:
            parsed = json.loads(payload)
        except (TypeError, ValueError):
            return VerifyResult(
                ok=False,
                events=len(rows),
                event_id=int(row_id),
                reason="payload is not valid JSON",
            )
        if not isinstance(parsed, dict) or parsed.get("ts") != ts:
            return VerifyResult(
                ok=False,
                events=len(rows),
                event_id=int(row_id),
                reason="payload timestamp does not match the row",
            )
        if prev_hash != previous:
            return VerifyResult(
                ok=False,
                events=len(rows),
                event_id=int(row_id),
                reason="prev_hash does not match the previous event",
            )
        if digest != event_hash(previous, payload):
            return VerifyResult(
                ok=False,
                events=len(rows),
                event_id=int(row_id),
                reason="event_hash mismatch (payload was modified)",
            )
        previous = digest
    return VerifyResult(ok=True, events=len(rows), head=previous)


def read_events_sync(
    path: str | Path, start: date, end: date
) -> list[dict[str, Any]]:
    """Audit payloads for an inclusive UTC date range, in append order."""
    end_exclusive = (end + timedelta(days=1)).isoformat()
    try:
        connection = _read_connection(path)
    except sqlite3.Error as exc:
        raise AuditError("audit log could not be opened") from exc
    try:
        rows = connection.execute(
            "SELECT payload FROM audit_events WHERE ts >= ? AND ts < ? ORDER BY id",
            (start.isoformat(), end_exclusive),
        ).fetchall()
    except sqlite3.Error as exc:
        raise AuditError("audit log could not be read") from exc
    finally:
        connection.close()
    try:
        events = [json.loads(row[0]) for row in rows]
    except (TypeError, ValueError) as exc:
        raise AuditError("audit log contains an invalid payload") from exc
    return [event for event in events if isinstance(event, dict)]


class AuditLog:
    """Async facade over the append-only SQLite log."""

    def __init__(self, path: str) -> None:
        self.path = path
        _init(Path(path))

    async def append(self, event: TelemetryEvent) -> None:
        await asyncio.to_thread(append_sync, self.path, event)

    async def verify(self) -> VerifyResult:
        return await asyncio.to_thread(verify_sync, self.path)

    async def events(self, start: date, end: date) -> list[dict[str, Any]]:
        return await asyncio.to_thread(read_events_sync, self.path, start, end)
