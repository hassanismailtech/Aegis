# Aegis PRD (Original hackathon spec — archived)

> **Archived Specification**: This document is the original hackathon specification for Aegis. It is preserved for provenance, architecture context, and glossary reference.

Source of truth for the AI IDE. If code and this file disagree, this file wins. Anything unspecified: pick the simplest option and log it in `NOTES.md` under `ASSUMPTIONS`. Do not ask, do not invent features.

## 1. Pitch

Aegis is an OpenAI-compatible proxy. Before a prompt or agent tool call leaves the building, it swaps Nigerian PII for placeholders. When the reply comes back, it swaps the real values in again.

- **Problem:** Nigerian banks, fintechs and hospitals want frontier-model agents, but sending BVN, NIN, phone numbers and names to offshore APIs creates NDPA 2023 cross-border-transfer exposure (transfers are allowed only under conditions such as adequacy or safeguards). Local models are weaker.
- **Users:** Tobi (platform engineer) changes `base_url` and nothing else. Femi (DPO) gets proof of exactly what left the building.
- **Theme fit:** the caller is an agent. Aegis is infrastructure for agents handling regulated data: it handles tool-call arguments and tool results, not only chat text.
- **Honest claim:** Aegis reduces leakage. It does not "guarantee zero". Structured IDs are rule-detected. Names are model-detected, with recall we measure and show.
- **Why not Presidio / LLM Guard:** Nigerian entity pack (BVN, NIN, NUBAN, +234 formats, Yoruba/Igbo/Hausa names), reversible session-stable pseudonyms, agent/tool-call awareness, and a Wire Tap that proves what crossed the border.

## 2. Glossary (use these exact words in code, UI and comments)

| Term | Meaning |
|---|---|
| Aegis | The product. Never "Sovereign Proxy" or "Sovereign Data Proxy" in code. |
| Proxy | The FastAPI service exposing `/v1/chat/completions`. |
| Scrubber | Module that finds entities and replaces them with Placeholders. |
| Entity | A detected PII span. Types in section 6. |
| Placeholder | Replacement string, format `[[TYPE_N]]`, e.g. `[[PERSON_1]]`. Never "token" or "tag" (LLM tokens are a different thing). |
| Session Map | Redis hashes mapping Placeholder to original value for one Session. |
| Session | Conversation scope for stable numbering. Id = header `X-Aegis-Session`, else first 16 hex of sha256 of the Authorization header. |
| Reinjector | Module that swaps Placeholders in replies back to originals. |
| Upstream | The real LLM API (`UPSTREAM_BASE_URL`). |
| Wire Tap | Record of the exact post-scrub bytes sent to Upstream. |
| Telemetry Event | Per-request JSON record (section 7.3). |

## 3. Core Loop (build and perfect this before anything else)

1. Agent (official OpenAI SDK, `base_url` = Aegis) sends a request containing Nigerian PII.
2. Aegis scrubs every message, tool call argument and tool result into Placeholders.
3. Upstream receives only Placeholders. Wire Tap proves it.
4. Upstream replies using the Placeholders.
5. Aegis reinjects the originals into the reply, including inside `tool_calls[].function.arguments`.
6. Agent receives real values. Dashboard shows the event live.

Two-minute demo script: agent runs a "transfer to Chinedu Okafor, BVN ..., phone ..." task with 2 tools. Split screen: AGENT SAW (real) vs UPSTREAM SAW (placeholders). Then run the 12-prompt leak test and show `0 leaks / N planted entities`. Then show measured overhead and per-type recall.

## 4. Scope

**In:** `POST /v1/chat/completions` (non-streaming real path; `stream:true` handled by pseudo-stream, see 5.1), regex + gazetteer + GLiNER scrubbing, Redis Session Map, Reinjector, Telemetry SSE, one-page dashboard, demo agent, leak test, recall eval, mock Upstream.

**Out (do not build, do not scaffold):** auth/API keys/billing (BYOK passthrough only), Postgres or any persistent store, WebSockets, CI/CD, multi-arch Docker, cloud deploy, multimodal, `/v1/embeddings` or other routes, LOC entity, fine-tuning, Rust, user accounts, settings pages, dark/light toggle, multiple dashboard pages.

**Stretch (only after Step 5 is green):** true chunked streaming with hold-back buffer; ADDRESS entity; NUBAN check-digit validation.

## 5. Functional spec

### 5.1 Proxy (`POST /v1/chat/completions`)

