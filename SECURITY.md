# Security Policy

Aegis sits between applications and external models, so we take reports seriously.

## Reporting a vulnerability

Report privately: GitHub **Security → Report a vulnerability** on this repository (private advisory), or email **security@aegisproxy.dev**. Please do not open a public issue for security problems.

Include: affected version or commit, steps to reproduce, impact, and any proof of concept. **Use synthetic data only. Never send us real personal data.**

We aim to acknowledge within 3 working days, give an initial assessment within 7 days, and agree a disclosure date with you. We will credit you unless you prefer otherwise. There is no bug bounty yet.

## In scope (report privately)
- Any path that sends pre-scrub text or the Session Map to Upstream, logs, metrics, telemetry or the dashboard.
- Cross-tenant access to Session Maps, Wire Taps, events or stats.
- Authentication, ticket or rate-limit bypass; SSRF through `UPSTREAM_BASE_URL`; injection through placeholders; denial of service from a small request; secrets exposure; vulnerable dependencies reachable in the shipped image.

## Not security reports (use the public "Detection gap" issue form, synthetic examples only)
- An identifier the Scrubber misses or a false positive. Detection is probabilistic for names and bounded for obfuscation; see "What Aegis does not do" in the README.

## Out of scope
Social engineering, volumetric DoS, findings that need a malicious operator of the deployment, issues in Upstream providers, and unsupported versions.

## Supported versions
The latest release and `main`. Before 1.0 we do not backport fixes.

## Safe harbor
Good-faith research that follows this policy, avoids privacy violations and service disruption, and uses only your own deployment and synthetic data will not be pursued by the maintainers.

## Deployment guidance
Run Aegis inside your own network behind TLS, set `AEGIS_KEYS_FILE`, never expose Redis, and treat the Wire Tap as sensitive operational data.

## Development & Supply Chain Security

Aegis enforces strict branch protection rules. The default branch requires passing CI/CD status checks and blocks force-pushes to maintain an immutable audit log of all source code changes.

The required GitHub Actions checks run the backend test and leak-test suite, the deterministic pattern benchmark, held-out recall evaluation, frontend and marketing-site builds, dependency audits, and secret scanning. Repository maintainers should keep the `Protect main` ruleset active and require those checks before a Pull Request can merge.
