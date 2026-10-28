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
