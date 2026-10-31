# Aegis notes

## ASSUMPTIONS

- Source code is Apache-2.0. CC BY 4.0 applies only to original prose and diagrams under `docs/`; code, configuration, and code blocks remain Apache-2.0.
- Public contact email addresses are intentionally omitted until the Aegis domain is secured. General reports use GitHub Issues; vulnerability reports use GitHub private security advisories. Synthetic email fixtures remain because they validate the Scrubber's EMAIL detection.

- The requested modernisation is a presentation pass over the existing marketing and dashboard information architecture. It introduces no routes, data contracts, third-party tracking, customer logos, or claims.
- The landing-page telemetry specimen is illustrative and intentionally contains only post-scrub Placeholders and bounded metadata. It does not represent a real customer request and cannot reveal pre-scrub text or Session Map contents.
- Motion is limited to decorative entry and telemetry-sweep treatment; `prefers-reduced-motion` disables it. Live telemetry itself is not animated as a performance or security signal.

### Font and CI hardening

- Both deployed Next.js applications use `next/font` with Geist Sans and Geist Mono. The self-referencing Tailwind font variables caused unreliable fallback selection, so the variables now point explicitly at the generated Geist CSS variables.
- The existing GitHub Actions workflows are the checks selected by the active `Protect main` ruleset. The marketing-site build and deterministic pattern benchmark are added to make the protected-branch policy cover every shipped interface and the named benchmark requirement.
- The current deployment URLs are `website-woad-six-53.vercel.app` for marketing and `aegis-liard-pi.vercel.app` for the dashboard. They are documented as the cross-link transition origins until custom product domains are assigned.

### Marketing site scaffold

- `website/` already contains the Next.js App Router, Tailwind, and the requested shadcn/ui `navigation-menu`, `button`, `sheet`, and `card` components, so this step extends that scaffold and adds no dependencies.
- The requested `/security` and `/compliance/ndpa` stubs remain as explicit launch aliases while the site blueprint’s longer-term Trust routes are added in later steps.
- The five route pages deliberately render no body content; their shared marketing layout renders the complete responsive navigation while page copy remains out of scope.

### Marketing landing page

- `DESIGN.md` forbids rendering pre-scrub text in any UI. The hero preserves the landing-copy Wire Tap labels and post-scrub example, but replaces the red pre-scrub example line with `[pre-scrub text stays in your network]`.
- The design-partner application is a prefilled `mailto:` draft because `LANDING_COPY.md` specifies the information to collect but does not provide a destination work email.

### Marketing architecture expansion

- `docs/SITE_ARCHITECTURE.md` is implemented as a data-driven marketing route tree so every documented non-blog route has a substantive page without duplicating route components.
- The organisation's legal name, address, applicable privacy contact, effective dates, general contact channel, processor list, and contract terms are not in the repository. Privacy, terms, DPA, cookie, contact, design-partner, and subprocessor pages therefore clearly remain in publication review rather than presenting invented or binding legal content.
- Public repository contact routes use GitHub Issues for general reports and GitHub private security advisories for vulnerability reports; `NEXT_PUBLIC_SITE_URL` overrides the sitemap, robots, and security.txt origin during deployment.
- The existing Vercel project is retained as the marketing project, with a separate future dashboard project (`aegis-app`) recommended in `docs/WEBSITE_APP_INTEGRATION.md`; no Vercel project, domain, or environment variable was changed by this implementation.

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

### Phase 0 task 3: structured logging

- `aegis.request` emits one compact JSON line per completed/blocked/upstream-error proxy request with request id, hashed Session id, status, HTTP status, entity counts and timings. It deliberately omits model text, message content, tool arguments, headers and Session Map values; auth rejections log only the fixed reason and status.
- The `aegis` logger is set to INFO for the test session by `conftest.py`, which attaches an in-memory capture handler. The final log test is moved to the end of collection, so it inspects every line produced by `test_no_leak`, `test_roundtrip` and the rest of the suite against all 35 planted values plus roundtrip PII and demo/key credentials. No log file or persistent store is added.
- Structured request logging is separate from Telemetry Events: logs are process-local operational output, while Telemetry remains the Redis-backed dashboard contract.

