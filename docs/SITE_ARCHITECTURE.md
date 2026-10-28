# Aegis site architecture & mega-menu blueprint

> **Status:** Information architecture only. No page copy. Claims on shipped pages must stay within `docs/CLAIMS.md` (OK rows only). Numbers from `docs/metrics.txt`.
>
> **Inputs used:** `docs/PRD.md`, `docs/DESIGN.md`, `docs/CLAIMS.md`, `README.md`, `SECURITY.md`, `NOTES.md`, and (private, do not commit contents elsewhere) `private/WEBSITE_DOCS_ACCESS_PLAN.md`, `private/STRATEGY.md`, `private/LANDING_COPY.md`.
>
> **Nav modes:** `LANDING_COPY.md` defines a **launch chrome** (How it works · Evidence · Deploy · Docs · GitHub + Design partner CTA). This blueprint keeps that as the minimal header for v0 launch and expands it into an OpenAI-class **mega-menu** for the venture-scale site. Cloud / Enterprise items are **commercial / roadmap surfaces** aligned with STRATEGY §6 open-core vs paid hypotheses—not claims that those capabilities ship in Compose today.
>
> **Hard product rule (STRATEGY §2):** Aegis must run inside the customer boundary (VPC, on-prem, or a **Nigeria-hosted** managed instance). Never market an offshore hosted proxy that receives raw PII.

---

## 1. IA principles

| Principle | Implication |
|---|---|
| Dual audience | Platform engineers (Tobi) and DPOs / compliance (Femi) get parallel paths under Solutions and Trust. DPCOs are a channel (influencer), not only end buyers. |
| Open source vs Cloud | Product mega-menu splits **self-hosted open core** from **paid / Nigeria-hosted managed**. Never present Cloud items as if they are in the OSS Quickstart. |
| In-boundary only | Managed Nodes = Nigeria-hosted or customer-VPC operated. No `proxy.aegis.dev`-style offshore PII path (`LANDING_COPY` / STRATEGY). |
| Evidence over assurance | Trust pages explain architecture, methodology, and frameworks. Never H1 or describe as “NDPA-compliant” / “legal” / “guarantees” (`CLAIMS.md`, STRATEGY §2–3). |
| Glossary lock | Use Placeholder, Session Map, Scrubber, Reinjector, Upstream, Wire Tap exactly. Never “token” or “tag” for Placeholders. |
| Docs vs marketing | Marketing site (`website/`) on Vercel; docs as Docusaurus in `docs-site/` → `docs.<domain>` (WEBSITE plan §3–4). Playground is no-login, synthetic data only (`POST /v1/playground/scrub`). |
| Access model | Public Playground (no accounts) · Invited design partners (access code + BFF cookie) · Self-hosted production (tenant keys; SSO later). Skip Clerk/Auth0 for now. |
| Footer = liability + ops | Product / Community / Support / Company columns (WEBSITE plan §6) plus legal bar: Privacy, Terms, DPA, Acceptable Use, Cookies, License. |

### URL conventions

- Marketing: kebab-case under topical roots (`/product/...`, `/solutions/...`, `/trust/...`, `/company/...`). Short aliases from W1 stubs (`/security` → `/trust/security`, `/privacy` → `/legal/privacy`) may redirect.
- Docs: prefer host `docs.<domain>` (Docusaurus); path form `/docs/...` remains valid in nav JSON for monorepo preview.
- App surfaces: `/playground` (public), invited dashboard via BFF (not a marketing mega-menu item until partners exist).
- Legal: `/legal/...` (and short aliases `/privacy`, `/terms`, `/acceptable-use`).
- Utility: `/404`, `/sitemap.xml`, `/robots.txt`, `/.well-known/security.txt`, press kit.
- External: GitHub, Status, Community — marked `external` in nav JSON.

---

## 2. Top-level navigation (chrome)

| Label | Type | Default href |
|---|---|---|
| Product | Mega-menu | `/product` |
| Solutions | Mega-menu | `/solutions` |
| Developers | Mega-menu | `/developers` |
| Trust & Security | Mega-menu | `/trust` |
| Company | Mega-menu | `/company` |
| Docs | Text link (optional duplicate of Developers → Documentation) | `/docs` |
| GitHub | Icon / text (external) | `https://github.com/...` *(repo URL as published)* |
| Playground | Primary CTA | `/playground` |
| Contact / Design partners | Secondary CTA (Company) | `/company/design-partners` |

---

## 3. Mega-menu structure (information design)

### 3.1 Product

