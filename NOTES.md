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

### Step 4: Reinjector and Telemetry

- Reinjector regex: `\[\[? ?(?P<type>[A-Za-z_]+)_(?P<n>\d+) ?\]\]?` — open/close bracket depth and inner padding are independent (`[PERSON_1]`, `[[ PERSON_1 ]]`, `[ PERSON_1 ]`, `[[PERSON_1]` all tolerate); the type backtracks so `ACCOUNT_NO_1` still resolves; `[[PERSON_1]]'s` and `**[[PERSON_1]]**` matched by prefix. Missing-from-map matches stay as-is and each occurrence increments `unresolved` (`[[PERSON_9]]`, a type not in the Map, etc.); `[1]` never matches (no type letters before `_`).
- `unresolved` counts failed swap *occurrences* (content + tool-call argument strings), not distinct Placeholders — the simplest honest reading of PRD 5.4/7.1 counting "X-Aegis-Unresolved: n".
- Tool-call `arguments` reinjection is raw-string regex replacement with the session value run through `json.dumps(value)[1:-1]` (JSON-escape without the outer quotes) — matches PRD 5.4's "JSON-escape the replacement inside the arguments string" and keeps the string parseable as JSON; it also works when arguments are not strict JSON (the Scrubber treats those as plain text and may still plant Placeholders in them).
- Redis outage *at* reinjection (after the Upstream call already happened) is not in the PRD table; chosen policy: treat the Session Map as empty → all Placeholders unresolved → `state_loss`, HTTP stays 200, no PII guessed or leaked. Failure to record telemetry is silent (best-effort) and never changes the client response.
- `forward_map()` (HGETALL of the fwd hash, one call per response) also refreshes the sliding TTL of all three session keys, mirroring `resolve()`.
- `record()` puts XADD + PUBLISH + HINCRBY + RPUSH/LTRIM in one MULTI pipeline; `fee_micro_usd` stores micro-USD HINCRBY (integer) to avoid float accumulation; overhead list is LTRIMmed to the last 500 entries.
- Redis-py 8.1 note (verified in source): the first `get_message` after `subscribe()` consumes the (dropped) subscribe ack, so consumers poll `get_message` in a loop; a push arrives with OS-level urgency during a timed wait. SSE heartbeats are emitted whenever `get_message(timeout=HEARTBEAT_SECONDS)` comes back empty.
- Telemetry Event shape: all six entity types always present (PRD 7.3 example), ms fields rounded to 1 decimal, `overhead_ms` computed from the *rounded* scrub+reinject so header/event/list agree exactly; `fee_usd` (tokens/1000 × FEE rate) rounded to 6 decimals. `ts` is UTC `%Y-%m-%dT%H:%M:%SZ`.
- Stats endpoint shape (PRD does not pin it; flat, dashboard-friendly): `requests`, `entities_total`, `entities` (6 types), `state_loss`, `overhead_ms_p50`, `overhead_ms_p95`, `fee_usd`, using nearest-rank percentiles over the last 500 overhead values. 503 `aegis_state_unavailable` when Redis is down (PRD 8 row 2).
- `/v1/aegis/_seed` loops 20 synthetic events through the same `record()` path (so stats/stream/stream-list see them exactly like real traffic); deterministic profiles × 4, sessions `seed-00..19`, all `ok`, zero real text.
- Scrub-blocked requests (ScrubError and Redis-down both, PRD 8 event status) also emit a Telemetry Event (`scrub_blocked`, measured scrub_ms, zero-filled rest) — malformed 400s stay unlogged ("not logged" row has no request body to measure).
- Bugfix vs an earlier draft: `_blocked` previously sent the error *code* as the message too; now message is human-readable ("Scrubber failed; request blocked fail-closed." / "Redis unavailable; request blocked fail-closed.") and the code stays `aegis_*`.
- Leak-test line `leaks: 0 / N planted entities` prints in-test and is echoed under plain `pytest -q` via a small `pytest_terminal_summary` hook in a new `backend/conftest.py` (`Config` attribute handoff — pytest hides prints of passing tests otherwise).
- Tests using the mock Upstream route but asserting *exact* reinjected values (tool arguments, multi-turn numbering) monkeypatch `settings.ner_enabled=False` like the Step-3 tests: gazetteer + patterns are deterministic, GLiNER is not (it sometimes tags stray words as PERSON).
- Environment note: `docker ps` shows `aegis-redis-1` on :6379, so all telemetry/failure-policy tests exercise the real Redis instance.

### Step 5: Dashboard, demo and public documentation

