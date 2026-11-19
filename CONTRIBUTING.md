# Contributing to Seclume

Thanks for helping. Seclume handles sensitive data paths, so we are strict about tests and claims.

## Ground rules
- **Never put real personal data** in issues, PRs, tests, fixtures or screenshots. Synthetic only.
- **DCO:** sign every commit (`git commit -s`). By signing you certify the Developer Certificate of Origin (developercertificate.org).
- **Conventional commits** (`feat(scope): ...`, `fix:`, `docs:`, `test:`, `chore:`). They drive the changelog.
- **Claims policy:** public text (README, docs, site) may only state what `docs/CLAIMS.md` marks OK, and numbers must come from `docs/metrics.txt`.
- **Licensing:** source code, configuration, and code blocks are contributed under Apache-2.0. Original prose and diagrams in `docs/` are contributed under CC BY 4.0; see `LICENSE` and `docs/LICENSE.md`.
- AI-assisted contributions are welcome. You are responsible for the result: review every line, run the tests.

## Dev setup

The complete backend suite requires real Redis and a checksum-verified Caddy executable supplied through `CADDY_BIN`. See [the local quickstart](docs/quickstart.md) for prerequisites; CI runs native Redis on Ubuntu. Missing integration prerequisites are failures, not optional skips.

```bash
docker compose up -d redis mock-upstream
cd backend && uv sync && uv run pytest -q
cd ../frontend && npm ci && npm run build
```
Before a PR: `uv run pytest -q`, `uv run python scripts/eval_heldout.py --floor 0.85`, `npm run lint && npm run build`.

## Good first contributions
- **New identifier pack** (Ghana Card, Kenya national ID, South Africa ID with checksum, etc.): create `backend/packs/<cc>/` with patterns, validators, a gazetteer if relevant, unit tests, and a labelled synthetic evaluation file. Cite the official format specification in the PR.
- Detection gaps and false positives from the "Detection gap" issue form.
- Docs, examples for agent frameworks, translations.

## PR checklist
Tests added and passing; no new logging of bodies or secrets; claims policy respected; CHANGELOG updated under *Unreleased*; new dependencies justified and licence-checked (Apache-2.0, MIT or BSD).

## Pull Request Process

Submit changes through Pull Requests and verify passing automated checks before merging. Repository administrators must configure and verify the intended GitHub rules; source files alone do not prove that direct pushes are blocked.

Use a short-lived branch named `feat/<area>-<summary>`, `fix/<area>-<summary>`, `docs/<summary>`, or `chore/<summary>`. Open the PR against `main`, use Conventional Commits, sign commits with the DCO, and request review from the code owners. Review the `ci` backend, containers, frontend, website, secrets and claims jobs, plus `eval`. Configure the intended required checks in GitHub settings and do not override a failed or skipped required check. A main merge can trigger the separate image-publishing workflow.

## Conduct and security
See `CODE_OF_CONDUCT.md`. Report vulnerabilities privately per `SECURITY.md`.
