# Seclume

Formerly Aegis. The public name is Seclume; existing `AEGIS_*` settings, `X-Aegis-*` headers, the `aegis` CLI/package, Redis prefixes and local image default remain unchanged.

> An inspectable data boundary for AI agents handling Nigerian identifiers.

Seclume is an OpenAI- and Anthropic-compatible Proxy. Its Scrubber replaces detected sensitive values with session-stable Placeholders before a request reaches an external Upstream, and its Reinjector restores known values only in the response returned to the caller. Wire Tap and telemetry make the post-scrub boundary reviewable. Seclume reduces leakage exposure; detection has limits, and Seclume does not make a transfer lawful.

## Visit the public website

[Visit Seclume on the web →](https://seclume.tech)

[![CI](https://github.com/hassanismailtech/seclume/actions/workflows/ci.yml/badge.svg)](https://github.com/hassanismailtech/seclume/actions/workflows/ci.yml)
[![Evaluation](https://github.com/hassanismailtech/seclume/actions/workflows/eval.yml/badge.svg)](https://github.com/hassanismailtech/seclume/actions/workflows/eval.yml)
[![License: Apache--2.0](https://img.shields.io/badge/License-Apache--2.0-blue.svg)](LICENSE)
[![Python 3.12+](https://img.shields.io/badge/Python-3.12%2B-3776AB?logo=python&logoColor=white)](backend/pyproject.toml)
[![Next.js 16](https://img.shields.io/badge/Next.js-16-000000?logo=next.js)](frontend/package.json)

## Table of contents

- [Key features](#key-features)
- [Current scope](#current-scope)
- [Architecture and system design](#architecture-and-system-design)
- [Getting started](#getting-started)
- [Local playground](#local-playground)
- [Operating guides](#operating-guides)
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
- Fail-closed pre-Upstream handling: a Scrubber or required Session Map write failure blocks the request. Reinjector state loss leaves unresolved Placeholders intact.
- Wire Tap records exactly what Upstream received after scrubbing; telemetry carries safe counts, IDs, timings, and status, never pre-scrub text or Session Map contents.
- Optional tenant API keys, request limits, rate limits, and signed dashboard tickets. Authentication is off unless <code>AEGIS_KEYS_FILE</code> is configured.
- Opt-in synthetic playground API and page: scrubbed output, entity counts, measured scrub time, actual full/lite mode, and a simulated reply. No Upstream call, restored values or Telemetry Events.
- Separate Next.js dashboard and marketing applications, both using App Router, TypeScript, Tailwind CSS, shadcn/ui, and deterministic Geist Sans/Geist Mono font variables.
- Offline mock Upstream, official SDK smoke tests, no-leak tests, synthetic project-authored evaluation, and a deterministic Scrubber benchmark.

## Current scope

The self-hosted Proxy and dashboard are implemented. The playground API and page are implemented but require explicit backend and browser configuration; a working marketing site alone does not establish a working public API. Use synthetic inputs only.

The planned release remains [Unreleased](CHANGELOG.md#unreleased). The [release checklist](docs/release-checklist.md) and [public playground deployment guide](docs/deployment.md) distinguish prepared configuration from verified release images, hosting and external-network checks. The visual brand update is still in progress.

## Architecture and system design

~~~mermaid
flowchart LR
    A[Agent or application] --> B[Seclume Proxy]
    B --> C[Scrubber]
    C --> D[Redis Session Map]
    C --> E[External Upstream]
    E --> F[Reinjector]
    D --> F
    F --> A
    C --> G[Wire Tap and telemetry: post-scrub only]
~~~

The Proxy scrubs messages, assistant tool-call arguments, and tool results before the Upstream call. The Session Map temporarily associates each Placeholder with its original value for the current Session. The Reinjector uses that Session Map for the response. If scrubbing or required state writes fail, Seclume blocks before the Upstream call; if reinjection state is unavailable, it returns unresolved Placeholders rather than guessing.

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
| Git | Current stable | Clone the repository and commit changes. |
| Python | 3.12 or later | Run the Proxy, scripts, and tests. |
| uv | Current stable | Resolve and run the Python workspace. |
| Docker Desktop | Current stable, Compose v2 | Start Redis, the mock Upstream, and the Proxy locally. |
| Node.js | 22 | Run the dashboard and marketing applications, matching CI. |
| npm | Bundled with Node.js | Install and build each Next.js app. |

### Installation

Clone the repository and create a local environment file. Never commit <code>.env</code> or put real personal data in it.

~~~bash
git clone https://github.com/hassanismailtech/seclume.git
cd seclume
cp .env.example .env
uv sync --project backend
npm --prefix frontend ci
npm --prefix website ci
~~~

PowerShell equivalent for the environment file:

~~~powershell
Copy-Item .env.example .env
~~~

For this Compose demo, set these values in the root <code>.env</code>. Inside a container, <code>localhost</code> refers to that container; the mock Upstream is reached by its Compose service name.

~~~dotenv
UPSTREAM_BASE_URL=http://mock-upstream:9000/v1
CORS_ORIGINS=http://127.0.0.1:3000,http://127.0.0.1:3001
~~~

Start the local backend demo stack:

~~~bash
docker compose up --build
~~~

Local endpoints are <code>http://127.0.0.1:8000</code> for Seclume, <code>http://127.0.0.1:9000</code> for the mock Upstream, and <code>127.0.0.1:6379</code> for Redis. Confirm readiness without exposing request data:

~~~bash
curl http://127.0.0.1:8000/readyz
~~~

In separate terminals, start the dashboard and marketing site on distinct loopback ports:

~~~bash
npm --prefix frontend run dev -- --hostname 127.0.0.1 --port 3000
npm --prefix website run dev -- --hostname 127.0.0.1 --port 3001
~~~

Open <code>http://127.0.0.1:3000</code> for the dashboard and <code>http://127.0.0.1:3001</code> for the marketing site. Set <code>NEXT_PUBLIC_AEGIS_URL</code> to a reachable Proxy base URL for a separately deployed dashboard. The public entry point is the [Seclume website](https://seclume.tech). Configure <code>NEXT_PUBLIC_MARKETING_URL</code> in the dashboard; enable a marketing-to-dashboard link only after the dashboard is ready for visitors.

## Local playground

In the root <code>.env</code>, set <code>PLAYGROUND_ENABLED=true</code>. For the rules-and-gazetteer demonstration, also set <code>NER_ENABLED=false</code>; the page reports lite mode. Keep the Compose mock URL and browser CORS origins above, then recreate the Proxy with <code>docker compose up --build --detach</code>.

Create <code>website/.env.local</code> with the public API base URL:

~~~dotenv
NEXT_PUBLIC_PLAYGROUND_API=http://127.0.0.1:8000
~~~

Restart the website development server and open <code>http://127.0.0.1:3001/playground</code>. Use its existing synthetic examples. The API accepts <code>POST /v1/playground/scrub</code>; responses contain scrubbed text and a simulated reply, never restored values. Redis is required; rate limiting is atomic and playground requests emit no Telemetry Events. If the backend is disabled it returns 404; if the browser API setting is empty, submissions are disabled. Production values are bundled at build time and require a rebuild.

The local development stack is not the public hosting configuration. Follow the separate [deployment guide](docs/deployment.md) before exposing the synthetic API.

## Operating guides

- [Local quickstart](docs/quickstart.md): Compose, a synthetic chat-client check, dashboard inspection and cleanup.
- [Configuration](docs/configuration.md): complete Python defaults, working-directory behavior, Compose overrides and public browser settings.
- [Security model](docs/security-model.md): trust boundary, attacker capabilities, existing controls and remaining risks.
- [Limitations](docs/limitations.md): detection evidence, Session continuity, retention and verification gaps.

Authentication is off unless `AEGIS_KEYS_FILE` is configured. The supplied Compose stack is unauthenticated local development with loopback publishing; it does not mount a tenant keys file. Session Map state uses ephemeral Redis, while existing SQLite audit metadata persists separately. See the guides before changing exposure or connecting a real Upstream.

## Local development and scripts

| Task | Command | Notes |
| --- | --- | --- |
| Start services | <code>docker compose up --build</code> | Ephemeral Redis plus local mock Upstream. |
| Proxy tests | <code>uv run --directory backend pytest -q</code> | Requires real Redis and a verified Caddy executable via <code>CADDY_BIN</code>; includes integration and leak tests. |
| Held-out evaluation | <code>uv run --directory backend python scripts/eval_heldout.py --floor 0.85</code> | Synthetic project-authored set. |
| Scrubber benchmark | <code>uv run --directory backend python scripts/bench_scrub.py</code> | Measured p50/p95; no fixed latency promise. |
| OpenAI SDK smoke test | <code>uv run --directory backend python scripts/sdk_smoke.py</code> | Requires the local stack. |
| Dashboard development | <code>npm --prefix frontend run dev</code> | Operational dashboard. |
| Dashboard lint and build | <code>npm --prefix frontend run lint</code>, <code>npm --prefix frontend run build</code> | Quality gates. |
| Marketing development | <code>npm --prefix website run dev</code> | Marketing site. |
| Marketing lint and build | <code>npm --prefix website run lint</code>, <code>npm --prefix website run build</code> | Quality gates. |
| Marketing client tests | <code>npm --prefix website test</code> | Playground, public routes and contact contracts. |
| Public claims | <code>uv run --directory backend python scripts/claims_lint.py</code> | Checks public source text for banned claims. |

## Deployment and production build

Build the Proxy runtime image with the same image-name setting used by Compose:

~~~bash
export SECLUME_IMAGE="${SECLUME_IMAGE:-aegis:local}"
docker build --target runtime --tag "$SECLUME_IMAGE" backend
~~~

PowerShell equivalent:

~~~powershell
$env:SECLUME_IMAGE = "aegis:local"
docker build --target runtime --tag $env:SECLUME_IMAGE backend
~~~

The planned release is still [Unreleased](CHANGELOG.md#unreleased). These commands build a local image; a published release image is not assumed. See the [release checklist](docs/release-checklist.md) before tagging, merging to the publishing branch, or publishing. A separate [synthetic playground deployment profile](docs/deployment.md) is prepared for review; it has not been launched.

The Proxy refuses startup when <code>BIND_HOST</code> is non-loopback and tenant-key authentication is disabled, unless <code>AEGIS_INSECURE_DEV=1</code> is explicitly set. Wildcard addresses <code>0.0.0.0</code> and <code>::</code> are not loopback. When tenant keys are configured, a dedicated <code>AEGIS_TICKET_SECRET</code> is required even with the development override. Direct Uvicorn commands must use the same <code>--host</code> as <code>BIND_HOST</code>; the guard checks configuration, not Uvicorn's independently supplied arguments.

For a standalone container, first provide container-reachable Redis and Upstream URLs in <code>.env</code>. This development example binds inside the container while publishing only on host loopback:

~~~bash
docker run --rm --publish 127.0.0.1:8000:8000 --env-file .env \
  --env BIND_HOST=0.0.0.0 --env AEGIS_INSECURE_DEV=1 "$SECLUME_IMAGE"
~~~

Or use the local Compose deployment:

~~~bash
docker compose up --build --detach
docker compose ps
~~~

Compose explicitly sets <code>BIND_HOST=0.0.0.0</code> and <code>AEGIS_INSECURE_DEV=1</code>. This unauthenticated development configuration is suitable only while published ports remain on <code>127.0.0.1</code> and the host is trusted; do not expose it through a public reverse proxy. <code>SECLUME_IMAGE</code> selects the Proxy image name and defaults to <code>aegis:local</code>.

Before connecting a real Upstream, provide <code>UPSTREAM_BASE_URL</code>, provide an <code>UPSTREAM_API_KEY</code> or pass a caller Authorization header, set <code>AEGIS_KEYS_FILE</code> when authentication is required, use TLS and an authenticated network boundary, and never expose Redis directly.

The dashboard and marketing site are independently deployable Next.js applications. The [marketing site](https://seclume.tech) is the public entry point. Configure <code>NEXT_PUBLIC_MARKETING_URL</code> to return dashboard users to marketing, and set both <code>NEXT_PUBLIC_APP_URL</code> and <code>NEXT_PUBLIC_DASHBOARD_ENABLED=true</code> only when the dashboard is ready for visitor navigation. Shared Tailwind design tokens and explicit Geist font variables preserve a consistent handoff. The <code>ci</code> workflow builds both applications on every Pull Request and on <code>main</code>.

## API documentation and usage examples

### Health and readiness

~~~bash
curl http://127.0.0.1:8000/healthz
curl http://127.0.0.1:8000/readyz
~~~

### OpenAI-compatible chat completion

Use synthetic, non-sensitive content when testing. Set the client base URL to Seclume; the SDK request shape remains standard.

~~~python
from openai import OpenAI

client = OpenAI(
    base_url="http://127.0.0.1:8000/v1",
    api_key="local-development-key",
)

completion = client.chat.completions.create(
    model="mock",
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
| <code>/v1/playground/scrub</code> | <code>POST</code> | Disabled-by-default synthetic scrub-only playground. |
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

The no-leak tests assert that the project’s synthetic planted values do not appear in the Wire Tap. The evaluator reports precision and recall for a 220-sentence synthetic, project-authored set; its current floor is PERSON recall <code>0.85</code>. Complete backend tests require real Redis and a verified Caddy executable via <code>CADDY_BIN</code>. CI starts native Redis on Ubuntu with persistence disabled; missing integration prerequisites must fail rather than silently skip. Coverage reporting is not currently configured. Workflow jobs cover tests, the pattern benchmark, evaluation, web builds, dependency audits, secret scanning and public claims; repository administrators must verify which checks their rules require.

## Contributing

Read [CONTRIBUTING.md](CONTRIBUTING.md), [SECURITY.md](SECURITY.md), and [docs/CLAIMS.md](docs/CLAIMS.md) before opening a change.

- Work from a short-lived <code>feat/</code>, <code>fix/</code>, <code>docs/</code>, or <code>chore/</code> branch.
- Use Conventional Commits and follow [CONTRIBUTING.md](CONTRIBUTING.md) for commit requirements. A <code>-s</code> sign-off is distinct from cryptographic commit signing.
- Keep tests, claim updates, dependency licence checks, and documentation in the same Pull Request as the implementation.
- Never add real personal data to tests, fixtures, screenshots, issues, or Pull Requests.

### Pull Request Process

Submit changes through Pull Requests and review passing <code>ci</code> and <code>eval</code> results before merging. Repository administrators should require the intended checks and restrict direct pushes, force-pushes and deletions in GitHub settings. Workflow files do not prove that those repository settings are active. A merge to <code>main</code> can start the separate image-publishing workflow.

## Security and performance

Report privately to [security@seclume.tech](mailto:security@seclume.tech) or through [GitHub private security advisories](https://github.com/hassanismailtech/seclume/security/advisories/new); use synthetic reproduction data only. General/design-partner inquiries: [hello@seclume.tech](mailto:hello@seclume.tech). Privacy inquiries: [privacy@seclume.tech](mailto:privacy@seclume.tech). See [SECURITY.md](SECURITY.md) for scope and disclosure guidance.

The Session Map uses temporary Redis state and the supplied Compose configuration disables Redis persistence. Existing SQLite audit metadata is separate, and its unkeyed hash chain is not resistant to an administrator rewriting it. Seclume measures detector behaviour rather than promising latency; results depend on workload, runtime, hardware and cache state. Review [docs/metrics.txt](docs/metrics.txt), [docs/limitations.md](docs/limitations.md) and [docs/CLAIMS.md](docs/CLAIMS.md) before publishing performance or quality claims.

## License and authors

Seclume source code is released under the [Apache License 2.0](LICENSE). Original
prose and diagrams in [`docs/`](docs/) are released under
[CC BY 4.0](docs/LICENSE.md); source code, configuration, and code blocks in
those documents remain Apache-2.0. Copyright © 2026 Hassan Ismail. Maintained
by Hassan Ismail and contributors.
