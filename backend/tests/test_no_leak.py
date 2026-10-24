"""Leak test (PRD 3, 5.7): every demo prompt through Aegis → mock Upstream.

None of the planted PII strings may appear in any Wire Tap body — the exact
post-scrub bytes that crossed the border. Prints `leaks: 0 / N planted
entities` (also surfaced under plain `pytest -q` via conftest.py).
"""

import json
import uuid
from pathlib import Path
from collections.abc import AsyncIterator

import httpx
import pytest
from asgi_lifespan import LifespanManager

from app import main as aegis_main
from app.main import app as aegis_app
from app.upstream import Upstream
from scripts.mock_upstream import app as mock_app

PROMPTS_PATH = Path(__file__).resolve().parents[2] / "demo" / "prompts.json"


@pytest.fixture
async def client(monkeypatch: pytest.MonkeyPatch) -> AsyncIterator[httpx.AsyncClient]:
    aegis_upstream = Upstream(
        base_url="http://mock-upstream.test/v1",
        client=httpx.AsyncClient(
            transport=httpx.ASGITransport(app=mock_app), timeout=60.0, trust_env=False
        ),
    )
    monkeypatch.setattr(aegis_main, "build_upstream", lambda: aegis_upstream)
    # GLiNER warms in lifespan; the one-time load needs > asgi-lifespan's 5s default.
    async with LifespanManager(aegis_app, startup_timeout=300):
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=aegis_app),
            base_url="http://aegis.test",
            trust_env=False,
        ) as client:
            yield client


def prompts() -> list[dict]:
    loaded: list[dict] = json.loads(PROMPTS_PATH.read_text(encoding="utf-8"))
    assert len(loaded) == 12  # PRD 11: exactly the 12 demo prompts
    return loaded


async def test_no_planted_pii_in_any_wire_tap_body(
    client: httpx.AsyncClient, pytestconfig: pytest.Config
) -> None:
    planted_prompts = prompts()
    leaks: list[str] = []
    total = 0
    for prompt in planted_prompts:
        total += len(prompt["planted"])
        messages = prompt.get("messages") or [{"role": "user", "content": prompt["text"]}]
        response = await client.post(
            "/v1/chat/completions",
            json={"model": "gpt-5-mini", "messages": messages},
            headers={"X-Aegis-Session": f"leak-{prompt['id']}-{uuid.uuid4().hex[:8]}"},
        )
        assert response.status_code == 200, prompt["id"]
        request_id = response.headers["X-Aegis-Request-Id"]
        tap = await client.get(f"/v1/aegis/wiretap/{request_id}")
        assert tap.status_code == 200, prompt["id"]
        body = json.dumps(tap.json())
        for value in prompt["planted"]:
            if value in body:
                leaks.append(f"{prompt['id']}: {value!r}")
    summary = f"leaks: {len(leaks)} / {total} planted entities"
    print(summary, flush=True)
    setattr(pytestconfig, "_aegis_leak_line", summary)
    assert not leaks, "leaked to the Wire Tap: " + ", ".join(leaks)