### Phase 0 task 4: short-lived SSE tickets

- `POST /v1/aegis/ticket` exchanges the existing demo/deployment token for a stateless HMAC-SHA256 ticket with a 60-second TTL (`v`, `iat`, `exp` claims). The ticket is signed, not encrypted, and contains no tenant id, Session id or request text.
- The signing secret is `AEGIS_TICKET_SECRET` when set, otherwise `AEGIS_DEMO_TOKEN`, otherwise an ephemeral random secret per process for local development. The ticket is therefore not portable across replicas unless a shared secret is configured.
- Ticket issuance uses the same `_authorized` guard as the dashboard's other operational endpoints, not the per-tenant chat keys. Per-tenant keys deliberately cannot mint tickets for the global Telemetry feed.
- The old `access_token` query parameter is removed from `_authorized`. SSE accepts either the demo token header or a valid `?ticket=`, and the ticket is accepted only by the SSE route; stats, Wire Tap and seed still require headers.
- The frontend requests a fresh ticket for every connect/reconnect attempt, so long-lived streams keep working and an expired ticket is never reused. Ticket values and the signing secret are never logged.

### Phase 1 task 1: Dockerfile and compose

- CPU-only torch is enforced in `pyproject.toml` by declaring `torch` as a direct dependency and pinning it to the explicit `pytorch-cpu` index. `uv lock --upgrade-package torch` then removed the Linux CUDA/NVIDIA/triton packages from `uv.lock`; the image never installs them.
- The image warms the configured GLiNER model during the build (`get_ner().warm()`), so the build fails if the model cannot load. Runtime sets `HF_HUB_OFFLINE=1` and `TRANSFORMERS_OFFLINE=1` so startup uses only the baked cache.
- `libgomp1` is the only extra runtime system package; the CPU torch wheel needs it. Healthchecks use the Python standard library instead of installing `curl`.
- `GET /readyz` is unauthenticated like `/healthz`; it pings Redis with a 2-second timeout and requires `app.state.ner.ready` when `NER_ENABLED=true`. `NER_ENABLED=false` makes the NER check pass by design.
- Compose builds both `aegis` and `mock-upstream` from the same backend image. The mock Upstream overrides the image healthcheck to poll its own `/_tap` endpoint on :9000; otherwise the image's `/readyz` healthcheck would target the wrong port.
- Compose fixes `REDIS_URL` to the `redis` service and interpolates only the optional Upstream and demo-token values from a repository-root `.env`. With no `.env`, all defaults still work. Redis and mock-upstream ports are published for host-side tests and debugging.
- The frontend is not a compose service (the task names only aegis, redis and mock-upstream); the README keeps the dashboard as a separate `npm run dev` step.
- `backend/Dockerfile` also has a `mock` target for the mock Upstream. It reuses the builder venv and scripts but skips the model bake, so a clean compose build downloads the GLiNER model once instead of once per service. The `mock` target has its own `/_tap` healthcheck; the `runtime` target keeps the required `/readyz` healthcheck.
- The builder uses a BuildKit cache mount for uv downloads. It does not cache the Hugging Face model across builds: the model cache must remain in the final image layer to be baked in.
- Docker Desktop is now available on this machine; the Step 1 note that it was unavailable is historical. The local verification used Docker Desktop's Linux engine.

### Phase 1 task 2: GHCR publish workflow

- `.github/workflows/publish.yml` builds the `runtime` target for `linux/amd64` and `linux/arm64` on pushes to `main`, `v*` tags and manual dispatch. It publishes `ghcr.io/<owner>/<repo>` with branch, tag, SHA and `latest` tags via `docker/metadata-action`.
- The workflow uses `GITHUB_TOKEN` with `packages: write`; no extra registry secret is required. It does not run tests (not part of this task) and publishes only the Proxy image, not the mock target.
- The 120-minute job timeout covers QEMU arm64 builds plus the build-time GLiNER warm-up. The PyTorch CPU index has a cp312 `manylinux_2_28_aarch64` wheel for the pinned torch version, so the arm64 build uses the same CPU-only resolution.

