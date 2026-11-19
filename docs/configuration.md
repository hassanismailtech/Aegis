# Configuration reference

These are defaults from [Settings](../backend/app/config.py), not production recommendations. Numeric defaults below are configuration values, not measured quality or performance claims. Python settings read process environment and a `.env` relative to the process working directory; unknown entries are ignored. Run native commands from the intended directory and do not assume a repository-root `.env` is loaded after `uv --directory backend` changes directory. Never commit secrets.

| Setting | Default | Purpose / qualification |
|---|---|---|
| `UPSTREAM_BASE_URL` | `"http://localhost:9000/v1"` | Compatible Upstream base URL; use a trusted endpoint. |
| `UPSTREAM_API_KEY` | `""` | Provider secret; when empty, eligible caller credentials are forwarded. |
| `UPSTREAM_MODEL_OVERRIDE` | `""` | Empty preserves the requested model. |
| `REDIS_URL` | `"redis://localhost:6379/0"` | Private Redis connection. |
| `SESSION_TTL_SECONDS` | `300` | Sliding Session Map TTL. |
| `NER_ENABLED` | `true` | Enables the local GLiNER PERSON layer. |
| `NER_MODEL` | `"urchade/gliner_small-v2.1"` | Local model identifier. |
| `NER_THRESHOLD` | `0.5` | PERSON detection threshold. |
| `NER_TIMEOUT_MS` | `2000` | Inference timeout; a timeout blocks scrubbing. |
| `NER_RUNTIME` | `"torch"` | `torch` or opt-in `onnx`; export the ONNX model before use. |
| `NER_ONNX_DIR` | `"data/ner_onnx"` | ONNX model directory. |
| `NER_ONNX_FILE` | `"model_quantized.onnx"` | ONNX model filename. |
| `NER_CACHE_TTL_SECONDS` | `300` | In-process detected-span cache TTL; zero disables it. |
| `NER_CACHE_MAX_ENTRIES` | `512` | Detected-span cache entry bound. |
| `EVAL_RECALL_FLOOR` | `0.85` | Evaluation threshold, not a result or operating assurance. |
| `FEE_USD_PER_1K_TOKENS` | `0.001` | Telemetry fee calculation rate; not billing or a provider price. |
| `CORS_ORIGINS` | `"http://localhost:3000"` | Comma-separated allowed browser origins; not authentication. |
| `DETECTOR_PACKS` | `["ng"]` | Ordered installed detector packs. |
| `AEGIS_DEMO_TOKEN` | `""` | Optional shared demo guard; not tenant isolation. |
| `AEGIS_KEYS_FILE` | `""` | Tenant-key JSON path; authentication is off when unset. |
| `AEGIS_TICKET_SECRET` | `""` | Dedicated secret required with tenant keys. Otherwise ticket signing falls back to the demo secret or a process-local secret. |
| `AEGIS_INSECURE_DEV` | `false` | Explicit non-loopback startup bypass without tenant keys; development only. |
| `BIND_HOST` | `"127.0.0.1"` | Checked at startup and used by the Docker entrypoint. Align any direct Uvicorn `--host` with it. |
| `PLAYGROUND_ENABLED` | `false` | Opt-in public synthetic Scrubber route. |
| `PLAYGROUND_MAX_CHARS` | `2000` | Positive API input limit; website input is independently capped at 2000. |
| `PLAYGROUND_RATE_PER_MINUTE` | `20` | Positive per-client fixed-minute limit, enforced atomically in Redis. |
| `PLAYGROUND_TRUST_PROXY` | `false` | Trust first valid forwarded IP only behind isolated ingress that overwrites the header. |
| `MAX_BODY_BYTES` | `1048576` | Positive request-body byte limit. |
| `MAX_MESSAGES` | `200` | Positive message-count limit. |
| `RATE_LIMIT_CAPACITY` | `60` | Positive tenant request allowance when tenant authentication is enabled. |
| `RATE_LIMIT_REFILL_PER_SECOND` | `1.0` | Positive tenant allowance refill rate. |
| `AUDIT_DB_PATH` | `"data/audit.db"` | Existing SQLite Telemetry Event audit file; initialized at startup, not an opt-in switch. |

## Launch-specific settings

Compose reads its explicit [environment mapping](../docker-compose.yml), not every entry in the root `.env`. Root values are used only where the Compose file interpolates them. It overrides `BIND_HOST`, `AEGIS_INSECURE_DEV`, and `REDIS_URL`, and supplies its own mock Upstream default. Unmapped settings and key files need explicit wiring/mounts before a different deployment can use them. The default Compose stack remains unauthenticated and loopback-published.

`SECLUME_IMAGE` selects the Compose Proxy image, default `aegis:local`. `PORT` controls the Docker entrypoint port, default `8000`; changing it also requires matching health checks and port mappings. Compose sets Uvicorn's `FORWARDED_ALLOW_IPS` empty to disable its own client-IP rewriting. Keep that behavior when using the playground's separate proxy-trust control.

The website's public build settings are documented in [its environment example](../website/.env.example). `NEXT_PUBLIC_PLAYGROUND_API` is a public API base URL, not a secret. `NEXT_PUBLIC_SITE_URL` is the verified HTTPS site origin. Cross-origin retry countdowns require ingress to expose `Retry-After`; otherwise the website uses a generic wait message. Backend CORS configuration alone does not expose that response header.

For authenticated API calls, use `Authorization: Bearer` for the tenant key. Supply a separate provider credential using `UPSTREAM_API_KEY`, OpenAI `X-Upstream-Authorization`, or Anthropic `X-Upstream-Api-Key`; do not put tenant credentials in browser-visible `NEXT_PUBLIC_*` settings. Review the [security model](security-model.md) before deployment.
