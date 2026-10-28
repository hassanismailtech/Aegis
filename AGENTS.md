# AGENTS.md: rules for every Aegis task

1. `docs/PRD.md` is the source of truth. Read it before coding. If it conflicts with your habits, docs/PRD.md wins.
2. Use the glossary words exactly: Placeholder, Session Map, Scrubber, Reinjector, Upstream, Wire Tap. Never call a Placeholder a "token" or "tag".
3. Build only the step you were given. Do not add routes, auth, databases, settings or extra pages. Unspecified detail: choose the simplest option and log it under `ASSUMPTIONS` in `NOTES.md`.
4. Stack: Python 3.12, uv, FastAPI, httpx (async), redis-py asyncio, Pydantic v2, pydantic-settings, gliner, pytest. Frontend: Next.js (latest stable) App Router, TypeScript, Tailwind, shadcn/ui, Recharts via shadcn chart. Do not use Pages Router, Python 3.9-era typing, Pydantic v1 syntax or `requests` in the proxy.
5. Before using any library API you are not certain about, check current docs via the Context7 MCP. Do not guess signatures.
6. Never block the event loop. CPU-bound work (GLiNER) goes to a thread pool.
7. Never log, print, persist or send to the frontend any pre-scrub text or the Session Map contents. Logs may contain counts, types, ids and timings only.
8. Redis has no persistence and no volume. Do not add Postgres, SQLite or files for state.
9. Every module gets tests in the same step. Run them and paste the result before saying "done". Do not claim success without running the commands in the step's "Done when".
10. Keep commits small and frequent with clear messages (the public commit history is judged). Do not commit `.env`.
11. Terse code, no dead code, no TODO placeholders, no sample data beyond what docs/PRD.md section 11 lists.
12. When finished, reply with: files changed, commands run with real output, ASSUMPTIONS added. Nothing else.
13. Public text (README, landing, docs) may only contain claims marked OK in docs/CLAIMS.md. Numbers must come from docs/metrics.txt.
14. Logs, exceptions, metrics and traces must never contain request or response bodies, placeholders' real values, or Authorization headers. Add a test when you add logging.
15. Treat all inbound text as hostile. Never use user text in a regex without escaping, in a Redis key without hashing, or in a log line.
16. Do not add dependencies without stating why and checking the license (Apache-2.0/MIT/BSD only).