**Layout:** two columns + right rail “Start here”.

| Column | Items |
|---|---|
| **Open Source** | Overview · Proxy · Scrubber · Wire Tap · Session Map & Reinjector · Dashboard |
| **Cloud / Enterprise** | Overview · Nigeria-hosted Managed Nodes · Audit & transfer-record exports · Multi-tenant policy / SSO · Jurisdiction packs · HA / Failover · Support SLAs |
| **Start here** | Quickstart · Compare OSS vs Cloud · Design partners *(no public prices yet per WEBSITE plan)* |

### 3.2 Solutions

**Layout:** two columns (Industry · By role) + featured use-case strip.

| Column | Items |
|---|---|
| **By industry** | Banking · Healthcare · Fintech · Public sector *(optional)* |
| **By role** | Platform Engineers · DPOs & Compliance · Security / AppSec · AI / Agent builders |
| **Featured** | Agent tool-call boundary · Cross-border LLM use · Evidence for audits |

### 3.3 Developers

**Layout:** three columns (Build · Reference · Community).

| Column | Items |
|---|---|
| **Build** | Quickstart · Integration (OpenAI SDK) · Integration (Anthropic SDK) · Deploy (Docker / VPC) · Playground |
| **Reference** | Documentation home · API Reference · Entity types · Configuration · Failure policy |
| **Community** | GitHub · Contributing · Discussions / Discord · Changelog · Support |

### 3.4 Trust & Security

**Layout:** two columns + “Report a vulnerability” CTA.

| Column | Items |
|---|---|
| **Architecture & proof** | Security Architecture · Wire Tap & evidence · What Aegis does not do · Claims & Methodology |
| **Operations & frameworks** | Subprocessors · Status · Compliance Frameworks (NDPA 2023, GAID 2025) · Responsible disclosure |
| **CTA** | Report a vulnerability → `/trust/security` or SECURITY.md flow |

### 3.5 Company

**Layout:** single wide column + blog highlight.

| Column | Items |
|---|---|
| **Company** | About · Blog · Changelog · Contact · Design Partner Program · Careers *(optional stub)* |
| **Highlight** | Latest changelog entry or design-partner brief |

---

## 4. Complete page inventory

For each row: **URL** · **H1** · **Purpose (1 sentence)**.  
`Surface`: `shipped` = backed by current OSS product; `roadmap` = Cloud / commercial narrative; `legal` = required policy; `docs` = documentation.

### 4.0 Global & entry

| URL | H1 | Purpose | Surface |
|---|---|---|---|
| `/` | Aegis | Primary landing: problem, core loop, evidence teaser, Quickstart CTA, design-partner CTA. | shipped |
| `/pricing` | Pricing | Redirect or soft page: no public prices yet; point to Design Partner Program (WEBSITE plan §5). | roadmap |
| `/sitemap` | Sitemap | Human-readable index; pair with `/sitemap.xml`. | shipped |
| `/press` | Press & brand kit | Logos and naming rules once trademark/domain checks clear (STRATEGY §6). | shipped |
| `/.well-known/security.txt` | *(file)* | Machine-readable disclosure contact per WEBSITE plan §5. | shipped |

### 4.1 Product — hubs & open source

| URL | H1 | Purpose | Surface |
|---|---|---|---|
| `/product` | Product | Hub comparing Open Source control plane components and Cloud / Enterprise offerings. | shipped |
| `/product/open-source` | Open Source | Overview of the self-hosted Proxy, Scrubber, Session Map, Reinjector, Wire Tap, and dashboard. | shipped |
| `/product/proxy` | Proxy | Explain the OpenAI- and Anthropic-compatible Proxy path (`base_url` swap) and request lifecycle. | shipped |
| `/product/scrubber` | Scrubber | Describe layered detection (patterns, gazetteer, GLiNER) and Nigerian entity pack scope. | shipped |
| `/product/wire-tap` | Wire Tap | Position the Wire Tap as post-scrub proof of what Upstream received—never pre-scrub text. | shipped |
| `/product/session-map` | Session Map & Reinjector | Explain ephemeral Redis Session Maps, stable Placeholders, and reinjection behaviour including `state_loss`. | shipped |
| `/product/dashboard` | Dashboard | Describe the live telemetry UI (counts, timings, Wire View) available with the open-source stack. | shipped |
| `/product/compare` | Open Source vs Cloud | Side-by-side responsibilities: self-host vs managed nodes, audit exports, failover. | roadmap |

### 4.2 Product — Cloud / Enterprise