- Request model: `extra="allow"`. Unknown fields pass through untouched (new models need `max_completion_tokens`, `reasoning_effort`, etc.).
- Accept `messages[].content` as a string OR a list of parts (`{"type":"text","text":...}`; scrub text parts, pass other parts through). Roles: system, user, assistant, tool. Also scrub `assistant.tool_calls[].function.arguments` (JSON string) and `tool` message content.
- Auth: forward the client's `Authorization` header to Upstream unless `UPSTREAM_API_KEY` is set. Aegis does not validate keys.
- Malformed body: HTTP 400 in OpenAI error shape (7.4).
- `stream:true`: call Upstream non-streaming, then return a valid SSE response (one content chunk, a final chunk with `finish_reason`, then `data: [DONE]`) so SDK streaming clients work.
- Response headers added: `X-Aegis-Request-Id`, `X-Aegis-Entities` (count), `X-Aegis-Overhead-Ms`, `X-Aegis-Unresolved` (count).

### 5.2 Scrubber

Order: (1) pattern rules, (2) gazetteer for PERSON, (3) GLiNER for PERSON. Merge overlapping spans, longest wins. Same original value in the same Session always gets the same Placeholder (reverse map lookup). Scrub every message on every request: client apps resend history that already contains reinjected real values.

GLiNER runs in a thread pool with an `NER_TIMEOUT_MS` timeout (CPU-bound, must never block the event loop). Load and warm the model in the FastAPI `lifespan`, not on first request.

### 5.3 Session Map

Redis only, no disk. Sliding TTL: every request refreshes `SESSION_TTL_SECONDS` (default 300). Keys in 7.2.

### 5.4 Reinjector

Applies to `choices[].message.content` and `choices[].message.tool_calls[].function.arguments`. For `arguments` (JSON string) JSON-escape the replacement value. Tolerant matching (section 7.1 test table). Only swap Placeholders that exist in this Session Map. Unknown ones stay as-is and increment `unresolved`.

### 5.5 Telemetry

After each request write a Telemetry Event: `XADD aegis:events MAXLEN ~ 1000`, `PUBLISH aegis:live`, and `HINCRBY aegis:stats`. `GET /v1/aegis/events` streams SSE (`event: telemetry`). `GET /v1/aegis/stats` returns aggregates. `GET /v1/aegis/wiretap/{request_id}` returns the post-scrub outbound messages. All of these contain post-scrub text only, never the Session Map or pre-scrub text.

### 5.6 Dashboard (single page, Next.js)

Top bar: entities scrubbed (total), p50 and p95 `overhead_ms`, requests, metered fee (USD), leaks found (from last leak-test run). Left: live feed (SSE). Right: entity-type bar chart. Center-bottom: Wire View showing for the selected request what Upstream received. Empty state shows "Waiting for traffic" plus a "Seed demo data" button that POSTs 20 synthetic Telemetry Events to `/v1/aegis/_seed`. Must render in under 200 ms with seeded data.

### 5.7 Demo agent, leak test, recall eval

- `demo/agent.py`: OpenAI SDK, tools `lookup_customer(name)` and `initiate_transfer(account_no, amount)` backed by a hardcoded `CUSTOMERS` array. Prints AGENT SAW vs UPSTREAM SAW (from Wire Tap).
- `tests/test_no_leak.py`: send every prompt in `demo/prompts.json` through Aegis to the mock Upstream. Assert none of the planted PII strings appear in any Wire Tap body.
- `scripts/eval_recall.py`: reads `demo/labeled_eval.jsonl` (40 labeled sentences), prints per-type precision and recall.
- `scripts/bench_scrub.py`: 100 runs on a 60-word and a 500-word prompt, prints p50/p95 for pattern layer and NER layer separately.
- `scripts/mock_upstream.py`: FastAPI app on :9000 implementing `/v1/chat/completions`. Echo mode: replies "Transfer initiated to <first placeholder it sees>". Tool mode: if tools are present, returns a tool call whose arguments reuse Placeholders from the prompt. Stores every received body for `GET /_tap`. Enables offline demos and zero API cost.

## 6. Entity spec