### Phase 1 task 3: aegis doctor CLI

- Added a `project.scripts` entry point `aegis = "app.cli:main"` and a Hatchling build backend so `uv run aegis doctor` works from the backend project. Hatchling is a build-time dependency only, MIT licensed; the Docker builder keeps `--no-install-project`, so the runtime image does not include Hatchling. The runtime image gets a small `/usr/local/bin/aegis` wrapper that runs `python -m app.cli`.
- The builder also builds the project wheel and copies only its `aegis-*.dist-info` into the runtime venv. This makes `aegis doctor` report the real Aegis version inside the image instead of `unknown`; the application code still runs from `/app`. The metadata layer sits after the model-bake layer, so changing the version does not re-download the model.
- `aegis doctor` checks Redis with a 3-second connect/read timeout, warms the GLiNER model off the event loop when `NER_ENABLED=true`, and probes the Upstream base URL with a 3-second `httpx` GET. Any HTTP response counts as reachable; the check is connectivity, not an inference call.
- Doctor prints Python, Aegis, FastAPI, Pydantic, redis-py, httpx, torch, transformers and GLiNER versions plus three `ok`/`FAIL` lines. It exits 1 if any check fails, 0 otherwise. `NER_ENABLED=false` reports the model as intentionally disabled and still exits 0.
- URLs are reduced to scheme/host/port/path before printing, so credentials embedded in `REDIS_URL` or `UPSTREAM_BASE_URL` never appear in terminal output. Exceptions are reduced to a generic status line; no request text, keys or headers are printed.
- Tests in `backend/tests/test_doctor.py` cover credential stripping, success and failure exit codes, the required subcommand and the disabled-NER path. The real Redis/model/Upstream checks are not exercised in unit tests to keep the suite offline and fast.

### Review hardening

- Literal inbound Placeholder-lookalikes are neutralized before Scrubber detection, preventing a caller from addressing another request's Session Map entry.
- Requests without an explicit session or Authorization now receive a unique anonymous session id; the demo continues to use its explicit session header for multi-turn stability.
- `AEGIS_DEMO_TOKEN` is optional to preserve local quickstart behavior; when set, it guards chat, stats, events, Wire Tap and seed routes. Browser SSE accepts the same token through its EventSource query because native EventSource cannot set headers.
- Pseudo-streaming now emits tool-call deltas and a `tool_calls` finish reason.
- Bare ten-digit local phone patterns require phone context; prefixed forms remain rule-detected.
- Latest benchmark: pattern p50/p95 is 0.18/0.68 ms for 60 words and 1.71/2.86 ms for 500 words; GLiNER p50/p95 is 428.6/1270.6 ms and 2651.3/3730.9 ms respectively. Deliberate leetspeak and spelled-out digit evasion remain an explicit limitation.

### Detector packs (Task 1)

- Detection now composes through `app.detectors.base.Detector`: an async `detect(text, prior)` layer returning `Span`s. `prior` is the spans found by earlier layers; pack detectors ignore it, and the GLiNER detector uses it to preserve the PRD 9 fallback (NER only on text left after pattern + gazetteer). Span moved to `app/detectors/base.py`.
- `DETECTOR_PACKS` is an ordered JSON list in config (default `["ng"]`, env example `DETECTOR_PACKS=["ng"]`). Each name maps to `backend/packs/<name>/__init__.py`, which must expose `detectors()`. Names are restricted to lowercase snake case before import; a bad name or missing pack fails at Scrubber import/startup rather than at request time. Pack detector instances are loaded once per process.
- The Nigerian pack holds the unchanged regex patterns (`packs/ng/patterns.py`) and gazetteer (`packs/ng/gazetteer.py`); no regex, context window or threshold was edited. `data/ng_names.json` stays at `backend/data/` per PRD 10.
- `app/scrubber/patterns.py` and `app/scrubber/gazetteer.py` are compatibility re-export shims so existing test imports (`pattern_spans`, `find_persons`, `Span`) and scripts keep working unchanged. The implementation no longer lives there.
- GLiNER remains `app/scrubber/ner.py` (not Nigeria-specific) and is appended after configured pack detectors; its `NER_ENABLED`, timeout, model and threshold behaviour is unchanged.
- Packaging follows the new module: the Hatchling wheel includes both `app` and `packs`, and both Dockerfile build stages copy `packs/`.

