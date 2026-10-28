"""Tests for the hash-chained audit log (Phase 4 Task 1)."""

from __future__ import annotations

import hashlib
import json
import sqlite3
import tempfile
from datetime import datetime, timezone

import pytest

from app.audit import (
    AuditError,
    AuditLog,
    GENESIS_HASH,
    SCHEMA_VERSION,
    canonical_payload,
    event_hash,
    read_events_sync,
    verify_sync,
)
from app.schemas import EntityType, TelemetryEvent


def _event(**overrides) -> TelemetryEvent:
    base = dict(
        request_id="req_" + "a" * 12,
        ts="2026-10-24T09:00:00Z",
        session="sess-test",
        model="gpt-5-mini",
        stream_requested=False,
        entities={
            EntityType.PERSON: 2,
            EntityType.PHONE: 1,
            EntityType.BVN: 1,
            EntityType.NIN: 0,
            EntityType.ACCOUNT_NO: 0,
            EntityType.EMAIL: 0,
        },
        entities_total=4,
        scrub_ms=31.2,
        reinject_ms=0.8,
        upstream_ms=912.4,
        overhead_ms=32.0,
        unresolved=0,
        status="ok",
        fee_usd=0.0003,
    )
    base.update(overrides)
    return TelemetryEvent(**base)


def test_canonical_payload_is_deterministic() -> None:
    e = _event()
    a = canonical_payload(e)
    b = canonical_payload(e)
    assert a == b
    assert "request_id" in a
    assert "scrub_ms" in a


def test_canonical_payload_includes_schema_version() -> None:
    e = _event()
    payload = json.loads(canonical_payload(e))
    assert payload["v"] == SCHEMA_VERSION


def test_event_hash_chains_with_previous() -> None:
    e = _event()
    payload = canonical_payload(e)
    h1 = event_hash(GENESIS_HASH, payload)
    h2 = event_hash(h1, payload)
    assert h1 != h2
    assert len(h1) == 64
    assert len(h2) == 64
    # Recompute
    assert event_hash(GENESIS_HASH, payload) == h1
    assert event_hash(h1, payload) == h2


def test_append_and_verify(temp_path: str) -> None:
    e = _event()
    append_sync(temp_path, e)
    result = verify_sync(temp_path)
    assert result.ok
    assert result.events == 1
    assert result.head != GENESIS_HASH


def test_verify_detects_missing_file() -> None:
    result = verify_sync("/nonexistent/path/audit.db")
    assert not result.ok
    assert result.reason == "audit log not found"


def _create_tampered_db(tamper_fn) -> str:
    """Create a fresh audit db, insert valid events, then tamper."""
    import tempfile
    path = tempfile.mktemp(suffix=".db")
    conn = sqlite3.connect(path)
    try:
        # Create schema without triggers
        conn.execute("PRAGMA journal_mode=WAL")
        conn.executescript(
            """
            CREATE TABLE audit_events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                ts TEXT NOT NULL,
                payload TEXT NOT NULL,
                prev_hash TEXT NOT NULL,
                event_hash TEXT NOT NULL
            );
            CREATE INDEX audit_events_ts ON audit_events(ts);
            """
        )
        # Insert genesis + one valid event
        from app.audit import GENESIS_HASH, canonical_payload, event_hash, SCHEMA_VERSION
        import json
        e = _event()
        payload = canonical_payload(e)
        digest = event_hash(GENESIS_HASH, payload)
        conn.execute(
            "INSERT INTO audit_events (ts, payload, prev_hash, event_hash)"
            " VALUES (?, ?, ?, ?)",
            (e.ts, payload, GENESIS_HASH, digest),
        )
        conn.commit()
        # Now tamper
        tamper_fn(conn)
        conn.commit()
    finally:
        conn.close()
    return path


def test_verify_detects_tampered_payload() -> None:
    path = _create_tampered_db(lambda c: c.execute(
        "UPDATE audit_events SET payload = ? WHERE id = 1",
        ('{"tampered": true}',),
    ))
    result = verify_sync(path)
    assert not result.ok
    assert result.event_id == 1
    assert "payload timestamp does not match" in result.reason or "event_hash mismatch" in result.reason


def test_verify_detects_tampered_hash() -> None:
    path = _create_tampered_db(lambda c: c.execute(
        "UPDATE audit_events SET event_hash = ? WHERE id = 1",
        ("0" * 64,),
    ))
    result = verify_sync(path)
    assert not result.ok
    assert result.event_id == 1
    assert "event_hash mismatch" in result.reason