| Type | Detection | Notes |
|---|---|---|
| PHONE | Regex: optional `+234`/`234`/`0`, then `[789][01]`, then 8 digits; spaces/dashes allowed between groups | Check before 11-digit IDs (phones are 11 digits starting with 0). |
| BVN | 11 digits, not a phone; default label for unlabeled 11-digit numbers (over-redact on purpose) | Real BVNs are 11 digits. Fixtures must use 11. |
| NIN | 11 digits with `NIN` or `National Identification` within 40 chars before | Else falls to BVN. |
| ACCOUNT_NO | 10 digits with `account`, `acct`, `a/c` or `NUBAN` within 40 chars before | Bare 10-digit numbers are usually amounts: leave alone. |
| EMAIL | Standard email regex | |
| PERSON | `data/ng_names.json` gazetteer (capitalized name sequences) + GLiNER label `person`, threshold `NER_THRESHOLD` | Include Yoruba, Igbo, Hausa, Pidgin-context names. |

Dashboard breakdown uses exactly these six types.

## 7. Contracts

### 7.1 Placeholder format and Reinjector tests

Format `[[TYPE_N]]`, N starts at 1 per type per Session. Reinjector must resolve all of these to `[[PERSON_1]]`'s value:

`[[PERSON_1]]`, `[[ PERSON_1 ]]`, `[[person_1]]`, `[PERSON_1]`, `[ PERSON_1 ]`, `[[PERSON_1]]'s`, and `**[[PERSON_1]]**`. It must NOT touch `[[PERSON_9]]` when 9 is absent from the map, or text like `[1]`.

### 7.2 Redis keys (no persistence: run with `--save "" --appendonly no`, no volume)

| Key | Type | Content |
|---|---|---|
| `aegis:sess:{sid}:fwd` | HASH | placeholder to original |
| `aegis:sess:{sid}:rev` | HASH | original to placeholder |
| `aegis:sess:{sid}:ctr` | HASH | type to int counter |
| `aegis:events` | STREAM | Telemetry Events, `MAXLEN ~ 1000` |
| `aegis:stats` | HASH | counters: `requests`, `entities_total`, `entities:{TYPE}`, `fee_micro_usd`, `state_loss` |
| `aegis:overhead` | LIST | last 500 `overhead_ms` values (for p50/p95), `LTRIM` after push |

All `aegis:sess:*` keys share the same sliding TTL.

### 7.3 Telemetry Event

```json
{
  "request_id": "req_01",
  "ts": "2026-10-24T09:00:00Z",
  "session": "a1b2c3d4",
  "model": "gpt-5-mini",
  "stream_requested": false,
  "entities": {"PERSON": 2, "BVN": 1, "PHONE": 1, "NIN": 0, "ACCOUNT_NO": 0, "EMAIL": 0},
  "entities_total": 4,
  "scrub_ms": 31.2,
  "reinject_ms": 0.8,
  "upstream_ms": 912.4,
  "overhead_ms": 32.0,
  "unresolved": 0,
  "status": "ok",
  "fee_usd": 0.0003
}
```

`status` is one of `ok`, `state_loss`, `scrub_blocked`, `upstream_error`. `overhead_ms = scrub_ms + reinject_ms` (excludes Upstream time). `fee_usd = (prompt_tokens + completion_tokens) / 1000 * FEE_USD_PER_1K_TOKENS`, using Upstream `usage`. "Entities" always means detected PII spans; never call these "tokens".

### 7.4 Error shape (OpenAI-compatible)

```json
{"error": {"message": "...", "type": "invalid_request_error", "param": null, "code": "aegis_scrub_failed"}}
```

### 7.5 Environment (`.env.example`)

```
UPSTREAM_BASE_URL=http://localhost:9000/v1   # real: https://api.openai.com/v1
UPSTREAM_API_KEY=                            # empty = forward client's Authorization
UPSTREAM_MODEL_OVERRIDE=                     # empty = pass client's model
REDIS_URL=redis://localhost:6379/0
SESSION_TTL_SECONDS=300
NER_ENABLED=true
NER_MODEL=urchade/gliner_small-v2.1
NER_THRESHOLD=0.5
NER_TIMEOUT_MS=2000
FEE_USD_PER_1K_TOKENS=0.001
CORS_ORIGINS=http://localhost:3000
```

## 8. Failure policy

| Condition | Behavior | HTTP | Event `status` |
|---|---|---|---|
| Scrubber exception or NER timeout | Block. Nothing is sent Upstream. | 503 `aegis_scrub_failed` | `scrub_blocked` |
| Redis unavailable before Upstream call | Block. | 503 `aegis_state_unavailable` | `scrub_blocked` |
| Upstream 4xx/5xx/timeout | Pass status and OpenAI-shaped error through. 60 s Upstream timeout, then 504. | as Upstream / 504 | `upstream_error` |
| Placeholder missing from Session Map at reinjection (TTL expired, Redis restarted) | Return reply with Placeholders left as-is. | 200 + `X-Aegis-Unresolved: n` | `state_loss` |
| Malformed request | OpenAI-shaped 400. | 400 | not logged |

