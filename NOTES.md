# Aegis notes

## ASSUMPTIONS

### Step 1: Contracts and state

- Added `backend/app/__init__.py` (not spelled out in PRD 10) so `app` imports reliably as a regular package under `uv run` and pytest.
- `frontend/` is intentionally not created now: PRD 10 marks it as `create-next-app` output (Step 5), and pre-existing files would break `create-next-app`.
- `pyproject.toml` adds `uvicorn` (required to actually run the FastAPI apps, incl. the mock Upstream on :9000) and dev deps `pytest-asyncio` (async tests), plus a `[tool.pytest.ini_options]` section (`asyncio_mode="auto"`, `pythonpath=["."]`, `testpaths=["tests"]`).
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

### Step 3: Scrubber

- Deps: pinned `transformers>=4.51.3,<5` (5.16.x breaks gliner_small-v2.1's DeBERTa slow-tokenizer conversion), added `tiktoken` and `protobuf` (both pulled in by the gliner/transformers stack on this uv resolution). GLiNER is loaded lazily inside `scrubber/ner.py` functions: a bare `import gliner` at module top costs ~70s in every fresh Python process, which slowed `uv run pytest` to a crawl for non-NER tests.
- Warm-failure policy: if the model cannot load, `warm_ner()` returns `None` and the Scrubber silently degrades to pattern + gazetteer (a NER outage must not brick the proxy at startup). A NER *timeout or error at request time* is different: it raises `ScrubError` → 503 `aegis_scrub_unavailable` (fail-closed, PRD 8).
- PRD 9 fallback is ACTIVE — measured numbers, this box has 4 logical cores: pattern+gazetteer on a 60-word prompt p50=0.17ms / p95=0.27ms; NER layer on leftovers p50=374.3ms / p95=438.6ms, well over the 250ms budget. The fallback (NER only on text left after pattern+gazetteer spans are blanked, chunks capped at 2000 chars, already-blank chunks skipped) is the prescribed mitigation; the remaining latency is GLiNER inference speed on CPU hardware, not code we can trim without dropping the model size.
- `torch.set_num_threads(min(4, os.cpu_count()))` is set inside `warm()`: with default oversubscription GLiNER p95 hits the 2000ms timeout cap (2-3x worse); pinning to the core count fixed it.
- Fixing NER threading exposed a second risk: 500-word prompts produce 2 chunks and cost p50≈2.6s, *over* the `NER_TIMEOUT_MS=2000` cap → such requests take the 503 at runtime. `scripts/bench_scrub.py` therefore reports NER timings uncapped (timeout enforcement is proxy runtime behavior, not a scrub-layer property). Larger `NER_TIMEOUT_MS` trades latency budget for availability.
- Threshold probed 0.5 → 0.8 on `demo/labeled_eval.jsonl`: recall stayed 100% while PERSON precision rose 52%→62% (fewer hallucinated people like "Aegis" scored 0.73). PRD's default `ner_threshold=0.5` is kept in config for fidelity, but 0.7 is the recommended production value (NLA drop).
- JSON tool-call arguments: the Scrubber has no separator info there, so argument *key names* are passed as label context (`f"{key} "` prefix) to `pattern_spans` — that is how `{"account_no": "0123456789"}` gets scrubbed despite NUBAN mid-line. Label regexes are underscore/hyphen tolerant (`nin`, `acct_n`, `a/c`, NUBAN variants). Arguments that are not valid JSON are scrubbed as plain text.
- Gazetteer rules: name sequences go up to 3 tokens; multi-word runs match case-insensitively, a single token must be Capitalized (avoids "Well"/"March" false hits).
- `Session` id resolution (PRD 2): `X-Aegis-Session`, else first 16 hex chars of sha256 of `Authorization`; with no auth header the empty string is hashed (one shared anonymous session per upstream).
- Tests: passthrough tests disable NER (`monkeypatch.setattr(settings, "ner_enabled", False)`) because GLiNER tags the product name "Aegis" itself as PERSON; `Lifespan(startup_timeout=300)` because model warm-up exceeds the 5s default; PII wiring test uses a unique `X-Aegis-Session: step3-wiring-pii` to isolate Redis placeholder numbering from prior runs' sessions (numbering is per-session stable).
- Both scripts do a `sys.path.insert` bootstrap of `backend/` so they run portably from any calling environment.
