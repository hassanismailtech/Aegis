# Aegis

**Aegis is an OpenAI-compatible PII proxy for agents handling regulated Nigerian data.** It scrubs sensitive values before they reach an external Upstream, then reinjects them only in the response returned to the caller. The Wire Tap and live dashboard make the boundary observable.

## The problem

Banks, fintechs and hospitals want to use frontier-model agents, but sending BVNs, NINs, account numbers, phone numbers and names to offshore APIs creates NDPA 2023 cross-border-transfer exposure. Local models can be weaker, while a conventional proxy often does not understand tool calls or provide proof of what crossed the boundary.

## Core Loop

```text
 Agent / OpenAI SDK
          |
          v
 +-------------------+
 | Aegis Proxy       |
 | Scrubber          |  real PII -> Placeholders
 | Session Map       |  stable, reversible Redis state
 | Wire Tap          |  exact post-scrub request
 | Reinjector        |  Placeholders -> real PII in reply
 +---------+---------+
           |
           v
      External Upstream
      sees Placeholders only
```

Every request is handled as one session: messages, assistant tool-call arguments and tool results are scrubbed; Upstream receives the post-scrub body; the response is reinjected without exposing the Session Map. The dashboard displays counts, timings and Wire Tap output, never pre-scrub text.

## What is included now

- OpenAI-compatible `POST /v1/chat/completions`, including pseudo-streaming for `stream: true`.
- Nigerian-aware Scrubber layers: patterns, gazetteer and GLiNER PERSON detection.
- Redis-only Session Map with stable Placeholders and sliding TTL.
- Tool-call and tool-result handling, tolerant Reinjector, and fail-closed scrub/state errors.
- Redis-backed Telemetry Event stream, `/stats`, Wire Tap endpoint and synthetic seed endpoint.
- Dark, high-contrast single-page dashboard at `frontend/`.
- Offline mock Upstream, two-tool official SDK demo agent, leak test, recall evaluation and scrub benchmark.

## Quickstart

Requirements: Docker Desktop. The demo agent needs Python 3.12 and [`uv`](https://docs.astral.sh/uv/); the optional dashboard needs Node.js 20+ and npm.

### 1. Start the stack

From the repository root:

```powershell
docker compose up --build
```

This builds the backend image with CPU-only torch and the GLiNER model baked in, then starts:

- `redis` on `127.0.0.1:6379` — ephemeral, with snapshots and AOF disabled and no volume.
- `mock-upstream` on `127.0.0.1:9000` — the offline OpenAI-compatible Upstream.
- `aegis` on `127.0.0.1:8000` — the Proxy. Its healthcheck polls `/readyz`, which returns 200 only when Redis answers and, with `NER_ENABLED=true`, the NER model is warm.

No environment variables are required. The first build downloads the model; later starts reuse it from the image. Wait for `aegis` to report healthy (`docker compose ps`).

Check the running stack and print versions with:

```powershell
docker compose exec aegis aegis doctor
```

### 2. Run the demo agent

In another terminal:

```powershell
uv run --project backend python demo/agent.py
```

The demo prints two labeled panels. **AGENT SAW** contains the real customer values after reinjection. **UPSTREAM SAW** is loaded from the Wire Tap and contains Placeholders only.

### 3. Start the dashboard

The compose stack is backend-only. In another terminal:

```powershell
cd frontend
npm install
$env:NEXT_PUBLIC_AEGIS_URL = "http://127.0.0.1:8000"
npm run dev
```

Open `http://localhost:3000`. Select **Seed demo data** for an immediate synthetic view, or leave the dashboard open while the agent runs.

For a shared demo host, set the same optional access token in the repository-root `.env` used by compose and in the dashboard environment:

```dotenv
AEGIS_DEMO_TOKEN=change-this-demo-secret
NEXT_PUBLIC_AEGIS_TOKEN=change-this-demo-secret
```

The token protects chat, stats, events, Wire Tap and seed endpoints. Because a browser-native SSE connection cannot send an Authorization header, the dashboard exchanges the token for a 60-second signed ticket at `POST /v1/aegis/ticket` and puts only that ticket in the SSE query string. Use a private network or an authenticated gateway for real deployments.

### 4. Run the leak test

```powershell
cd backend
uv run pytest -q --report
```

The report writes `aegis:leaktest` in Redis so the dashboard can show the latest result. No test output or persisted telemetry contains the Session Map.

## Switching to a real Upstream

Copy `.env.example` to `.env` at the repository root and change only the Upstream settings:

```dotenv
UPSTREAM_BASE_URL=https://api.openai.com/v1
UPSTREAM_API_KEY=sk-...
UPSTREAM_MODEL_OVERRIDE=
```

Compose forwards those three values into the `aegis` service. The proxy forwards `UPSTREAM_API_KEY` when set; otherwise it forwards the caller's `Authorization` header. Never commit `.env`, API keys, or customer data. Keep the dashboard origin in `CORS_ORIGINS` and expose the proxy only behind your network's normal TLS and access controls.

## Validation

```powershell
cd backend
uv run pytest -q
uv run python scripts/eval_recall.py
uv run python scripts/bench_scrub.py

cd ..\frontend
npm run build
```

Recall and latency are measured, not promised. `eval_recall.py` reports per-type precision and recall on the checked-in labeled set; `bench_scrub.py` reports pattern and NER p50/p95 on the demo machine.

## Honest limitations

- Names are model-detected and recall is measured, not guaranteed; structured IDs are rule-detected.
- Deliberately obfuscated values such as leetspeak/spelled-out digits are not guaranteed to be detected; do not present the current Scrubber as an adversarial-evasion defense.
- True chunked streaming with a hold-back buffer is not implemented yet; `stream: true` uses a valid pseudo-stream after a non-streaming Upstream call.
- The mock Upstream is intentionally in-memory and is for offline demos, not production inference.
- Redis is ephemeral and there is no persistence, authentication, billing, user account or multi-tenant control plane.
- In-country deployment is a roadmap item, not a current compliance claim.
- The Wire Tap is retained for a short TTL and should be treated as sensitive operational data even though it contains only post-scrub text.

## Five answers

- **What problem?** Aegis reduces the risk of regulated Nigerian PII crossing to an external LLM while preserving agent quality.
- **Who is the user?** Tobi, a platform engineer, changes `base_url`, while Femi, a DPO, gets proof of what left the building.
- **What does it do now?** It scrubs chat and agent tool traffic, calls an OpenAI-compatible Upstream, reinjects responses, and shows live evidence.
- **What did we build in 24 hours?** A working proxy, Nigerian entity pack, Redis Session Map, Wire Tap, leak test, mock Upstream, SDK demo and dashboard.
- **What next?** Add true streaming hold-back, harden deployment controls, expand entity coverage and ship an in-country operating model.

## Architecture and security posture

Aegis is intentionally stateless at the process layer: Redis is the only Session Map and telemetry store, so horizontal proxy replicas share state without introducing a second database. Scrubbing and Session Map writes happen before the Upstream call; if either fails, the request is blocked. If state is lost after the call, the Reinjector leaves unknown Placeholders intact rather than guessing. Telemetry is best effort and contains counts, IDs and timings only.

The current repository does not implement authentication, authorization, rate limiting, TLS termination, secret rotation or tenant isolation. Those are deployment responsibilities and explicit product scope exclusions, not hidden guarantees. Run the service on a private network or behind an authenticated TLS gateway before connecting a real Upstream.

## License

See [LICENSE](./LICENSE).
