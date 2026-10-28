# Marketing site and dashboard integration

## Decision

Run two Vercel projects from this monorepo:

| Surface | Vercel project | Root directory | Canonical host | Job |
|---|---|---|---|---|
| Marketing | `aegis` | `website` | apex domain | Public product, trust, company, legal-review, and documentation-entry routes |
| Dashboard | `aegis-app` | `frontend` | `app.<domain>` | Authenticated or deployment-scoped operational control plane |

The marketing site must never proxy dashboard API traffic or render the dashboard in an iframe. The dashboard calls the customer-controlled Aegis Proxy directly through `NEXT_PUBLIC_AEGIS_URL`.

## Why this is needed

The Vercel project named `aegis` is currently serving the marketing build: its latest production deployment is commit `082a350` (`website` scaffold). Earlier production history contains the dashboard commit `b1de40f`. Switching a single project between monorepo roots makes rollback, headers, environment variables, and UX ownership ambiguous.

## Cross-link contract

Set these public environment variables in production and preview deployments:

| Project | Variable | Value |
|---|---|---|
| `aegis` marketing | `NEXT_PUBLIC_APP_URL` | `https://app.<domain>` |
| `aegis-app` dashboard | `NEXT_PUBLIC_MARKETING_URL` | `https://<domain>` |
| `aegis` marketing | `NEXT_PUBLIC_SITE_URL` | `https://<domain>` |
| `aegis-app` dashboard | `NEXT_PUBLIC_AEGIS_URL` | Customer-controlled Aegis Proxy URL |

The marketing navigation displays **Dashboard** only when `NEXT_PUBLIC_APP_URL` is configured. The dashboard displays **Aegis site** only when `NEXT_PUBLIC_MARKETING_URL` is configured. This makes the cross-link explicit across production and preview without hard-coding a transient Vercel URL.

## Rollout

1. Keep the existing `aegis` Vercel project on root directory `website`; do not point it back at `frontend`.
2. Create `aegis-app` from the same GitHub repository with root directory `frontend` and its own production and preview environments.
3. Deploy the dashboard project without assigning the apex domain. Verify that it connects only to its configured Aegis Proxy and never shows pre-scrub text or Session Map content.
4. Assign the production hosts: apex or `www` for marketing, `app` subdomain for the dashboard. Add the three cross-link variables above in both production and preview scopes.
5. Verify browser navigation in both directions, session behaviour, CSP/CORS rules for the dashboard-to-Proxy connection, and the marketing redirects (`/security`, `/privacy`, `/terms`, `/acceptable-use`).
6. After a stable observation period, retire only obsolete aliases or the previous dashboard deployment. Do not delete the project history as part of this rollout.

## UI/UX contract

- Both apps use dark `zinc-950` foundations, `zinc-900` surfaces, cyan/mint accents, Geist Sans, Geist Mono metrics, 1px rings, and 150ms transitions.
- Marketing explains the system and routes visitors to Playground or the dashboard. The dashboard remains deliberately operational: live safe telemetry, entity counts, timings, and post-scrub Wire Tap data.
- The product boundary remains visible everywhere: no pre-scrub text or Session Map values are shown in marketing, dashboard, logging, or cross-origin telemetry.
- Marketing has no Vercel Web Analytics or Speed Insights import in the root layout. Do not introduce it into the dashboard without a separate privacy review and cookie-notice update.

## Required before public legal/contact launch

Provide the legal entity name, registered address, privacy contact, general contact path, effective date, analytics/processors inventory, and counsel-approved policy text. The current legal and contact routes deliberately state publication review rather than pretending those facts are known.
