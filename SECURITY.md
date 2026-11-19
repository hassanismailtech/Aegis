# Security Policy

Seclume sits between applications and external models, so we take reports seriously.

## Reporting a vulnerability

Report privately to [security@seclume.tech](mailto:security@seclume.tech) or through [GitHub Security → Report a vulnerability](https://github.com/hassanismailtech/seclume/security/advisories/new) (private advisory). Please do not open a public issue for security problems.

Include: affected version or commit, steps to reproduce, impact, and any proof of concept. **Use synthetic data only. Never send us real personal data.**

We aim to acknowledge within 3 working days, give an initial assessment within 7 days, and agree a disclosure date with you. We will credit you unless you prefer otherwise. There is no bug bounty yet.

## In scope (report privately)
- Any path that sends pre-scrub text or the Session Map to Upstream, logs, metrics, telemetry or the dashboard.
- Cross-tenant access to Session Maps, Wire Taps, events or stats.
- Authentication, ticket or rate-limit bypass; SSRF through `UPSTREAM_BASE_URL`; injection through placeholders; denial of service from a small request; secrets exposure; vulnerable dependencies reachable in the shipped image.

## Not security reports (use the public "Detection gap" issue form, synthetic examples only)
- An identifier the Scrubber misses or a false positive. Detection is probabilistic for names and bounded for obfuscation; see the [limits and evidence guide](docs/limitations.md).

## Out of scope
Social engineering, volumetric DoS, findings that need a malicious operator of the deployment, issues in Upstream providers, and unsupported versions.

## Supported versions
The latest release and `main`. Before 1.0 we do not backport fixes.

## Safe harbor
Good-faith research that follows this policy, avoids privacy violations and service disruption, and uses only your own deployment and synthetic data will not be pursued by the maintainers.

## Deployment guidance
Run Seclume inside your own network behind TLS, set `AEGIS_KEYS_FILE`, never expose Redis, and treat the Wire Tap as sensitive operational data.

## Development & Supply Chain Security

Repository administrators should require reviewed Pull Requests and passing CI/evaluation checks, and restrict direct pushes, force-pushes and deletions. These are GitHub settings to verify; workflow files alone do not establish their enforcement. Repository history is not an administrator-resistant audit record.

GitHub Actions workflows configure the backend test and leak-test suite, deterministic pattern benchmark, synthetic evaluation, frontend and marketing-site builds, dependency audits, secret scanning and claims lint. Maintainers should verify and require the appropriate checks before merging. Image publication is a separate workflow triggered by main/tag pushes or manual dispatch; it does not depend on CI/evaluation completion.