| URL | H1 | Purpose | Surface |
|---|---|---|---|
| `/product/cloud` | Cloud & Enterprise | Commercial hub for paid open-core add-ons and **Nigeria-hosted** managed instances (processor posture, DPA)—never an offshore raw-PII proxy. | roadmap |
| `/product/cloud/managed-nodes` | Managed Nodes | Nigeria-hosted or customer-VPC operated nodes (upgrades, health); Aegis remains inside the data boundary. | roadmap |
| `/product/cloud/audit-exports` | Audit Exports | Transfer-record / DPIA-input / hash-chained audit exports for DPO and DPCO workflows (STRATEGY §6). | roadmap |
| `/product/cloud/multi-region-failover` | Multi-Region Failover | HA / Helm / failover hypotheses for managed or self-hosted enterprise; Session Map semantics stay explicit. | roadmap |
| `/product/cloud/tenant-controls` | Tenant Controls | Multi-tenant policy engine, per-tenant keys, SSO/RBAC (roadmap) on top of OSS auth/limits. | roadmap |
| `/product/cloud/jurisdiction-packs` | Jurisdiction Packs | Venture-scale packs beyond Nigeria (Ghana, Kenya, POPIA, etc.)—nav stub until packs exist. | roadmap |
| `/product/cloud/support` | Enterprise Support | Support channels and SLA tiers once commercial support exists (no invented uptime %). | roadmap |

### 4.3 Solutions — hubs & industry

| URL | H1 | Purpose | Surface |
|---|---|---|---|
| `/solutions` | Solutions | Hub routing visitors by industry and role to the same core boundary story. | shipped |
| `/solutions/banking` | Banking | Frame BVN / NUBAN / customer-name exposure reduction for bank agent workloads. | shipped |
| `/solutions/healthcare` | Healthcare | Frame patient-identifier and staff-name exposure reduction for clinical agent pilots. | shipped |
| `/solutions/fintech` | Fintech | Frame account, phone, and KYC-field exposure reduction for product and ops agents. | shipped |
| `/solutions/public-sector` | Public sector | Optional lane for agencies evaluating cross-border model use with Nigerian identifiers. | shipped |

### 4.4 Solutions — by role & featured

| URL | H1 | Purpose | Surface |
|---|---|---|---|
| `/solutions/platform-engineers` | For Platform Engineers | “Change `base_url`” integration story, Docker deploy, SDK smoke, failure policy. | shipped |
| `/solutions/dpo-compliance` | For DPOs & Compliance | Evidence story: Wire Tap, leak test, methodology link—reduces exposure, not legal advice. | shipped |
| `/solutions/security` | For Security & AppSec | Threat model summary, fail-closed scrub, logging redaction, disclosure path. | shipped |
| `/solutions/ai-builders` | For AI & Agent Builders | Tool-call / tool-result scrubbing and streaming reinjection for agent stacks. | shipped |
| `/solutions/agent-tool-calls` | Agent tool-call boundary | Deep dive on scrubbing `tool_calls` arguments and tool results before Upstream. | shipped |
| `/solutions/cross-border-llm` | Cross-border LLM use | Problem framing for offshore Upstream APIs and data-minimisation at the boundary. | shipped |
| `/solutions/audit-evidence` | Evidence for audits | How telemetry counts, Wire Tap, and (roadmap) audit exports support internal reviews. | shipped |

### 4.5 Developers

| URL | H1 | Purpose | Surface |
|---|---|---|---|
| `/developers` | Developers | Developer hub linking Quickstart, docs, API, Playground, and community. | shipped |
| `/developers/quickstart` | Quickstart | Two-minute path: `docker compose up`, demo agent, optional dashboard. | shipped |
| `/playground` | Playground | No-login demo (`PLAYGROUND_ENABLED`); synthetic data only; scrub + Wire View + simulated reinjected reply; no Upstream LLM cost. | shipped |
| `/developers/openai` | OpenAI SDK integration | Official OpenAI SDK `base_url` integration, streaming, and tools. | shipped |
| `/developers/anthropic` | Anthropic SDK integration | Official Anthropic `/v1/messages` path, streaming, and tools. | shipped |
| `/developers/deploy` | Deploy | Self-host guidance: Docker, private network, TLS gateway, Redis ephemeral posture. | shipped |
| `/developers/community` | Community | Links to GitHub, contributing, code of conduct, and support channels. | shipped |

### 4.6 Documentation (Developers → Documentation tree)