Two different "fail closed" cases: scrub failure blocks the request (safety). Reinjection failure degrades the reply but never guesses PII (integrity).

## 9. Performance budgets (measured, never asserted)

- Pattern layer p95 under 5 ms on a 60-word prompt.
- NER layer: whatever `scripts/bench_scrub.py` measures on the demo laptop. Report it as measured. If NER p95 exceeds 250 ms on the 60-word prompt, switch the NER layer to run only on text left after pattern + gazetteer, and cap NER input at 2,000 characters per message.
- Reinjection p95 under 10 ms.
- Deck and dashboard show `overhead_ms` (Aegis only) separately from `upstream_ms`.

## 10. Repo layout (create exactly this)

```
aegis/
  AGENTS.md  PRD.md  PROMPTS.md  NOTES.md  README.md  .env.example
  docker-compose.yml            # redis only: --save "" --appendonly no, no volumes
  backend/
    pyproject.toml              # uv-managed
    app/
      main.py                   # app, lifespan (warm NER, redis pool), routes
      config.py                 # pydantic-settings
      schemas.py                # ChatRequest(extra=allow), EntityType, TelemetryEvent
      errors.py                 # OpenAI-shaped errors
      session_map.py            # redis hashes, sliding TTL, stable numbering
      scrubber/{__init__,patterns,gazetteer,ner}.py
      reinjector.py
      upstream.py               # httpx.AsyncClient
      telemetry.py              # stream, pubsub, SSE, stats, seed
    data/ng_names.json
    scripts/{mock_upstream,bench_scrub,eval_recall}.py
    tests/{test_patterns,test_session_map,test_reinjector,test_roundtrip,test_no_leak}.py
  demo/{agent.py,prompts.json,labeled_eval.jsonl}
  frontend/                     # create-next-app: App Router, TypeScript, Tailwind, shadcn/ui
    app/page.tsx
    components/{TopBar,LiveFeed,WireView,EntityChart}.tsx
    lib/{types.ts,useEventSource.ts}
```

## 11. Pre-built / hardcoded assets (do not make the AI invent UI)

- UI: shadcn/ui `card`, `badge`, `table`, `scroll-area`, `button`, `chart`. No custom component library.
- `demo/prompts.json`: 12 prompts (8 normal, 4 adversarial: digits spaced out, ALL CAPS names, pidgin, PII inside a tool result).
- `CUSTOMERS` array of 5 fake customers inside `demo/agent.py`.
- `data/ng_names.json`: about 150 seed first names and surnames.
- `POST /v1/aegis/_seed`: 20 synthetic Telemetry Events for an instantly populated dashboard.

## 12. Acceptance checklist

1. `python demo/agent.py` completes a two-tool task through Aegis against mock Upstream; the AGENT SAW panel has real values, UPSTREAM SAW has only Placeholders.
2. Official OpenAI SDK works with only `base_url` changed, including `stream=True`.
3. `pytest` green, including `test_no_leak` (0 leaks) and every row of the 7.1 test table.
4. Second turn of the same conversation reuses the same Placeholder for the same person.
5. Killing Redis mid-demo yields 503, not a leak. Flushing Redis between request and reply yields `state_loss`.
6. Dashboard updates within 1 s of a request and never shows pre-scrub text.
7. Same flow works against the real Upstream with one `.env` change.

## 13. Pitch map (judging: six criteria, 10 points each, plus 5 bonus)

| Criterion | Proof to show |
|---|---|
| Innovation | Reversible, session-stable pseudonymization for agents with Nigerian entities |
| Relevance | Live NDPA exposure problem for banks and hospitals; judges from payments will recognise BVN/NIN |
| Technical execution | Round trip with tool calls, leak test number, measured recall and overhead |
| Scalability | Stateless proxy plus Redis; per-entity and per-seat pricing; in-country deployment is the roadmap |
| Teamwork | Named owners: Proxy/Reinjector, Scrubber/Eval, Dashboard/Demo, Pitch/Deck |
| Presentation | 3 min story, 2 min live demo (mock Upstream as fallback), 3 min Q&A; backup video recorded |

One-sentence answers for the judges' table questions are in `README.md`.
