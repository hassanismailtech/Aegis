"""Startup behavior, including a mandatory real-Redis readiness check."""

import hashlib
import json
import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path

import httpx
import pytest
from asgi_lifespan import LifespanManager

from app import main
from app.config import Settings


@pytest.fixture(autouse=True)
def local_settings(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    for name, value in {
        "bind_host": "127.0.0.1",
        "aegis_keys_file": "",
        "aegis_ticket_secret": "",
        "aegis_demo_token": "",
        "aegis_insecure_dev": False,
        "ner_enabled": False,
        "audit_db_path": str(tmp_path / "audit.db"),
    }.items():
        monkeypatch.setattr(main.settings, name, value)


@pytest.fixture
def keys_file(tmp_path: Path) -> str:
    path = tmp_path / "keys.json"
    path.write_text(json.dumps([{
        "tenant_id": "startup-test",
        "key_sha256": hashlib.sha256(b"startup-test-key").hexdigest(),
    }]), encoding="utf-8")
    return str(path)


@asynccontextmanager
async def started_client() -> AsyncIterator[httpx.AsyncClient]:
    async with LifespanManager(main.app):
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=main.app),
            base_url="http://aegis.test", trust_env=False,
        ) as client:
            yield client


@pytest.mark.parametrize(("host", "expected"), [
    ("127.0.0.1", True), ("127.5.5.5", True), ("::1", True),
    ("localhost", True), (" LOCALHOST ", True), ("[::1]", True),
    ("0.0.0.0", False), ("::", False), ("192.168.1.5", False),
    ("example.com", False), ("", False), ("999.0.0.1", False),
])
def test_loopback_addresses(host: str, expected: bool) -> None:
    assert main._is_loopback(host) is expected


def test_default_bind_is_loopback(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("BIND_HOST", raising=False)
    assert Settings(_env_file=None).bind_host == "127.0.0.1"


@pytest.mark.parametrize("host", ["0.0.0.0", "::", "192.168.1.5"])
async def test_public_bind_without_keys_refuses(
    monkeypatch: pytest.MonkeyPatch, host: str,
) -> None:
    monkeypatch.setattr(main.settings, "bind_host", host)
    with pytest.raises(RuntimeError, match="Refusing to start"):
        async with LifespanManager(main.app):
            pytest.fail("Unauthenticated public startup must be refused")


@pytest.mark.parametrize("host", ["127.0.0.1", "::1", "localhost"])
async def test_loopback_startup(monkeypatch: pytest.MonkeyPatch, host: str) -> None:
    monkeypatch.setattr(main.settings, "bind_host", host)
    async with started_client() as client:
        assert (await client.get("/healthz")).status_code == 200


async def test_insecure_public_startup_warns(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture,
) -> None:
    monkeypatch.setattr(main.settings, "bind_host", "0.0.0.0")
    monkeypatch.setattr(main.settings, "aegis_insecure_dev", True)
    with caplog.at_level(logging.WARNING, logger="aegis.startup"):
        async with started_client() as client:
            assert (await client.get("/healthz")).status_code == 200
    assert [r.getMessage() for r in caplog.records if r.name == "aegis.startup"] == [
        "AEGIS_INSECURE_DEV=1: running without authentication on a "
        "non-loopback bind. Do not use this in production."
    ]


@pytest.mark.parametrize("host", ["127.0.0.1", "0.0.0.0"])
async def test_keys_require_ticket_secret(
    monkeypatch: pytest.MonkeyPatch, keys_file: str, host: str,
) -> None:
    monkeypatch.setattr(main.settings, "bind_host", host)
    monkeypatch.setattr(main.settings, "aegis_keys_file", keys_file)
    monkeypatch.setattr(main.settings, "aegis_insecure_dev", True)
    with pytest.raises(RuntimeError, match="AEGIS_TICKET_SECRET must be set"):
        async with LifespanManager(main.app):
            pytest.fail("Authentication must require a dedicated ticket secret")


async def test_authenticated_public_startup(
    monkeypatch: pytest.MonkeyPatch, keys_file: str,
) -> None:
    monkeypatch.setattr(main.settings, "bind_host", "0.0.0.0")
    monkeypatch.setattr(main.settings, "aegis_keys_file", keys_file)
    monkeypatch.setattr(main.settings, "aegis_ticket_secret", "startup-test-secret")
    async with started_client() as client:
        assert (await client.get("/healthz")).status_code == 200
        assert main.app.state.tenants is not None


async def test_loopback_startup_with_real_redis() -> None:
    async with started_client() as client:
        response = await client.get("/readyz")
        assert response.status_code == 200
        assert response.json() == {"status": "ready", "redis": "ok", "ner": "disabled"}
