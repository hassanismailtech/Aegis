# Aegis notes

## ASSUMPTIONS

### Step 1: Contracts and state

- Added `backend/app/__init__.py` (not spelled out in PRD 10) so `app` imports reliably as a regular package under `uv run` and pytest.
- `frontend/` is intentionally not created now: PRD 10 marks it as `create-next-app` output (Step 5), and pre-existing files would break `create-next-app`.
- `pyproject.toml` adds `uvicorn` (required to actually run the FastAPI apps, incl. the mock Upstream on :9000) and dev deps `pytest-asyncio` (async tests), plus a `[tool.pytest.ini_options]` section (`asyncio_mode="auto"`, `pythonpath=["."]", testpaths=["tests"]`).
- `backend/.python-version` pins 3.12 (host Python is 3.15; the gliner/torch wheels need <=3.12) so `uv sync` fetches its own 3.12.
- `SessionMap(redis, sid)` takes an optional third `ttl` kwarg defaulting to `SESSION_TTL_SECONDS`, so tests can use a short sliding TTL. Redis clients must be created with `decode_responses=True`.
- `config.py` loads `.env` relative to the backend/ working directory (all backend commands run from `backend/`); `.env.example` stays at repo root per PRD 10, copy it to `backend/.env` to use it.
- `CORS_ORIGINS` is typed as a plain string; Step 2 splits it for the CORS middleware.
- `TelemetryEvent.ts` is a `str` in the exact PRD 7.3 format (`2026-10-24T09:00:00Z`), not a datetime.
- `ChatRequest` validates only `model`, `messages` (loose `list[dict]`), `stream`; unknown fields pass through (PRD 5.1); deeper content handling happens while scrubbing (Step 3).
- Mock Upstream stores received bodies in a process-local list only (AGENTS rule 8: no files for state) and `GET /_tap` returns them as a JSON array.
- Mock Upstream tool mode answers `arguments = {"placeholders": [...ordered unique Placeholders seen...]}` for the first tool in `tools` — the simplest contract that lets the Reinjector (Step 4) swap them.
- Mock Upstream `usage` token counts are a crude chars/4 estimate; the real fee math in Step 4 uses the real Upstream's `usage`.
- `.gitignore` added to keep `.env`, `.venv`, caches out of the repo (AGENTS rule 10).
- Environment: this machine has no Docker and cannot run WSL2/Docker Desktop (virtualization disabled in firmware); decision: user enables virtualization and installs Docker, then `docker compose up -d` runs this repo's compose file unchanged. `docker-compose.yml` itself already matches the PRD.
- Shell quirk: targeting `localhost` fails on this box through the system proxy; verified calls use `curl.exe --noproxy '*'` against `127.0.0.1` (uvicorn binds `0.0.0.0:9000`).

### Step 2: Proxy passthrough and wire tap

- New error codes for the OpenAI-shaped errors (PRD 7.4 names `aegis_*` codes): `aegis_invalid_request` (malformed 400), `aegis_upstream_timeout` (504), `aegis_upstream_unreachable` (502, connection refused etc. — not in the PRD table but must not 500), `aegis_upstream_error` (wrapped non-OpenAI Upstream error bodies). Types: `invalid_request_error` for 4xx, `api_error` for 5xx. Upstream bodies that are already OpenAI-shaped pass through verbatim (PRD 8: "pass status ... through").
- Pseudo-stream sends the content chunk (`delta` = role + content), a finish chunk (`delta` = {}), then `[DONE]`, reusing the Upstream completion's id/created/model. Tool-call `arguments` are not delta-chunked yet; the Reinjector step (Prompt 4) owns that wiring.
- For `stream:true` Upstream is called with `stream:false`; the body forced to `stream:false` is also what the Wire Tap records (it holds the exact bytes sent Upstream, PRD 2).
- The Wire Tap body is stored as JSON (semantic equality with the outbound bytes). It is written *before* the Upstream call so a Redis outage blocks fail-closed: 503 `aegis_state_unavailable`, nothing sent (PRD 8 row 2).
- All httpx clients are built with `trust_env=False`: this box's system proxy hijacks localhost traffic (see Step 1 curl note). The OpenAI SDK smoke passes `http_client=httpx2.AsyncClient(trust_env=False)` — official SDK v3 is built on the `httpx2` package, not `httpx` 0.28.
- Added deps: `openai` (official SDK, PRD 12.2) and dev `asgi-lifespan` (needed to run the app lifespan under `ASGITransport` tests);
- httpx `ASGITransport` does not enforce timeouts (verified in 0.28.1 source), so the timeout test uses a real `asyncio` blackhole server on an ephemeral port. Also: `Server.wait_closed()` hangs forever on Windows/CPython 3.12 even after `close()` — tests only call `close()`.
- Malformed-body 400s come from the FastAPI `RequestValidationError` handler, so they carry no `X-Aegis-*` headers; all other responses from the route carry `X-Aegis-Request-Id` and `X-Aegis-Overhead-Ms: 0`.
- `GET /v1/aegis/wiretap/{request_id}` returns the stored body JSON; unknown id → 404 `aegis_not_found`.
- `scripts/sdk_smoke.py` does not spawn servers; it preflights `/healthz` and mock `/_tap` and exits with the start commands if they are down.
