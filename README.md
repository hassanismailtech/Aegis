# Aegis

> An inspectable data boundary for AI agents handling Nigerian identifiers.

Aegis is an OpenAI- and Anthropic-compatible Proxy. Its Scrubber replaces detected sensitive values with session-stable Placeholders before a request reaches an external Upstream, and its Reinjector restores known values only in the response returned to the caller. Wire Tap and telemetry make the post-scrub boundary reviewable. Aegis reduces leakage exposure; it does not guarantee perfect detection or make a transfer lawful.

[![CI](https://github.com/hassanismailtech/Aegis/actions/workflows/ci.yml/badge.svg)](https://github.com/hassanismailtech/Aegis/actions/workflows/ci.yml)
[![Evaluation](https://github.com/hassanismailtech/Aegis/actions/workflows/eval.yml/badge.svg)](https://github.com/hassanismailtech/Aegis/actions/workflows/eval.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Python 3.12+](https://img.shields.io/badge/Python-3.12%2B-3776AB?logo=python&logoColor=white)](backend/pyproject.toml)
[![Next.js 16](https://img.shields.io/badge/Next.js-16-000000?logo=next.js)](frontend/package.json)

## Table of contents

- [Key features](#key-features)
- [Architecture and system design](#architecture-and-system-design)
- [Getting started](#getting-started)
- [Configuration and environment variables](#configuration-and-environment-variables)
- [Local development and scripts](#local-development-and-scripts)
- [Deployment and production build](#deployment-and-production-build)
- [API documentation and usage examples](#api-documentation-and-usage-examples)
- [Testing suite](#testing-suite)
- [Contributing](#contributing)
- [Security and performance](#security-and-performance)
- [License and authors](#license-and-authors)

## Key features

- OpenAI-compatible <code>POST /v1/chat/completions</code> and Anthropic-compatible <code>POST /v1/messages</code>, with tool calls, tool results, and streaming.
- Nigerian-aware Scrubber layers for phone numbers, BVNs, NINs, account numbers, email addresses, and PERSON entities through patterns, gazetteer matching, and GLiNER.
- Redis-backed Session Map for stable Placeholder numbering during the configured TTL. The supplied Compose stack disables Redis snapshots, AOF, and volumes.
- Fail-closed pre-Upstream handling: a Scrubber or Session Map failure blocks the request. Reinjector state loss leaves unresolved Placeholders intact.
- Wire Tap records exactly what Upstream received after scrubbing; telemetry carries safe counts, IDs, timings, and status, never pre-scrub text or Session Map contents.
- Optional tenant API keys, request limits, rate limits, and signed dashboard tickets. Authentication is off unless <code>AEGIS_KEYS_FILE</code> is configured.
- Separate Next.js dashboard and marketing applications, both using App Router, TypeScript, Tailwind CSS, shadcn/ui, and deterministic Geist Sans/Geist Mono font variables.
- Offline mock Upstream, official SDK smoke tests, no-leak tests, held-out synthetic evaluation, and a deterministic Scrubber benchmark.

## Architecture and system design

~~~mermaid
flowchart LR
    A[Agent or application] --> B[Aegis Proxy]
    B --> C[Scrubber]
    C --> D[Redis Session Map]
    C --> E[External Upstream]
    E --> F[Reinjector]
    D --> F
    F --> A
    C --> G[Wire Tap and telemetry: post-scrub only]
~~~

The Proxy scrubs messages, assistant tool-call arguments, and tool results before the Upstream call. The Session Map temporarily associates each Placeholder with its original value for the current session. The Reinjector uses that Session Map after the response. If state is unavailable before the call, Aegis blocks; if it is unavailable during reinjection, Aegis returns unresolved Placeholders rather than guessing.

~~~text
backend/       FastAPI Proxy, Scrubber, Reinjector, Redis integration, tests, scripts
frontend/      Operational dashboard (Next.js)
website/       Marketing and trust site (Next.js)
demo/          Synthetic SDK demo inputs
docs/          Requirements, claims register, metrics, and operating guides
.github/       Pull-request template, code ownership, CI, evaluation, and publish workflows
~~~

## Getting started

### Prerequisites

| Tool | Required version | Purpose |
| --- | --- | --- |
| Git | Current stable | Clone the repository and create signed commits. |
| Python | 3.12 or later | Run the Proxy, scripts, and tests. |
| uv | Current stable | Resolve and run the Python workspace. |
| Docker Desktop | Current stable, Compose v2 | Start Redis, the mock Upstream, and the Proxy locally. |
| Node.js | 20 or later | Run the dashboard and marketing applications. |
| npm | Bundled with Node.js | Install and build each Next.js app. |

### Installation

Clone the repository and create a local environment file. Never commit <code>.env</code> or put real personal data in it.

~~~bash
git clone https://github.com/hassanismailtech/Aegis.git
cd Aegis
cp .env.example .env
uv sync --project backend
npm --prefix frontend ci
npm --prefix website ci
~~~

PowerShell equivalent for the environment file:

~~~powershell
Copy-Item .env.example .env
~~~

Start the complete local demo stack:

~~~bash
docker compose up --build
~~~

Local endpoints are <code>http://127.0.0.1:8000</code> for Aegis, <code>http://127.0.0.1:9000</code> for the mock Upstream, and <code>127.0.0.1:6379</code> for Redis. Confirm readiness without exposing request data:

~~~bash
curl http://127.0.0.1:8000/readyz
~~~

In separate terminals, start the dashboard and marketing site:

~~~bash
npm --prefix frontend run dev
npm --prefix website run dev
~~~

Set <code>NEXT_PUBLIC_AEGIS_URL=http://127.0.0.1:8000</code> for a separately deployed dashboard. Set <code>NEXT_PUBLIC_MARKETING_URL</code> in the dashboard and <code>NEXT_PUBLIC_APP_URL</code> in the marketing site to provide a seamless cross-application handoff.

## Configuration and environment variables

All Proxy settings are read by <code>backend/app/config.py</code> from the repository-root <code>.env</code> file. Defaults are repository defaults, not production recommendations.

| Variable | Type | Default | Required | Description |
| --- | --- | --- | --- | --- |
| <code>UPSTREAM_BASE_URL</code> | URL | <code>http://localhost:9000/v1</code> | Yes | Base URL for the compatible Upstream. |
| <code>UPSTREAM_API_KEY</code> | secret string | empty | No | Used instead of forwarding the caller Authorization header. |
| <code>UPSTREAM_MODEL_OVERRIDE</code> | string | empty | No | Model name to force for Upstream requests. |
| <code>REDIS_URL</code> | URL | <code>redis://localhost:6379/0</code> | Yes | Redis connection for Session Map and telemetry. |
| <code>SESSION_TTL_SECONDS</code> | integer | <code>300</code> | No | Sliding Session Map expiration. |
| <code>NER_ENABLED</code> | boolean | <code>true</code> | No | Enables the local GLiNER PERSON detector. |
| <code>NER_MODEL</code> | string | <code>urchade/gliner_small-v2.1</code> | No | GLiNER model identifier. |
| <code>NER_THRESHOLD</code> | float | <code>0.5</code> | No | PERSON detection threshold. |
| <code>NER_TIMEOUT_MS</code> | integer | <code>2000</code> | No | Model-detection timeout before a request is blocked. |
| <code>NER_RUNTIME</code> | enum | <code>torch</code> | No | <code>torch</code> or opt-in <code>onnx</code>. |
| <code>NER_ONNX_DIR</code> / <code>NER_ONNX_FILE</code> | path / string | model path | No | ONNX model location. |
| <code>NER_CACHE_TTL_SECONDS</code> / <code>NER_CACHE_MAX_ENTRIES</code> | integer | <code>300</code> / <code>512</code> | No | In-memory detector cache; TTL <code>0</code> disables it. |
| <code>EVAL_RECALL_FLOOR</code> | float | <code>0.85</code> | No | Minimum PERSON recall floor for held-out evaluation. |
| <code>FEE_USD_PER_1K_TOKENS</code> | float | <code>0.001</code> | No | Fee metadata rate for telemetry. |
| <code>CORS_ORIGINS</code> | URL string | <code>http://localhost:3000</code> | No | Allowed dashboard origin. |
| <code>DETECTOR_PACKS</code> | JSON array | <code>["ng"]</code> | No | Ordered detector packs to load. |
| <code>AEGIS_DEMO_TOKEN</code> | secret string | empty | No | Optional shared guard for demo/deployment endpoints. |
| <code>AEGIS_KEYS_FILE</code> | path | empty | No | Enables tenant API-key authentication when supplied. |
| <code>AEGIS_TICKET_SECRET</code> | secret string | empty | No | HMAC key for dashboard SSE tickets; defaults to demo token. |
| <code>AEGIS_INSECURE_DEV</code> | boolean | <code>false</code> | No | Development-only non-loopback startup override without keys. |
| <code>BIND_HOST</code> | IP or hostname | <code>0.0.0.0</code> | No | Proxy bind host. |
| <code>MAX_BODY_BYTES</code> / <code>MAX_MESSAGES</code> | integer | <code>1048576</code> / <code>200</code> | No | Request size and message-count limits. |
| <code>RATE_LIMIT_CAPACITY</code> / <code>RATE_LIMIT_REFILL_PER_SECOND</code> | integer / float | <code>60</code> / <code>1.0</code> | No | Token-bucket settings when tenant keys are configured. |
| <code>AUDIT_DB_PATH</code> | path | <code>data/audit.db</code> | No | Local path for the optional append-only audit log. |
| <code>NEXT_PUBLIC_AEGIS_URL</code> | URL | local Proxy URL | Dashboard only | Browser-visible Proxy base URL. |
| <code>NEXT_PUBLIC_AEGIS_TOKEN</code> | secret string | empty | Dashboard only | Optional dashboard demo token. |
| <code>NEXT_PUBLIC_MARKETING_URL</code> | URL | empty | Dashboard only | Marketing origin. |
| <code>NEXT_PUBLIC_APP_URL</code> | URL | empty | Marketing site only | Dashboard origin. |

## Local development and scripts

| Task | Command | Notes |
| --- | --- | --- |
| Start services | <code>docker compose up --build</code> | Ephemeral Redis plus local mock Upstream. |
| Proxy tests | <code>uv run --directory backend pytest -q</code> | Includes unit, integration, and leak tests. |
| Held-out evaluation | <code>uv run --directory backend python scripts/eval_heldout.py --floor 0.85</code> | Synthetic project-authored set. |
| Scrubber benchmark | <code>uv run --directory backend python scripts/bench_scrub.py</code> | Measured p50/p95, not a guarantee. |
| OpenAI SDK smoke test | <code>uv run --directory backend python scripts/sdk_smoke.py</code> | Requires the local stack. |
| Dashboard development | <code>npm --prefix frontend run dev</code> | Operational dashboard. |
| Dashboard lint and build | <code>npm --prefix frontend run lint</code>, <code>npm --prefix frontend run build</code> | Quality gates. |
| Marketing development | <code>npm --prefix website run dev</code> | Marketing site. |
| Marketing lint and build | <code>npm --prefix website run lint</code>, <code>npm --prefix website run build</code> | Quality gates. |

## Deployment and production build

Build the Proxy runtime image:

~~~bash
docker build --target runtime --tag aegis:local backend
docker run --rm --publish 8000:8000 --env-file .env aegis:local
~~~

Or use the reproducible local deployment:

~~~bash
docker compose up --build --detach
docker compose ps
~~~

Before connecting a real Upstream, provide <code>UPSTREAM_BASE_URL</code>, provide an <code>UPSTREAM_API_KEY</code> or pass a caller Authorization header, set <code>AEGIS_KEYS_FILE</code> when authentication is required, use TLS and an authenticated network boundary, and never expose Redis directly.

The dashboard and marketing site are independently deployable Next.js applications. Configure <code>NEXT_PUBLIC_MARKETING_URL</code> and <code>NEXT_PUBLIC_APP_URL</code> to connect the two deployments; shared Tailwind design tokens and explicit Geist font variables preserve a consistent handoff. The <code>ci</code> workflow builds both applications on every Pull Request and on <code>main</code>.

## API documentation and usage examples

### Health and readiness

~~~bash
curl http://127.0.0.1:8000/healthz
curl http://127.0.0.1:8000/readyz
~~~

### OpenAI-compatible chat completion

Use synthetic, non-sensitive content when testing. Set the client base URL to Aegis; the SDK request shape remains standard.

~~~python
from openai import OpenAI

client = OpenAI(
    base_url="http://127.0.0.1:8000/v1",
    api_key="local-development-key",
)

completion = client.chat.completions.create(
    model="gpt-5-mini",
    messages=[{"role": "user", "content": "Summarise this synthetic test note."}],
)

print(completion.choices[0].message.content)
~~~

| Endpoint | Method | Purpose |
| --- | --- | --- |
| <code>/healthz</code> | <code>GET</code> | Process health. |
| <code>/readyz</code> | <code>GET</code> | Readiness, including Redis and detector warm-up state. |
| <code>/v1/chat/completions</code> | <code>POST</code> | OpenAI-compatible chat completion path. |
| <code>/v1/messages</code> | <code>POST</code> | Anthropic-compatible Messages path. |
| <code>/v1/aegis/wiretap/{request_id}</code> | <code>GET</code> | Post-scrub Wire Tap record. |
| <code>/v1/aegis/events</code> | <code>GET</code> | Server-sent telemetry events. |
| <code>/v1/aegis/stats</code> | <code>GET</code> | Aggregate safe telemetry. |
| <code>/v1/aegis/ticket</code> | <code>POST</code> | Short-lived dashboard SSE ticket. |
| <code>/v1/aegis/_seed</code> | <code>POST</code> | Seeds synthetic dashboard telemetry. |

Do not expose Wire Tap, events, stats, ticket, or seed routes publicly without an authenticated boundary. They are operational interfaces and must never be used to handle real personal data in public demonstrations.

## Testing suite

~~~bash
uv run --directory backend pytest -q
uv run --directory backend python scripts/eval_heldout.py --floor 0.85
NER_ENABLED=false uv run --directory backend python scripts/bench_scrub.py
npm --prefix frontend run lint && npm --prefix frontend run build
npm --prefix website run lint && npm --prefix website run build
~~~

The no-leak tests assert that the project’s synthetic planted values do not appear in the Wire Tap. The held-out evaluator reports precision and recall for a 220-sentence synthetic, project-authored set; its current floor is PERSON recall <code>0.85</code>. Coverage reporting is not currently configured; required branch checks are test results, the pattern benchmark, held-out evaluation, web builds, dependency audits, and secret scanning.

## Contributing

Read [CONTRIBUTING.md](CONTRIBUTING.md), [SECURITY.md](SECURITY.md), and [docs/CLAIMS.md](docs/CLAIMS.md) before opening a change.

- Work from a short-lived <code>feat/</code>, <code>fix/</code>, <code>docs/</code>, or <code>chore/</code> branch.
- Use Conventional Commits and sign every commit: <code>git commit -s -m "feat(proxy): add safe behaviour"</code>.
- Keep tests, claim updates, dependency licence checks, and documentation in the same Pull Request as the implementation.
- Never add real personal data to tests, fixtures, screenshots, issues, or Pull Requests.

### Pull Request Process

Direct pushes to main are blocked. All changes must be submitted via Pull Request. Automated status checks (pytest, pattern benchmarks, and leak tests) must pass before merging.

The active <code>Protect main</code> ruleset also blocks deletions and force-pushes. Do not bypass failed checks; request code-owner review and merge only after required <code>ci</code> and <code>eval</code> checks succeed.

## Security and performance

Security reports belong in GitHub private security advisories or at <code>security@aegisproxy.dev</code>; use synthetic reproduction data only. See [SECURITY.md](SECURITY.md) for scope and disclosure guidance.

Aegis enforces strict branch protection rules. The default branch requires passing CI/CD status checks and blocks force-pushes to maintain an immutable audit log of all source code changes.

The process layer uses temporary Redis state and the supplied Compose configuration disables Redis persistence. Aegis measures detector behaviour rather than promising latency. On the project’s development laptop, the rule layer measured roughly p50 <code>0.15–0.22 ms</code> for a 60-word prompt; model results depend on workload, runtime, hardware, and cache state. Review [docs/metrics.txt](docs/metrics.txt) and [docs/CLAIMS.md](docs/CLAIMS.md) before publishing performance or quality claims.

## License and authors

Aegis is released under the [MIT License](LICENSE). Copyright © 2026 Hassan Ismail. Maintained by Hassan Ismail and contributors.
