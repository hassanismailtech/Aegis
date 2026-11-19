# Release preparation: target v0.4.0

**Unreleased.** Package metadata identifies the planned version; it is not evidence of a GitHub release or available container image. No release date, tag, registry publication, package-visibility change or repository rename is performed by this preparation task. Product and code identifiers remain Aegis.

The existing [publish workflow](../.github/workflows/publish.yml) publishes on pushes to `main`, version tags and manual dispatch. It does not wait for the separate CI/evaluation workflows. **Merging to `main` can therefore publish an image.** Do not merge, tag or dispatch as part of preparation; the publishing behavior and gates need explicit review before those actions.

## Prepared release-note copy

Use the [Unreleased changelog](../CHANGELOG.md#unreleased) as the draft source. It covers startup binding, the opt-in scrub-only playground, website truth fixes, operating guides and verification jobs. The playground has no restored reply or Telemetry Events. Authentication is off unless `AEGIS_KEYS_FILE` is configured; the default Compose stack remains unauthenticated local development with host-loopback publishing.

There is no rebrand note claiming completed work: repository naming, mailboxes and domain setup remain separate. Retain the existing configuration/header/CLI/Redis identifiers. Audit hardening remains deferred; see the [security model](security-model.md) and [limitations](limitations.md).

## Required gates before a release can be authorized

- [ ] Identify the exact reviewed commit containing all intended task branches. Confirm its package version and lockfile agree, with no accidental dependency changes.
- [ ] Obtain passing CI and evaluation results for that commit, including the complete backend suite with mandatory real-Redis cases. Earlier successful backend/container jobs do not establish that the current release candidate passed.
- [ ] Obtain passing image build, unauthenticated wildcard-refusal and Compose-health checks. Existing container CI covers its runner architecture; the publishing workflow requests both `linux/amd64` and `linux/arm64`, so validate the intended publication platforms separately.
- [ ] Resolve the recorded Next.js build security gate and dependency-audit failures through a separately scoped, reviewed dependency fix. No bypass or downgrade is part of release preparation.
- [ ] Complete a fresh-checkout local quickstart and a synthetic chat-client/SDK walkthrough. Check normal Proxy behavior and scrub-only playground behavior separately.
- [ ] Review public claims, configuration examples and the actual image identity. Use `SECLUME_IMAGE` in deployment instructions; do not invent a registry namespace after a future rebrand.
- [ ] Obtain explicit authorization for the publishing trigger, release tag, release creation and any package visibility/access change. The current standing push authorization covers task branches, not publication.

These boxes are intentionally unchecked. See [NOTES.md](../NOTES.md) for actual command results and limitations; a pushed branch is not a passing release gate.

## Assets and later publication checks

When release creation is authorized, prepare attachments from the exact approved commit: [docker-compose.yml](../docker-compose.yml) and [.env.example](../.env.example). The example contains empty credential values; do not attach a local `.env`, key file, audit database, model cache or request transcript. Include the existing [licence](../LICENSE) and [configuration guide](configuration.md) in the release references.

Only after the gates and authorization are satisfied should the changelog move to a dated release section and its comparison links be updated. Confirm the version tag points to the reviewed commit, record the published image digest, and test anonymous access from an isolated client configuration without logging out or changing the user's existing registry account. A local wheel build does not prove container/platform compatibility or anonymous image availability.

Deployment preparation is a later task. No host, DNS, TLS certificate, Caddy hostname or live service is configured here.
