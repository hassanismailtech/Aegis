"""SSE tickets: a 60 s signed ticket replaces the access_token query parameter."""

from __future__ import annotations

import asyncio
import contextlib
import time
from collections.abc import AsyncIterator

import httpx
import pytest
import uvicorn

from app import main as aegis_main
from app.config import settings
from app.main import app as aegis_app
from app.tickets import TICKET_TTL_SECONDS, TicketSigner

_DEMO_TOKEN = "ticket-demo-token"
_SIGNING_SECRET = "ticket-signing-secret"


@pytest.fixture
async def ticket_server(
    monkeypatch: pytest.MonkeyPatch,
) -> AsyncIterator[httpx.AsyncClient]:
    """Real server: ASGITransport buffers SSE bodies instead of streaming them."""
    monkeypatch.setattr(settings, "aegis_demo_token", _DEMO_TOKEN)
    monkeypatch.setattr(settings, "aegis_ticket_secret", _SIGNING_SECRET)
    monkeypatch.setattr(aegis_main, "HEARTBEAT_SECONDS", 0.2)
    config = uvicorn.Config(aegis_app, host="127.0.0.1", port=0, log_level="warning")
    server = uvicorn.Server(config)
    task = asyncio.create_task(server.serve())
    while not server.started:
        await asyncio.sleep(0.05)
    port = server.servers[0].sockets[0].getsockname()[1]
    async with httpx.AsyncClient(
        base_url=f"http://127.0.0.1:{port}", trust_env=False
    ) as client:
        yield client
    server.should_exit = True
    with contextlib.suppress(asyncio.TimeoutError, asyncio.CancelledError):
        await asyncio.wait_for(task, timeout=10)


def test_signer_round_trip_expiry_and_tampering() -> None:
    signer = TicketSigner(b"unit-secret")
    ticket, expires_at = signer.issue(now=1_000)
    assert expires_at == 1_000 + TICKET_TTL_SECONDS == 1_060
    assert ticket.count(".") == 1 and "=" not in ticket
    assert signer.verify(ticket, now=1_000)
    assert signer.verify(ticket, now=1_059)
    assert not signer.verify(ticket, now=1_060)
    assert not signer.verify(ticket, now=1_061)

    tampered = ticket[:-1] + ("A" if ticket[-1] != "A" else "B")
    assert not signer.verify(tampered, now=1_000)
    assert not TicketSigner(b"other-secret").verify(ticket, now=1_000)
    assert not signer.verify(ticket.partition(".")[0], now=1_000)
    assert not signer.verify("x" * 300, now=1_000)
    assert not signer.verify("", now=1_000)


async def test_ticket_endpoint_requires_auth_and_returns_60s_ticket(
    ticket_server: httpx.AsyncClient,
) -> None:
    missing = await ticket_server.post("/v1/aegis/ticket")
    wrong = await ticket_server.post(
        "/v1/aegis/ticket", headers={"X-Aegis-Demo-Token": "wrong"}
    )
    for response in (missing, wrong):
        assert response.status_code == 401
        assert response.json()["error"]["code"] == "aegis_unauthorized"

    response = await ticket_server.post(
        "/v1/aegis/ticket", headers={"X-Aegis-Demo-Token": _DEMO_TOKEN}
    )
    assert response.status_code == 200
    assert response.headers["cache-control"] == "no-store"
    body = response.json()
    assert body["expires_in"] == TICKET_TTL_SECONDS == 60
    assert body["ticket"] != _DEMO_TOKEN
    assert aegis_app.state.tickets.verify(body["ticket"])


async def test_events_rejects_old_query_token_and_invalid_tickets(
    ticket_server: httpx.AsyncClient,
) -> None:
    old = await ticket_server.get(
        "/v1/aegis/events", params={"access_token": _DEMO_TOKEN}
    )
    missing = await ticket_server.get("/v1/aegis/events")
    for response in (old, missing):
        assert response.status_code == 401
        assert response.json()["error"]["code"] == "aegis_unauthorized"

    ticket, _ = aegis_app.state.tickets.issue()
    tampered = await ticket_server.get(
        "/v1/aegis/events",
        params={"ticket": ticket[:-1] + ("A" if ticket[-1] != "A" else "B")},
    )
    expired_ticket, _ = aegis_app.state.tickets.issue(
        now=int(time.time()) - TICKET_TTL_SECONDS - 1
    )
    expired = await ticket_server.get(
        "/v1/aegis/events", params={"ticket": expired_ticket}
    )
    for response in (tampered, expired):
        assert response.status_code == 401
        assert response.json()["error"]["code"] == "aegis_unauthorized"


async def test_events_accepts_a_valid_ticket(
    ticket_server: httpx.AsyncClient,
) -> None:
    issued = await ticket_server.post(
        "/v1/aegis/ticket", headers={"X-Aegis-Demo-Token": _DEMO_TOKEN}
    )
    ticket = issued.json()["ticket"]
    async with ticket_server.stream(
        "GET", "/v1/aegis/events", params={"ticket": ticket}
    ) as stream:
        assert stream.status_code == 200
        assert stream.headers["content-type"].startswith("text/event-stream")
        buffer = ""
        async for chunk in stream.aiter_text():
            buffer += chunk
            if ": heartbeat" in buffer:
                break
    assert ": heartbeat" in buffer