| URL | H1 | Purpose | Surface |
|---|---|---|---|
| `/docs` | Documentation | Versioned docs home with search entry and task-oriented TOC. | docs |
| `/docs/introduction` | Introduction | What Aegis is, glossary, and honest limitations pointer. | docs |
| `/docs/concepts` | Concepts | Proxy, Scrubber, Placeholder, Session Map, Reinjector, Upstream, Wire Tap. | docs |
| `/docs/quickstart` | Docs Quickstart | Canonical install and first request (mirrors `/developers/quickstart` with more depth). | docs |
| `/docs/configuration` | Configuration | Environment variables and operational toggles (auth, limits, NER, Upstream). | docs |
| `/docs/entities` | Entity types | PHONE, BVN, NIN, ACCOUNT_NO, EMAIL, PERSON detection notes. | docs |
| `/docs/failure-policy` | Failure policy | Fail-closed scrub/state vs reinjection `state_loss` behaviour. | docs |
| `/docs/security` | Security guidance | Deployment hardening aligned with `SECURITY.md` (no pre-scrub in logs/UI). | docs |
| `/docs/api` | API Reference | HTTP routes: chat/completions, messages, aegis events/stats/wiretap/ticket. | docs |
| `/docs/api/openai` | OpenAI-compatible API | `POST /v1/chat/completions` contract and response headers. | docs |
| `/docs/api/anthropic` | Anthropic-compatible API | `POST /v1/messages` contract. | docs |
| `/docs/api/telemetry` | Telemetry & Wire Tap API | Events SSE, stats, Wire Tap, seed (synthetic). | docs |
| `/docs/changelog` | Docs changelog | Doc-only change log (product changelog lives under Company). | docs |

### 4.7 Trust & Security

| URL | H1 | Purpose | Surface |
|---|---|---|---|
| `/trust` | Trust & Security | Hub for architecture, methodology, subprocessors, status, and frameworks. | shipped |
| `/trust/architecture` | Security Architecture | Boundary diagram: scrub → Session Map → Upstream → reinject; fail-closed paths. | shipped |
| `/trust/wire-tap` | Wire Tap & evidence | How post-scrub evidence is produced and what it never contains. | shipped |
| `/trust/limitations` | What Aegis does not do | Explicit non-goals: no legal guarantee, no adversarial evasion claim, ephemeral Redis, etc. | shipped |
| `/trust/methodology` | Claims & Methodology | How leak tests and recall evals are run; links to `CLAIMS.md` / `metrics.txt` sourcing rules. | shipped |
| `/trust/subprocessors` | Subprocessors | Processors for marketing site, email routing, and Nigeria-hosted Cloud (OSS self-host has none by default). Disclose offshore marketing processors honestly. | roadmap |
| `/trust/status` | Status | Status for managed offerings (later); OSS users monitor their own deploy. | roadmap |
| `/trust/frameworks` | Compliance Frameworks | Neutral primers on NDPA 2023 and GAID 2025—helps document controls; not certifications. | shipped |
| `/trust/frameworks/ndpa-2023` | NDPA 2023 | Cross-border *context* (s.41 etc.): Aegis as pseudonymisation / minimisation / evidence—not a lawful-transfer silver bullet. | shipped |
| `/trust/frameworks/gaid-2025` | GAID 2025 | Guidance themes (e.g. CAR / DPCO context) mapped at a high level; not legal advice. | shipped |
| `/trust/security` | Security & disclosure | Architecture summary + responsible disclosure (`SECURITY.md`); alias `/security`. | shipped |
| `/trust/open-source-licenses` | Open source & third-party licences | Project license plus third-party notices for the marketing/docs sites. | shipped |
| `/trust/dpia-pack` | DPIA input pack | Reusable DPIA / transfer-record inputs for DPCOs and partners (STRATEGY §5 channel); roadmap content. | roadmap |

### 4.8 Company

| URL | H1 | Purpose | Surface |
|---|---|---|---|
| `/company` | Company | About hub: mission, open-source stance, design partners. | shipped |
| `/company/about` | About Us | Who builds Aegis and why Nigerian-aware agent infrastructure. | shipped |
| `/company/blog` | Blog | Essays and product thinking; every post claim-checked against `CLAIMS.md`. | shipped |
| `/company/blog/[slug]` | *(post title)* | Individual article. | shipped |
| `/company/changelog` | Changelog | User-facing product changes (align with repo `CHANGELOG.md`). | shipped |
| `/company/contact` | Contact | Sales, press, and general inquiry paths. | shipped |
| `/company/design-partners` | Design Partner Program | Recruit banks, fintechs, hospitals for feedback; clear expectations, no fake logos. | shipped |
| `/company/careers` | Careers | Optional hiring page when roles exist. | shipped |