### Phase 2 task 2: NUBAN validator

- `packs/ng/validators.py` implements the CBN check digit over the 3-digit bank code plus the 9-digit serial, weights `3,7,3`, and `(10 - sum % 10) % 10`. It is pinned by the CBN worked example `011` + `000001457` -> `0000014579`.
- PRD section 6 said bare 10-digit numbers stay untouched; the Phase 2 spec changes that. A bare number is now redacted only when the 40-char window names a bank (or says "bank code 123") and that bank's code validates the checksum. Trying every known code would accept almost every 10-digit string (each code accepts about 10%; 30 codes accept about 96%), which would over-redact amounts and contradict the PRD's precision intent. The explicit `account`/`acct`/`a/c`/`NUBAN` label path still redacts without a checksum, preserving recall.
- The bank table is deliberately small and checked against the CBN 2010 circular / Interswitch codes: 044, 023, 050, 070, 011, 214, 058, 030, 301, 082, 303, 014, 107, 104, 076, 105, 101, 106, 221, 068, 232, 100, 102, 033, 032, 215, 035, 057, 063, 103. Codes and aliases go stale as banks merge; add them with a CBN/Interswitch source, not from memory.
- Tests: CBN known-good, known-bad checksum, wrong bank, malformed lengths, named-bank gating, spaced bare account, and the explicit-label fallback.

### Phase 2 task 3: held-out eval and CI floor

- `demo/heldout_eval.jsonl` has 220 synthetic sentences covering bank statements, KYC forms, chats, pidgin, Yoruba/Igbo/Hausa names, OCR-style spacing and negative examples. It is separate from `demo/labeled_eval.jsonl` (which was used to tune `NER_THRESHOLD`) and was not used to tune the detectors. It is not human-labelled: no independent human labeller was available in this session. Do not describe it as human-labelled in public text.
- `scripts/eval_heldout.py` reports per-type precision and recall with Wilson 95% confidence intervals, validates label offsets before running the model, and exits 1 when the configured type's recall is below `--floor` (default `EVAL_RECALL_FLOOR=0.85`). The default floor type is PERSON, i.e. the model layer. A scrub timeout is counted as a miss and reported, never retried.
- `.github/workflows/eval.yml` runs the floor on pushes to `main` and pull requests. CI sets `NER_TIMEOUT_MS=10000` because it measures model quality; latency stays with `bench_scrub.py`, where production's 2000 ms budget is reported separately.
- `docs/metrics.txt` is generated by `eval_heldout.py --output`; it contains counts and rates only, never sentence text.
- The held-out set is synthetic and small relative to production traffic; the confidence intervals show that uncertainty rather than hiding it.

### Phase 2 task 4: ONNX, skip and cache

