# Local quickstart

Use synthetic data only. This path runs the Proxy, Redis and mock Upstream on a trusted development machine. It is not a public deployment. Build/download time varies; the mock requires no provider key.

## Start the stack

Install Git and Docker with Compose v2. From a checkout of this branch:

```sh
docker compose config --quiet
docker compose up --build --detach --wait --wait-timeout 180
docker compose ps
curl --fail http://127.0.0.1:8000/readyz
```

Run these commands from the repository root. The health wait starts after image building; the runtime image builds with the local model included. Readiness requires Redis and, when enabled, a warm NER model. If model loading fails while NER is enabled, readiness stays unavailable even though the process can run with rules and the gazetteer.

The supplied Compose file publishes Proxy, mock Upstream and Redis ports only on loopback. Inside the Proxy container it explicitly enables wildcard binding and `AEGIS_INSECURE_DEV=1`. Authentication is off unless `AEGIS_KEYS_FILE` is configured; this Compose file does not mount a keys file or forward that setting. Keep this development stack private. Use `SECLUME_IMAGE` to select the local Proxy image name; the default is `aegis:local`.

## Try a chat client

Use an API client with configurable OpenAI-compatible connection settings. This is a manual compatibility check, not a claim that a particular desktop chat application has been tested.

| Client setting | Local value |
|---|---|
| API base URL | `http://127.0.0.1:8000/v1` (some clients append `/v1` themselves) |
| API key | A dummy, non-secret value for this unauthenticated local mock |
| Model | `mock` |

Paste the existing synthetic `p01` text from [demo/prompts.json](../demo/prompts.json). The mock reply should reuse detected Placeholders, which the Reinjector restores for the client. This does not test a real model or execute a banking transaction. For stable Placeholders across turns, the client must reuse `X-Aegis-Session` while the Session Map remains available; clients without custom headers cannot rely on that continuity.

To inspect the post-scrub Wire Tap, install Node.js 22 and the existing dashboard dependencies, then start it in another terminal:

```sh
npm --prefix frontend ci
npm --prefix frontend run dev
```

Open the printed local dashboard URL and select the request. The Wire View shows post-scrub request data; the chat client's reply contains restored values. Keep chat history and screenshots synthetic. Client storage and provider retention are outside the Proxy's boundary.

## Optional checks and cleanup

With Python 3.12 and uv installed, `uv run --directory backend python -m app.cli doctor` checks local dependencies. It does not prove an authenticated provider request succeeds. The complete backend test suite requires real Redis and `CADDY_BIN` pointing to a verified Caddy executable: `uv run --directory backend pytest -q`. CI starts native Redis on Ubuntu with persistence disabled and downloads a checksum-verified Caddy release for ingress tests. Mandatory real-Redis and Caddy tests do not silently skip when their prerequisites are unavailable.

Stop the demo with `docker compose down`. Redis has no configured persistence or volume. The existing SQLite audit file is separate; do not describe the whole application as storage-free. See [configuration](configuration.md), [security model](security-model.md) and [limitations](limitations.md) before connecting a real Upstream or changing network exposure.

The website playground is a separate, opt-in scrub-only demonstration. Its API returns scrubbed output and a simulated reply, with no restored values, Upstream call or Telemetry Events. The website needs `NEXT_PUBLIC_PLAYGROUND_API` at build time; the backend needs `PLAYGROUND_ENABLED=true` and an allowed CORS origin. Missing configuration leaves submissions disabled.