- The dashboard is a single client page with four focused components; it consumes only Telemetry Events, aggregate stats and post-scrub Wire Tap bodies. It does not replay historical events because the SSE route is live-only; the seed endpoint provides the intentional empty-state population path.
- The dashboard refreshes aggregate stats every five seconds and applies incoming SSE events immediately so the top bar remains useful during an active demo.
- Wire View renders message content from the Wire Tap because that endpoint is explicitly post-scrub; it does not render the original client transcript.
- README commands use `127.0.0.1` for local backend calls to avoid host proxy behavior observed on this Windows machine; the browser-facing URL remains `localhost:3000`.
- README documents the current security boundary and intentionally excluded controls (authentication, TLS termination, rate limiting and tenant isolation) rather than presenting the prototype as production-compliant.

### Phase 0 task 1: per-tenant API key auth

- This task intentionally supersedes PRD section 4's auth exclusion: tenants and hashed keys now load from `AEGIS_KEYS_FILE`, and chat requires `Authorization: Bearer <aegis-key>` when it is set.
- Keys file format is the requested JSON list of `{tenant_id, key_sha256}`. Hashes must be 64 hex characters (case-insensitive); duplicate hashes may share a tenant for rotation, but one hash cannot belong to two tenants. A set-but-unreadable/invalid file aborts startup rather than silently disabling auth; an empty list is valid and rejects every key (fail-closed). The file is read once in the lifespan, not per request.
- When `AEGIS_KEYS_FILE` is unset, auth is disabled to preserve the local quickstart and `aegis.auth` logs a startup warning. The warning contains no keys, hashes or request data.
- Session id is `sha256(tenant_id + (X-Aegis-Session or random uuid))[:16]`, per the task, so the same client header under two tenants yields different Redis Session Maps. This replaces the old raw-header / sha256(Authorization) / `anon-` fallbacks. With auth disabled the tenant component is the empty string, so local sessions stay stable when a client sends a header and are per-request when it does not.
- `AEGIS_DEMO_TOKEN` remains the optional guard for operational routes. On chat it is still enforced in local-dev mode (no keys file) to preserve existing behaviour, but a valid tenant key replaces it when per-tenant auth is active.
- The tenant key is an Aegis credential, so when auth is active it is not forwarded Upstream: `UPSTREAM_API_KEY` or a separate `X-Upstream-Authorization` header supplies the Upstream credential. When auth is disabled, the old Authorization passthrough is unchanged.
- Auth failures return HTTP 401 with `WWW-Authenticate: Bearer` and the existing OpenAI-shaped `aegis_unauthorized` error.

### Phase 0 task 2: request limits and rate limiting

- Limits are configurable through `MAX_BODY_BYTES` (default 1 MiB), `MAX_MESSAGES` (default 200), `RATE_LIMIT_CAPACITY` (default 60-token burst) and `RATE_LIMIT_REFILL_PER_SECOND` (default 1 token/s).
- Body size is enforced in ASGI middleware before FastAPI parses the body, including chunked bodies; the response is 413 `aegis_request_too_large` in the OpenAI error shape. The middleware buffers only up to the configured limit and replays a bounded body to the app, preserving SSE disconnect detection.
- Too many messages returns 400 `aegis_too_many_messages` rather than 413, because the body itself may be within the byte limit. Message-count rejection happens before a rate-limit token is spent.
- Rate limiting is a Redis token bucket keyed by a SHA-256 of the tenant id, so one tenant's bucket cannot collide with another's or expose the raw id in a Redis key. The Lua script uses Redis TIME, refills lazily and sets a TTL long enough to refill the bucket. Local-dev mode has no tenant, so it skips rate limiting to preserve the quickstart behaviour.
- A Redis failure during rate limiting fails closed with the existing 503 `aegis_state_unavailable` path. A denied request returns 429 `aegis_rate_limited` (`rate_limit_error`) with `Retry-After`; allowed tenant requests expose `X-RateLimit-Limit` and `X-RateLimit-Remaining`.
- The body-limit middleware is added before CORS in application setup so CORS remains the outermost middleware and can decorate 413 responses for browser clients.

### Review hardening

- Literal inbound Placeholder-lookalikes are neutralized before Scrubber detection, preventing a caller from addressing another request's Session Map entry.
- Requests without an explicit session or Authorization now receive a unique anonymous session id; the demo continues to use its explicit session header for multi-turn stability.
- `AEGIS_DEMO_TOKEN` is optional to preserve local quickstart behavior; when set, it guards chat, stats, events, Wire Tap and seed routes. Browser SSE accepts the same token through its EventSource query because native EventSource cannot set headers.
- Pseudo-streaming now emits tool-call deltas and a `tool_calls` finish reason.
- Bare ten-digit local phone patterns require phone context; prefixed forms remain rule-detected.
- Latest benchmark: pattern p50/p95 is 0.18/0.68 ms for 60 words and 1.71/2.86 ms for 500 words; GLiNER p50/p95 is 428.6/1270.6 ms and 2651.3/3730.9 ms respectively. Deliberate leetspeak and spelled-out digit evasion remain an explicit limitation.