def test_verify_detects_gap_in_event_ids() -> None:
    path = tempfile.mktemp(suffix=".db")
    conn = sqlite3.connect(path)
    try:
        conn.execute("PRAGMA journal_mode=WAL")
        conn.executescript(
            """
            CREATE TABLE audit_events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                ts TEXT NOT NULL,
                payload TEXT NOT NULL,
                prev_hash TEXT NOT NULL,
                event_hash TEXT NOT NULL
            );
            CREATE INDEX audit_events_ts ON audit_events(ts);
            """
        )
        from app.audit import GENESIS_HASH, canonical_payload, event_hash, SCHEMA_VERSION
        e1 = _event(request_id="req_1")
        e2 = _event(request_id="req_2")
        p1 = canonical_payload(e1)
        h1 = event_hash(GENESIS_HASH, p1)
        p2 = canonical_payload(e2)
        h2 = event_hash(h1, p2)
        conn.execute(
            "INSERT INTO audit_events (ts, payload, prev_hash, event_hash)"
            " VALUES (?, ?, ?, ?), (?, ?, ?, ?)",
            (e1.ts, p1, GENESIS_HASH, h1, e2.ts, p2, h1, h2),
        )
        conn.commit()
        # Delete first event
        conn.execute("DELETE FROM audit_events WHERE id = 1")
        conn.commit()
    finally:
        conn.close()
    result = verify_sync(path)
    assert not result.ok
    assert "event id gap" in result.reason


def test_verify_detects_wrong_prev_hash() -> None:
    # Need two events for this test
    path = tempfile.mktemp(suffix=".db")
    conn = sqlite3.connect(path)
    try:
        conn.execute("PRAGMA journal_mode=WAL")
        conn.executescript(
            """
            CREATE TABLE audit_events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                ts TEXT NOT NULL,
                payload TEXT NOT NULL,
                prev_hash TEXT NOT NULL,
                event_hash TEXT NOT NULL
            );
            CREATE INDEX audit_events_ts ON audit_events(ts);
            """
        )
        from app.audit import GENESIS_HASH, canonical_payload, event_hash, SCHEMA_VERSION
        e1 = _event(request_id="req_1")
        e2 = _event(request_id="req_2")
        p1 = canonical_payload(e1)
        h1 = event_hash(GENESIS_HASH, p1)
        p2 = canonical_payload(e2)
        h2 = event_hash(h1, p2)
        conn.execute(
            "INSERT INTO audit_events (ts, payload, prev_hash, event_hash)"
            " VALUES (?, ?, ?, ?), (?, ?, ?, ?)",
            (e1.ts, p1, GENESIS_HASH, h1, e2.ts, p2, h1, h2),
        )
        conn.commit()
        # Tamper prev_hash of event 2
        c = conn.execute("UPDATE audit_events SET prev_hash = ? WHERE id = 2", ("z" * 64,))
        conn.commit()
    finally:
        conn.close()
    result = verify_sync(path)
    assert not result.ok
    assert result.event_id == 2
    assert "prev_hash does not match" in result.reason


def test_append_different_events_chain(temp_path: str) -> None:
    e1 = _event(request_id="req_1", ts="2026-10-24T09:00:00Z")
    e2 = _event(request_id="req_2", ts="2026-10-24T09:00:01Z")
    append_sync(temp_path, e1)
    append_sync(temp_path, e2)
    result = verify_sync(temp_path)
    assert result.ok
    assert result.events == 2


def test_read_events_sync_date_range(temp_path: str) -> None:
    e1 = _event(request_id="req_1", ts="2026-10-24T09:00:00Z")
    e2 = _event(request_id="req_2", ts="2026-10-25T09:00:00Z")
    e3 = _event(request_id="req_3", ts="2026-10-26T09:00:00Z")
    append_sync(temp_path, e1)
    append_sync(temp_path, e2)
    append_sync(temp_path, e3)

    events = read_events_sync(temp_path, date(2026, 10, 24), date(2026, 10, 25))
    assert len(events) == 2
    assert events[0]["request_id"] == "req_1"
    assert events[1]["request_id"] == "req_2"

    events = read_events_sync(temp_path, date(2026, 10, 26), date(2026, 10, 26))
    assert len(events) == 1
    assert events[0]["request_id"] == "req_3"

    events = read_events_sync(temp_path, date(2026, 10, 20), date(2026, 10, 23))
    assert len(events) == 0


def test_async_audit_log(temp_path: str) -> None:
    import asyncio

    async def _test() -> None:
        log = AuditLog(temp_path)
        e = _event()
        await log.append(e)
        result = await log.verify()
        assert result.ok
        assert result.events == 1

    asyncio.run(_test())


def test_audit_log_appends_to_existing(temp_path: str) -> None:
    import asyncio

    async def _test() -> None:
        log = AuditLog(temp_path)
        await log.append(_event(request_id="req_1"))
        await log.append(_event(request_id="req_2"))
        result = await log.verify()
        assert result.ok
        assert result.events == 2

    asyncio.run(_test())


def test_audit_error_on_invalid_path() -> None:
    import asyncio
    import os

    async def _test() -> None:
        # Use a path in a non-writable location
        if os.name == "nt":
            # On Windows, try to write to a directory we can't create
            bad_path = r"C:\Windows\System32\audit.db"
        else:
            bad_path = "/root/audit.db"
        # Error is raised during AuditLog construction (_init)
        with pytest.raises(AuditError):
            AuditLog(bad_path)

    asyncio.run(_test())


# Fixture for temp audit db
@pytest.fixture
def temp_path() -> str:
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        return f.name


# Need to import append_sync for tests
from app.audit import append_sync
from datetime import date