### 4.9 Legal & footer-only

| URL | H1 | Purpose | Surface |
|---|---|---|---|
| `/legal/privacy` | Privacy Policy | How the marketing site (and Cloud, when live) processes personal data. | legal |
| `/legal/terms` | Terms of Use | Terms for website use and, separately referenced, Cloud terms when sold. | legal |
| `/legal/dpa` | Data Processing Addendum | DPA template for Cloud / design-partner processing relationships. | legal |
| `/legal/cookies` | Cookie Notice | Marketing-site cookies / analytics disclosure (none in dashboard per DESIGN.md). | legal |
| `/legal/acceptable-use` | Acceptable Use | Prohibited uses of Playground and hosted services (synthetic data only). | legal |
| `/license` | License | Open-source license summary with link to repository `LICENSE`. | legal |

---

## 5. Footer map

Aligned with WEBSITE plan §6 (Product / Community / Support / Company) plus Trust links under Support. Optional email capture states purpose (design-partner waitlist / updates)—disclosed in Privacy Policy.

### Column A — Product
- Open Source → `/product/open-source`
- Proxy → `/product/proxy`
- Scrubber → `/product/scrubber`
- Wire Tap → `/product/wire-tap`
- Cloud → `/product/cloud`
- Design partners → `/company/design-partners`

### Column B — Community
- GitHub → external
- Docs → `docs.<domain>` / `/docs`
- Playground → `/playground`
- Changelog → `/company/changelog`
- Contributing → `/developers/community`
- Blog → `/company/blog`

### Column C — Support
- Security → `/trust/security`
- Claims & Methodology → `/trust/methodology`
- Frameworks → `/trust/frameworks`
- Subprocessors → `/trust/subprocessors`
- Status → `/trust/status`
- Contact → `/company/contact`

### Column D — Company
- About → `/company/about`
- Contact → `/company/contact`
- Design Partners → `/company/design-partners`
- Press kit → `/press`
- Careers → `/company/careers`

### Bottom bar (required)
- Privacy Policy → `/legal/privacy` (alias `/privacy`)
- Terms of Use → `/legal/terms` (alias `/terms`)
- DPA Template → `/legal/dpa`
- Acceptable Use → `/legal/acceptable-use` (alias `/acceptable-use`)
- Cookie Notice → `/legal/cookies`
- License → `/license`
- © {year} Aegis

---

## 6. User journeys (nav proof)

| Persona | Entry | Primary path | Success |
|---|---|---|---|
| Tobi (platform eng) | `/` or Product → Proxy | Developers → Quickstart → Docs API → Playground | Running Proxy with SDK `base_url` |
| Femi (DPO) | Trust or Solutions → DPO | Methodology → Wire Tap → Frameworks → Design Partners | Understands evidence story; knows non-claims |
| Buyer (enterprise) | Product → Cloud | Managed Nodes → Audit Exports → Contact / Design Partners | Clear OSS vs Cloud split; contact captured |
| Contributor | Developers → Community | GitHub → Contributing → Changelog | Can file detection-gap / security correctly |

---

## 7. shadcn/ui `NavigationMenu` data (JSON)

Feed this object into a typed nav config; render with `@/components/ui/navigation-menu`.  
`description` strings are **menu blurbs**, not page copy. Mark `external: true` for off-site links.  
Replace `GITHUB_URL` and `STATUS_URL` at build time.

