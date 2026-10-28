# Contributing to Aegis

Thanks for helping. Aegis handles sensitive data paths, so we are strict about tests and claims.

## Ground rules
- **Never put real personal data** in issues, PRs, tests, fixtures or screenshots. Synthetic only.
- **DCO:** sign every commit (`git commit -s`). By signing you certify the Developer Certificate of Origin (developercertificate.org).
- **Conventional commits** (`feat(scope): ...`, `fix:`, `docs:`, `test:`, `chore:`). They drive the changelog.
- **Claims policy:** public text (README, docs, site) may only state what `docs/CLAIMS.md` marks OK, and numbers must come from `docs/metrics.txt`.
- AI-assisted contributions are welcome. You are responsible for the result: review every line, run the tests.

## Dev setup
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

## Conduct and security
See `CODE_OF_CONDUCT.md`. Report vulnerabilities privately per `SECURITY.md`.
