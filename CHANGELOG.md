# Changelog

All notable changes are documented here. Format: [Keep a Changelog](https://keepachangelog.com/en/1.1.0/). Versioning: [Semantic Versioning](https://semver.org/). Until 1.0, minor versions may include breaking changes; they are always listed under **Changed** or **Removed**.

## [Unreleased]

Planned target: **0.4.0**. These changes are prepared on task branches and have not been released. See the [release checklist](docs/release-checklist.md) for verification and publication gates.

### Added
- Disabled-by-default synthetic playground API with atomic Redis rate limiting, temporary Session Map cleanup, scrubbed output and a simulated reply. Playground requests call no Upstream and emit no Telemetry Events.
- Minimal playground page with approved synthetic examples, highlighted Placeholders, counts, measured scrub time, actual full/lite mode, and safe error states. Submissions require an explicitly configured public API URL.
- CI checks for native-Redis backend tests, image startup refusal, Compose health, website client tests, and public claims lint.
- Local quickstart, complete Python configuration reference, security model, and limitations guides.

### Fixed
- Wildcard addresses no longer count as loopback for startup checks. `BIND_HOST` defaults to `127.0.0.1`; the Docker entrypoint uses that setting. Non-loopback startup requires tenant keys or the explicit development bypass; tenant keys require a dedicated ticket secret.
- Public wording now qualifies Session continuity, synthetic evaluation evidence, storage, and pilot availability. Removed unshipped roadmap stub pages and corrected the source-code licence footer.

### Changed
- Python package metadata is aligned to the planned release version; dependency requirements and locked third-party versions are unchanged.
- The repository/product name remains Aegis. Existing `AEGIS_*` settings, `X-Aegis-*` headers, CLI name and Redis prefixes are unchanged; no rebrand or registry-image publication is claimed.

## [0.3.0] - 2026-10-28
### Added
- Anthropic Messages API (`POST /v1/messages`), non-streaming and streaming, scrubbing `system`, text blocks, `tool_use.input` and `tool_result` content.
- True SSE streaming for OpenAI and Anthropic with a hold-back buffer, so Placeholders split across chunks are still reinjected. Supports `n > 1`.
- NUBAN check-digit validation, held-out evaluation set (220 sentences, synthetic) with a PERSON recall floor in CI, and model fast paths (skip gate, bounded in-memory cache, opt-in ONNX int8).
### Changed
- `stream: true` now relays the real Upstream stream. The earlier pseudo-stream is removed.

## [0.2.0] - 2026-10-27
### Added
- Per-tenant API key authentication (hashed keys), request size and message limits, per-tenant rate limiting.
- Structured request logging with a test proving no planted PII reaches logs.
- Short-lived signed tickets for the dashboard event stream.
- CPU Docker image with the model baked in, `docker compose up` stack, GHCR publish workflow, `aegis doctor` CLI.
### Changed
- Detection refactored into composable detector packs (`packs/ng`).

## [0.1.0] - 2026-10-24
### Added
- PAU 24-Hour Hackathon build: OpenAI-compatible proxy, Nigerian entity scrubbing (patterns, gazetteer, GLiNER), Redis Session Map, Reinjector, Wire Tap, telemetry stream, dashboard, mock Upstream, SDK demo agent, leak test.

[Unreleased]: https://github.com/hassanismailtech/Aegis/compare/v0.3.0...HEAD
[0.3.0]: https://github.com/hassanismailtech/Aegis/releases/tag/v0.3.0
[0.2.0]: https://github.com/hassanismailtech/Aegis/releases/tag/v0.2.0
[0.1.0]: https://github.com/hassanismailtech/Aegis/releases/tag/v0.1.0