- Added `onnx>=1.17` (Apache-2.0), `onnxruntime>=1.20` (MIT), and transitive `flatbuffers`/`ml-dtypes` (Apache-2.0). They are needed for the GLiNER ONNX export and int8 runtime; no proprietary dependency was added.
- `NER_RUNTIME` defaults to `torch` so the existing image and startup path are unchanged. Set `NER_RUNTIME=onnx` after `uv run python scripts/export_ner_onnx.py`; the exporter writes `model.onnx`, `model_quantized.onnx`, `gliner_config.json` and the tokenizer to `NER_ONNX_DIR` (default `backend/data/ner_onnx`, gitignored). The Docker image still bakes the torch model; ONNX artifacts are not baked because they are generated, large and machine-specific.
- The GLiNER exporter uses dynamic int8 quantization (`QUInt8` internally). Its held-out recall is measured before recommending it; speed is not traded for a silent recall drop.
- Skip gate: after pattern + gazetteer, a chunk with no 3+ letter ASCII word cannot contain a person name for this pack, so the model call is skipped. The gate is intentionally conservative (names shorter than three letters would be missed by NER, but the pack targets Nigerian names and the gazetteer still covers short names).
- Cache: SHA-256 of `threshold + NUL + chunk` is the key, values are span lists, TTL defaults to 300 s and the LRU is bounded at 512 entries. Raw text is never stored or logged; nothing is persisted. `find_persons(..., use_cache=False)` exists so the benchmark can measure the model rather than the cache.
- `bench_scrub.py` now reports cold model timings (cache bypassed), cache-hit timings for the same prompt, and a no-candidate skip probe. This keeps the headline latency honest instead of reporting 100 cache hits as model speed.
- Added tests for skip alignment, cache hits/disable, ONNX artifact selection and exporter kwargs.
- Measured `scripts/bench_scrub.py`, 100 runs per prompt, cold model (cache bypassed), on the demo laptop (Windows, 14.9 GB RAM). "Before" is the pre-change commit state; "after" is this branch:

  | prompt | layer | before | after (torch) | after (ONNX int8) |
  |---|---|---|---|---|
  | 60-word | pattern p50/p95 | 0.18 / 0.53 ms | 0.15 / 0.25 ms | 0.22 / 4.78 ms |
  | 60-word | NER p50/p95 | 370.8 / 639.9 ms | 439.2 / 734.2 ms | 350.0 / 878.8 ms |
  | 60-word | NER cache hit | n/a | 0.38 / 1.77 ms | 0.41 / 6.09 ms |
  | 500-word | pattern p50/p95 | 1.75 / 2.28 ms | 1.96 / 4.95 ms | 2.17 / 6.49 ms |
  | 500-word | NER p50/p95 | 4066.8 / 10723.5 ms | 4305.4 / 10476.9 ms | 3193.2 / 9273.8 ms |
  | 500-word | NER cache hit | n/a | 0.65 / 1.88 ms | 0.36 / 0.89 ms |
  | no-candidate probe | skip gate | n/a | 0.44 / 1.44 ms | 0.33 / 0.96 ms |

- Run-to-run variance on this box is large (the pattern p95, which does no model work, swung from 0.25 ms to 4.78 ms between runs). The honest reading: int8 ONNX is a modest p50 win for the cold model, not a step change, and the deterministic wins are the two fast paths — a cache hit and a skipped model call are both under 1.5 ms p95 versus hundreds of ms cold. PRD 9's fallback remains active for cold text: NER p95 is far over 250 ms, so the 2000 ms timeout is the production guard.
- Held-out quality with `NER_TIMEOUT_MS=10000`: torch PERSON recall 96.9% (95% CI 93.5-98.6), precision 61.9%; total recall 98.8%, precision 80.9%. ONNX int8 PERSON recall 94.9% (95% CI 90.9-97.2), precision 63.7%; total recall 98.0%, precision 82.2%. Both pass the 0.85 floor, so ONNX is a valid opt-in; torch stays the default and supplies `docs/metrics.txt`.
- `uv run pytest -q`: 133 passed, `leaks: 0 / 35 planted entities`. One earlier full-suite run hit the 2000 ms NER cap on two leak/telemetry requests (503, no leak); a rerun on the idle box passed. The timeout is deliberately fail-closed, so a loaded laptop can still turn a slow inference into a blocked request.

### Phase 3 task 1: Anthropic Messages route

