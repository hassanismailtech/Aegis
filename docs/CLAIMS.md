# Claims register

Public text may only use rows marked **OK**, with the stated qualifier. Numbers come from `docs/metrics.txt` and `NOTES.md` benchmark tables. Update this file in the same PR that changes behaviour.

| Claim | Status | Qualifier / evidence |
|---|---|---|
| Works with the official OpenAI SDK by changing `base_url`, incl. streaming and tool calls | OK | `scripts/sdk_smoke.py`, `test_roundtrip.py`, `test_streaming.py` |
| Works with the official Anthropic SDK (`/v1/messages`), incl. streaming | OK | `test_anthropic.py`, `test_streaming.py` |
| Scrubs tool-call arguments and tool results | OK | `test_roundtrip.py`, `test_anthropic.py` |
| Placeholders split across stream chunks are reinjected | OK | `test_streaming.py` (every split position) |
| Wire Tap shows exactly what Upstream received | OK | Wire Tap endpoint, `test_no_leak.py` |
| Leak test: 0 planted entities reached Upstream | OK | `leaks: 0 / 35` on the project's own prompts; not an adversarial audit |
| Per-tenant API keys, size limits, rate limits, signed dashboard tickets | OK | Authentication is **off unless `AEGIS_KEYS_FILE` is set**. Say so wherever auth is mentioned |
| Startup refuses configured non-loopback binds without tenant keys | OK | `AEGIS_INSECURE_DEV=1` explicitly bypasses this check. Keys require `AEGIS_TICKET_SECRET`. The guard checks `BIND_HOST`, not independently supplied Uvicorn arguments; `test_startup_guard.py` |
| Optional synthetic playground shows scrubbed input, Placeholders, entity counts and a simulated reply | OK | API disabled by default; website submissions require `NEXT_PUBLIC_PLAYGROUND_API` at build time and backend opt-in/CORS. No reply-generation model or Upstream call; detection can use NER in full mode. No restored values or Telemetry Events. Temporary Redis Session Map cleanup is attempted after each request, with TTL fallback. `test_playground.py`, `website/tests/playground.test.mjs` |
| Placeholders remain stable across conversation requests using `X-Aegis-Session` | OK | Reuse the same header within the same tenant and the Session Map's sliding TTL. State expiry or loss ends that mapping. `main._session_id`, `test_roundtrip.py`, `test_session_map.py` |
| Source code is Apache-2.0; design partners are being sought for a free self-hosted pilot | OK | `LICENSE`; this is an invitation, not evidence of existing partners or customers. Public interest uses GitHub Issues with synthetic descriptions only; no response-time commitment or mailbox is advertised. |
| Rule layer overhead | OK, as measured | p50 about 0.15 to 0.22 ms on 60 words (dev laptop, `bench_scrub.py`) |
| Model layer overhead | OK, as measured | Cold p50 about 350 to 440 ms (60 words) and about 3.2 to 4.3 s (500 words); long text exceeds the 2 s default timeout and is blocked (503) |
| Cached or skipped model calls are fast | OK | about 0.4 ms p50 / under 2 ms p95 on cache hit or skip |
| Quality numbers | OK, with qualifier | 220-sentence **synthetic, project-authored** set. Structured types 100% there (template-like); PERSON recall 96.9% [93.5, 98.6], **PERSON precision 61.9%** (over-redaction). Not independent evidence |
| ONNX int8 | OK, opt-in | PERSON recall 94.9% on the same set; modest speed gain |
| No persistent storage by design | OK | Redis snapshots and AOF off, sliding TTL (default 300 s). Upstream providers have their own retention |
| Blocks the request if scrubbing or state fails | OK | Reinjection failure degrades (returns Placeholders), documented |
| `<40 ms`, "three milliseconds", "sub-millisecond overhead" | **FALSE** | Never use |
| "Zero retention mathematically", "zero-knowledge", "guarantees", "100% recall", "99.4% precision" | **NEVER** | |
| "Compliant", "legal", "without violating the NDPA" | **NEVER** | Say: reduces exposure, minimises data, produces evidence. Not legal advice |
| Evasion resistance (leetspeak, spelled-out digits) | **NO** | Known limitation |