```json
{
  "cta": {
    "primary": { "label": "Playground", "href": "/playground" },
    "secondary": { "label": "Design partners", "href": "/company/design-partners" }
  },
  "items": [
    {
      "id": "product",
      "label": "Product",
      "href": "/product",
      "featured": {
        "title": "Start with Open Source",
        "description": "Self-host the Proxy, Scrubber, and Wire Tap with Docker Compose.",
        "href": "/product/open-source",
        "cta": "Explore open source"
      },
      "columns": [
        {
          "title": "Open Source",
          "items": [
            {
              "title": "Open Source overview",
              "href": "/product/open-source",
              "description": "Self-hosted control plane for the AI data boundary."
            },
            {
              "title": "Proxy",
              "href": "/product/proxy",
              "description": "OpenAI- and Anthropic-compatible path; change base_url."
            },
            {
              "title": "Scrubber",
              "href": "/product/scrubber",
              "description": "Nigerian-aware detection into Placeholders."
            },
            {
              "title": "Wire Tap",
              "href": "/product/wire-tap",
              "description": "Exact post-scrub bytes Upstream received."
            },
            {
              "title": "Session Map & Reinjector",
              "href": "/product/session-map",
              "description": "Ephemeral Redis maps and stable Placeholders."
            },
            {
              "title": "Dashboard",
              "href": "/product/dashboard",
              "description": "Live counts, timings, and Wire View."
            }
          ]
        },
        {
          "title": "Cloud / Enterprise",
          "items": [
            {
              "title": "Cloud overview",
              "href": "/product/cloud",
              "description": "Managed operation of the Aegis boundary.",
              "badge": "Roadmap"
            },
            {
              "title": "Managed Nodes",
              "href": "/product/cloud/managed-nodes",
              "description": "Operated nodes with regional placement.",
              "badge": "Roadmap"
            },
            {
              "title": "Audit Exports",
              "href": "/product/cloud/audit-exports",
              "description": "Exportable evidence for DPO workflows.",
              "badge": "Roadmap"
            },
            {
              "title": "Multi-Region Failover",
              "href": "/product/cloud/multi-region-failover",
              "description": "Failover across managed regions.",
              "badge": "Roadmap"
            },
            {
              "title": "Tenant Controls",
              "href": "/product/cloud/tenant-controls",
              "description": "Keys, limits, and isolation controls.",
              "badge": "Roadmap"
            },
            {
              "title": "Enterprise Support",
              "href": "/product/cloud/support",
              "description": "Support channels and commercial SLAs.",
              "badge": "Roadmap"
            }
          ]
        },
        {
          "title": "Compare",
          "items": [
            {
              "title": "OSS vs Cloud",
              "href": "/product/compare",
              "description": "What you run yourself vs what we operate."
            },
            {
              "title": "Pricing",
              "href": "/pricing",
              "description": "Self-host free; Cloud pricing when available."
            }
          ]
        }
      ]
    },
    {
      "id": "solutions",
      "label": "Solutions",
      "href": "/solutions",
      "featured": {
        "title": "Evidence for audits",
        "description": "Wire Tap and methodology for teams that need proof of what left the building.",
        "href": "/solutions/audit-evidence",
        "cta": "See evidence story"
      },
      "columns": [
        {
          "title": "By industry",
          "items": [
            {
              "title": "Banking",
              "href": "/solutions/banking",
              "description": "BVN, NUBAN, and customer-name boundary control."
            },
            {
              "title": "Healthcare",
              "href": "/solutions/healthcare",
              "description": "Reduce identifier exposure in clinical agent pilots."
            },
            {
              "title": "Fintech",
              "href": "/solutions/fintech",
              "description": "Account, phone, and KYC fields at the model edge."
            },
            {
              "title": "Public sector",
              "href": "/solutions/public-sector",
              "description": "Cross-border model use with Nigerian identifiers."
            }
          ]
        },
        {
          "title": "By role",
          "items": [
            {
              "title": "For Platform Engineers",
              "href": "/solutions/platform-engineers",
              "description": "base_url swap, Docker, SDKs, failure policy."
            },
            {
              "title": "For DPOs & Compliance",
              "href": "/solutions/dpo-compliance",
              "description": "Evidence, methodology, and honest limitations."
            },
            {
              "title": "For Security & AppSec",
              "href": "/solutions/security",
              "description": "Fail-closed scrub, logging rules, disclosure."
            },
            {
              "title": "For AI & Agent Builders",
              "href": "/solutions/ai-builders",
              "description": "Tool calls, tool results, and streaming reinjection."
            }
          ]
        },
        {
          "title": "Featured",
          "items": [
            {
              "title": "Agent tool-call boundary",
              "href": "/solutions/agent-tool-calls",
              "description": "Scrub arguments and results before Upstream."
            },
            {
              "title": "Cross-border LLM use",
              "href": "/solutions/cross-border-llm",
              "description": "Minimise regulated data sent offshore."
            },
            {
              "title": "Evidence for audits",
              "href": "/solutions/audit-evidence",
              "description": "Telemetry and Wire Tap for internal review."
            }
          ]
        }
      ]
    },
    {
      "id": "developers",
      "label": "Developers",
      "href": "/developers",
      "featured": {
        "title": "Playground",
        "description": "No-login demo with synthetic data. Agent saw vs Upstream saw.",
        "href": "/playground",
        "cta": "Open Playground"
      },
      "columns": [
        {
          "title": "Build",
          "items": [
            {
              "title": "Quickstart",
              "href": "/developers/quickstart",
              "description": "Compose up, demo agent, optional dashboard."
            },
            {
              "title": "OpenAI SDK",
              "href": "/developers/openai",
              "description": "Official SDK via base_url, streaming, tools."
            },
            {
              "title": "Anthropic SDK",
              "href": "/developers/anthropic",
              "description": "Messages API path with streaming."
            },
            {
              "title": "Deploy",
              "href": "/developers/deploy",
              "description": "Private network, TLS gateway, ephemeral Redis."
            },
            {
              "title": "Playground",
              "href": "/playground",
              "description": "Interactive demo; synthetic PII only."
            }
          ]
        },
        {
          "title": "Reference",
          "items": [
            {
              "title": "Documentation",
              "href": "/docs",
              "description": "Guides, concepts, and configuration."
            },
            {
              "title": "API Reference",
              "href": "/docs/api",
              "description": "Proxy and Aegis operational routes."
            },
            {
              "title": "Entity types",
              "href": "/docs/entities",
              "description": "PHONE, BVN, NIN, ACCOUNT_NO, EMAIL, PERSON."
            },
            {
              "title": "Configuration",
              "href": "/docs/configuration",
              "description": "Environment and runtime toggles."
            },
            {
              "title": "Failure policy",
              "href": "/docs/failure-policy",
              "description": "Fail-closed scrub vs state_loss reinjection."
            }
          ]
        },
        {
          "title": "Community",
          "items": [
            {
              "title": "GitHub",
              "href": "GITHUB_URL",
              "description": "Source, issues, and releases.",
              "external": true
            },
            {
              "title": "Community",
              "href": "/developers/community",
              "description": "Contributing, conduct, and support."
            },
            {
              "title": "Changelog",
              "href": "/company/changelog",
              "description": "What shipped and what changed."
            },
            {
              "title": "Support",
              "href": "/company/contact",
              "description": "How to get help."
            }
          ]
        }
      ]
    },
    {
      "id": "trust",
      "label": "Trust & Security",
      "href": "/trust",
      "featured": {
        "title": "Claims & Methodology",
        "description": "How we measure leak tests and recall—and what we will not claim.",
        "href": "/trust/methodology",
        "cta": "Read methodology"
      },
      "columns": [
        {
          "title": "Architecture & proof",
          "items": [
            {
              "title": "Security Architecture",
              "href": "/trust/architecture",
              "description": "Boundary, Session Map, and fail-closed paths."
            },
            {
              "title": "Wire Tap & evidence",
              "href": "/trust/wire-tap",
              "description": "Post-scrub proof of Upstream traffic."
            },
            {
              "title": "What Aegis does not do",
              "href": "/trust/limitations",
              "description": "Non-goals and honest limitations."
            },
            {
              "title": "Claims & Methodology",
              "href": "/trust/methodology",
              "description": "Evidence rules for public claims."
            }
          ]
        },
        {
          "title": "Operations & frameworks",
          "items": [
            {
              "title": "Subprocessors",
              "href": "/trust/subprocessors",
              "description": "Processors for marketing site and Cloud."
            },
            {
              "title": "Status",
              "href": "/trust/status",
              "description": "Service status for managed offerings.",
              "external": false
            },
            {
              "title": "Compliance Frameworks",
              "href": "/trust/frameworks",
              "description": "NDPA 2023 and GAID 2025 context pages."
            },
            {
              "title": "NDPA 2023",
              "href": "/trust/frameworks/ndpa-2023",
              "description": "Cross-border context; not a compliance certificate."
            },
            {
              "title": "GAID 2025",
              "href": "/trust/frameworks/gaid-2025",
              "description": "Guidance themes mapped at a high level."
            },
            {
              "title": "Responsible disclosure",
              "href": "/trust/security",
              "description": "Report vulnerabilities privately."
            }
          ]
        }
      ]
    },
    {
      "id": "company",
      "label": "Company",
      "href": "/company",
      "featured": {
        "title": "Design Partner Program",
        "description": "Banks, fintechs, and hospitals shaping the boundary control plane.",
        "href": "/company/design-partners",
        "cta": "Apply"
      },
      "columns": [
        {
          "title": "Company",
          "items": [
            {
              "title": "About Us",
              "href": "/company/about",
              "description": "Mission and open-source stance."
            },
            {
              "title": "Blog",
              "href": "/company/blog",
              "description": "Product and policy writing."
            },
            {
              "title": "Changelog",
              "href": "/company/changelog",
              "description": "Release notes for operators."
            },
            {
              "title": "Contact",
              "href": "/company/contact",
              "description": "Sales, press, and general inquiries."
            },
            {
              "title": "Design Partner Program",
              "href": "/company/design-partners",
              "description": "Early access and structured feedback."
            },
            {
              "title": "Careers",
              "href": "/company/careers",
              "description": "Roles when hiring is open."
            }
          ]
        }
      ]
    }
  ],
  "utilityLinks": [
    { "label": "Docs", "href": "/docs" },
    { "label": "GitHub", "href": "GITHUB_URL", "external": true }
  ],
  "footer": {
    "columns": [
      {
        "title": "Product",
        "links": [
          { "label": "Open Source", "href": "/product/open-source" },
          { "label": "Proxy", "href": "/product/proxy" },
          { "label": "Scrubber", "href": "/product/scrubber" },
          { "label": "Wire Tap", "href": "/product/wire-tap" },
          { "label": "Cloud", "href": "/product/cloud" },
          { "label": "Pricing", "href": "/pricing" }
        ]
      },
      {
        "title": "Developers",
        "links": [
          { "label": "Quickstart", "href": "/developers/quickstart" },
          { "label": "Documentation", "href": "/docs" },
          { "label": "API Reference", "href": "/docs/api" },
          { "label": "Playground", "href": "/playground" },
          { "label": "GitHub", "href": "GITHUB_URL", "external": true },
          { "label": "Community", "href": "/developers/community" }
        ]
      },
      {
        "title": "Trust",
        "links": [
          { "label": "Security Architecture", "href": "/trust/architecture" },
          { "label": "Claims & Methodology", "href": "/trust/methodology" },
          { "label": "Frameworks", "href": "/trust/frameworks" },
          { "label": "Subprocessors", "href": "/trust/subprocessors" },
          { "label": "Status", "href": "/trust/status" },
          { "label": "Disclosure", "href": "/trust/security" }
        ]
      },
      {
        "title": "Company",
        "links": [
          { "label": "About", "href": "/company/about" },
          { "label": "Blog", "href": "/company/blog" },
          { "label": "Changelog", "href": "/company/changelog" },
          { "label": "Contact", "href": "/company/contact" },
          { "label": "Design Partners", "href": "/company/design-partners" }
        ]
      }
    ],
    "legal": [
      { "label": "Privacy Policy", "href": "/legal/privacy" },
      { "label": "Terms of Use", "href": "/legal/terms" },
      { "label": "DPA Template", "href": "/legal/dpa" },
      { "label": "Cookie Notice", "href": "/legal/cookies" },
      { "label": "License", "href": "/license" }
    ]
  }
}
```