- Added `POST /v1/messages` as a non-streaming route. `stream:true` returns an Anthropic-shaped 400 (`invalid_request_error`) because the task scopes this step to non-streaming; the PRD's pseudo-streaming contract is specified for `/v1/chat/completions` only.
- `app/anthropic_adapter.py` walks Anthropic blocks and delegates every detection/Placeholder decision to the Scrubber and every swap to the Reinjector. To make that reuse explicit, the Scrubber's text and JSON walkers are now public (`scrub_text`, `scrub_json_value`, renamed from private names) and the Reinjector gained `json_value()` for parsed JSON structures. No regex, numbering or matching logic was copied into the adapter.
- Scrubbed: `system` (string or list of text blocks), `messages[].content` strings, text blocks, `tool_use.input` (nested JSON string values), and `tool_result.content` (string or list of text blocks). Image/document/other blocks and tool definitions (`name`, `description`, `input_schema`) pass through untouched.
- Reinjected: response `content[].text` blocks and `content[].tool_use.input` recursively. `thinking` blocks are not rewritten; the task names text blocks and tool_use input, and thinking is model reasoning rather than the answer or tool payload.
- Aegis tenant auth stays `Authorization: Bearer` (same `require_tenant` dependency). The Anthropic SDK's `x-api-key` is forwarded Upstream only when tenant auth is off; with tenant auth on, the BYOK key comes from `X-Upstream-Api-Key` or `UPSTREAM_API_KEY`, mirroring `X-Upstream-Authorization` on the OpenAI route. This keeps an Aegis tenant key from being sent Upstream when an SDK client puts it in `api_key`.
- `UPSTREAM_API_KEY` is sent as raw `x-api-key` (a leading `Bearer ` is stripped). `anthropic-version` defaults to `2023-06-01`; the client's `anthropic-version` and `anthropic-beta` headers are forwarded.
- Anthropic `usage.input_tokens`/`output_tokens` are normalized to the existing `prompt_tokens`/`completion_tokens` shape before fee and Telemetry Event math. Telemetry, the Wire Tap key/TTL, and the four `X-Aegis-*` response headers are shared with the OpenAI route.
- Route-level 400/401/429/503 and upstream timeout/unreachable errors are Anthropic-shaped (`{"type":"error","error":{...}}`). The body-size middleware's 413 stays OpenAI-shaped because it rejects before routing (existing behaviour, outside this step).
- Added dev dependency `anthropic>=2.3.0` (Apache-2.0) for the official-SDK smoke test. Like `openai` 3.x it is built on `httpx2`, so the test supplies an `httpx2.ASGITransport`.
- Mock Upstream implements `/v1/messages` and shares Placeholder extraction, schema-field mapping and `/_tap` with `/v1/chat/completions`; usage remains a chars/4 estimate.
- Tests: `backend/tests/test_anthropic.py` covers the official SDK smoke, tool_use input scrub/reinject, tool_result string and list-block scrubbing, cross-tenant Session isolation with the same client header, adapter numbering, and Anthropic-shaped stream/malformed errors.

### Phase 3 tasks 2-3: true streaming and hold-back

- Supersedes Phase 3 task 1's `stream:true` 400: `/v1/chat/completions` and `/v1/messages` now call Upstream with `stream:true` and relay real SSE; the old non-streaming pseudo-stream is removed.
- `StreamingReinjector` (`app/reinjector.py`) keeps one hold-back buffer per content stream. It holds from any suffix that could still become a tolerant Placeholder (PRD 7.1), releases as soon as following text proves it cannot, and flushes unchanged at 40 held characters (`HOLDBACK_CHARS`) or at stream/block end. Held bytes are never dropped. This is a superset of the required unclosed `[[` rule: single-bracket tolerant forms also hold, and a complete Placeholder at the very end of a chunk waits for one more chunk so an extra `]` can still be consumed.
- A Placeholder longer than the 40-character cap is split and cannot resolve; it stays literal and counts as unresolved, consistent with the bounded-memory rule. Valid Placeholders are far shorter.
- OpenAI: one buffer per choice index and a separate one per `(choice, tool_call)` index, so `n > 1` works. Chunks preserve Upstream `id`/`model`/`created` and extra top-level fields; held content/tool-arguments chunks are emitted before the `finish_reason` chunk; `[DONE]` flushes any remaining tails first. Usage is captured from the final chunk for telemetry.
- Anthropic: one buffer per content-block index; `text_delta` and `input_json_delta` are rewritten separately and flushed before `content_block_stop`; `message_stop` flushes any block that never stopped. Non-text blocks (thinking, signatures, images) pass through untouched. Usage is captured from `message_start` (input) and `message_delta` (output); an upstream `error` event marks telemetry `upstream_error`.
- Streaming telemetry: `unresolved` is unknowable before response headers, so streaming responses omit `X-Aegis-Unresolved` and the final count is recorded in the Telemetry Event instead. `X-Aegis-Overhead-Ms` on a streaming response reports Scrub time only (reinject time is only known when the stream ends). `upstream_ms` is time to the first SSE event; `reinject_ms` includes the Session Map read plus all rewrite work.
- The Session Map is loaded before the Upstream stream is opened. A Redis error there degrades to an empty map: the stream still relays, every Placeholder stays literal, and telemetry ends as `state_loss`.
- A transport error after headers cannot change the HTTP status; the relay ends, and telemetry records `upstream_error`. Telemetry write failures remain best-effort.
- Mock Upstream now emits real SSE for both protocols. It deliberately splits the first Placeholder across three chunks in text and tool arguments (and Anthropic `input_json_delta`) so integration tests exercise split reinjection.
- Tests: `backend/tests/test_streaming.py` (24 tests) covers every tolerant PRD 7.1 form split at every character of the Placeholder and of the whole sentence, one-character-at-a-time streaming, unknown Placeholders, the 40-character cap, an earlier single `[` not stealing a Placeholder's closing bracket, OpenAI `n > 1`, and official-SDK Anthropic streaming for text and tool input. Existing OpenAI stream tests now reassemble split tool arguments instead of assuming one delta.

