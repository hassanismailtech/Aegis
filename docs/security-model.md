# Security model

The Proxy reduces identifier exposure on supported request surfaces. It is a technical control, not a legal conclusion or a substitute for reviewing the data sent to a provider. See the [claims register](CLAIMS.md) and [limits](limitations.md).

The trusted boundary contains the client, Proxy process, local detector, Redis Session Map, Reinjector and protected operational interfaces. Upstream receives the scrubbed request. The client receives a reply with known Placeholders restored. A host/Redis administrator, the caller's chat history, and the provider's storage remain outside the protection offered by replacement alone.

| Attacker or failure | Existing control | Residual risk / operator responsibility |
|---|---|---|
| Remote caller reaches an unauthenticated Proxy | Non-loopback `BIND_HOST` refuses startup without tenant keys unless the explicit development bypass is enabled. Keys require a dedicated ticket secret. | Authentication is off unless `AEGIS_KEYS_FILE` is set. Direct Uvicorn arguments must match settings. Loopback publishing is a development boundary, not a public gateway. |
| Caller submits identifiers through messages or tools | Scrubber processes supported message text, tool arguments and tool results before Upstream. | Misses and over-redaction remain possible. Unknown fields, unsupported content and arbitrary extra metadata are not a blanket scrubbed surface. |
| Scrubber inference or required state writes fail | Request is blocked before Upstream. | A failed forward-map read for streaming can instead degrade reinjection to unresolved Placeholders. Startup model-load failure can reduce detection to rules and gazetteer; enabled-but-unwarmed NER fails readiness. Enforce readiness and verify the intended mode. |
| Session state expires during a reply | Reinjector leaves unknown Placeholders unresolved rather than guessing values. | Restored replies may be incomplete. Redis availability and expiry affect continuity. |
| A caller accesses another tenant's Session | Configured tenant keys select tenant-scoped Session identifiers. | Keep keys private and authenticate operational access. The demo shared guard is not a tenant boundary. |
| Proxy headers are forged to evade playground limits | Proxy trust defaults off; rate counters are atomic and client keys are HMAC-derived. | Trusted ingress must replace forwarded headers and prevent direct backend access. Per-client limits do not stop a distributed resource-exhaustion attack. |
| Operational data or infrastructure is compromised | Session Map state uses ephemeral Redis in the supplied configuration; operational records avoid body fields by contract. | Redis, host memory, audit files, logs and Wire Tap require access control. Wire Tap may still contain undetected identifiers. Do not place sensitive text in model names or metadata. |

## Retention and deployment responsibilities

Redis snapshots and AOF are disabled and no Redis volume is configured. Session Map keys expire; the NER cache is separate process memory and can hold detected name spans. Existing SQLite audit metadata persists independently of Redis. Its current hash chain is not protection against an administrator rewriting the database and recomputing the chain. Audit hardening is deferred; no new retention or audit controls are introduced here.

Keep Redis and operational routes private, use TLS and tenant authentication for real deployments, and protect provider credentials. CORS controls browser origins; it does not authorize non-browser clients. Do not publish the development Compose stack behind a public proxy. The supplied configuration does not itself provision TLS, firewall rules or a production ingress.

Playground requests have their own temporary Session Map and cleanup/TTL fallback. They return only scrubbed output and a simulated reply, emit no Telemetry Events and do not call Upstream. A detection miss can still appear in the Scrubber output: public demos must use synthetic data. This behavior does not describe normal Proxy telemetry or the caller's chat history.

Report vulnerabilities through [GitHub private security advisories](https://github.com/hassanismailtech/seclume/security/advisories/new), using synthetic reproductions. See [SECURITY.md](../SECURITY.md) for the existing reporting policy.