### TypeScript shape (optional consumer)

```ts
export type NavLink = {
  title?: string;
  label?: string;
  href: string;
  description?: string;
  badge?: string;
  external?: boolean;
  cta?: string;
};

export type NavColumn = {
  title: string;
  items?: NavLink[];
  links?: NavLink[];
};

export type NavItem = {
  id: string;
  label: string;
  href: string;
  featured?: NavLink & { title: string; description: string; cta?: string };
  columns: NavColumn[];
};

export type SiteNav = {
  cta: { primary: NavLink; secondary: NavLink };
  items: NavItem[];
  utilityLinks: NavLink[];
  footer: {
    columns: NavColumn[];
    legal: NavLink[];
  };
};
```

---

## 8. Implementation notes (for later build steps)

1. **Do not write marketing copy in this file’s follow-on PRs without `CLAIMS.md` review.** Framework pages especially must avoid “compliant / legal / without violating NDPA”.
2. **Cloud pages** should visually badge “Managed / Coming” until features ship; OSS pages must not imply managed failover exists in Compose today.
3. **Playground** accepts no login and must refuse or clearly sandbox real PII (synthetic-only Acceptable Use).
4. **Status URL** may become external (`status.aegis…`); keep `/trust/status` as a redirect wrapper so footer/nav stay stable.
5. **Docs search / versioning** can nest under `/docs` without changing mega-menu labels.
6. **DESIGN.md §7** landing sections map to `/` only; deeper IA above is the scalable tree around that single composition.

---

## 9. Page count summary

| Area | Pages (approx.) |
|---|---|
| Global / Product | 14 |
| Solutions | 12 |
| Developers + Docs | 18 |
| Trust | 11 |
| Company | 8 |
| Legal / license | 6 |
| **Total blueprint routes** | **~69** (excl. blog slugs) |