### Fix-First and Repo Hygiene (2026-10-28)

- `docker-compose.yml` binds published ports for Redis (6379), aegis (8000), and mock-upstream (9000) strictly to `127.0.0.1` to prevent exposure on external interfaces on public networks or VMs.
- Lifespan startup guard (`app/main.py`) checks `bind_host` and refuses to run on non-loopback addresses without `AEGIS_KEYS_FILE` unless `AEGIS_INSECURE_DEV=1` is explicitly set. Dedicated `AEGIS_TICKET_SECRET` is required whenever tenant auth is enabled (no fallback to demo token).
- Dashboard (`frontend/`) has all third-party analytics (`@vercel/analytics`, `@vercel/speed-insights`) removed per DESIGN.md privacy principles.
- Public claims in `README.md` aligned with `docs/CLAIMS.md` and `docs/metrics.txt` (reflecting true streaming, Anthropic adapter, and honest evaluation caveats).
- `backend/app/audit.py` provides an append-only, SHA-256 hash-chained verification log (`aegis audit verify`) for Telemetry Events stored in SQLite (`AUDIT_DB_PATH`). This is cryptographic compliance evidence logging, not proxy session state (which remains strictly in ephemeral Redis per AGENTS rule 8). All generated `*.db` files are gitignored.

### UI/UX pass (2026-10-28)

- The existing one-page dashboard remains the product surface; this pass improves hierarchy, status clarity and post-scrub inspection without adding routes, settings or new backend contracts.
- The dashboard displays the existing aggregate pipeline overhead as p50/p95 and does not invent separate rule/model latency fields that the current stats API does not expose.

### Site architecture blueprint (2026-10-28)

- Private inputs live under `private/` (`WEBSITE_DOCS_ACCESS_PLAN.md`, `STRATEGY.md`, `LANDING_COPY.md`); `docs/SITE_ARCHITECTURE.md` + `docs/nav.json` now incorporate them. Keep `private/` gitignored; do not paste strategy competitive content into public docs beyond IA structure.
- Launch chrome may stay the slim `LANDING_COPY` nav; mega-menu is the venture-scale expansion.
- Cloud lanes are roadmap only; Managed Nodes must be Nigeria-hosted or customer-VPC (never an offshore raw-PII hosted proxy).
- Trust framework pages remain claim-safe primers; footer columns follow WEBSITE plan (Product / Community / Support / Company).
- Docs target: Docusaurus `docs-site/` on `docs.<domain>`; Playground = no-login synthetic scrub API.
- `GITHUB_URL` / Status URL placeholders in `nav.json` are build-time substitutions.
