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
