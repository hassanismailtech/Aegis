# Aegis design system v2 (landing + dashboard)

Feeling: calm, exact, trustworthy. A DPO and an engineer should both feel "this tells me the truth". Evidence over decoration.

## 1. What to borrow (patterns, not copy)
- **Mistral:** a sovereign-deployment story told as a block ("run in your VPC / on-prem / in-region") and a customer-logo strip once you have real ones. Do not copy their colours or the "#1" framing.
- **Devin:** the enterprise-security row (retention, SSO/RBAC, private networking, audit) as a compact checklist near the footer, and product screenshots as hero imagery.
- **Armadin:** restraint, large editorial headline, one particle or topographic graphic. Do not reuse their "machine-speed attacks" problem. Your problem is data crossing a border.
- **Moonshot:** whitespace and a single accent. Skip the prompt box; your hero action is the `docker compose up` snippet.

## 2. Hard rules
1. No manipulation: no pulsing "not run" warnings, no fake-disabled "enterprise" toggles, no fee anchoring on a free tool. Show a neutral "Leak test: not run. Run it:" with the command.
2. Never show a number you cannot source. Latency is shown as measured p50/p95 with the stage name (rule layer, model layer, upstream).
3. Pre-scrub text never appears in any UI. Wire View shows post-scrub only, and says so in its label.
4. Third-party analytics only on the marketing site, disclosed. None in the dashboard.

## 3. Tokens (CSS variables; dark default, provide light)
```css
:root[data-theme="dark"] {
  --bg:#09090b; --surface:#18181b; --border:#27272a; --ring:rgba(255,255,255,.10);
  --text:#fafafa; --muted:#a1a1aa;
  --accent:#22d3ee;      /* secure / active */
  --ok:#34d399; --warn:#fbbf24; --danger:#fb7185;
}
:root[data-theme="light"] {
  --bg:#ffffff; --surface:#f4f4f5; --border:#e4e4e7; --ring:rgba(0,0,0,.08);
  --text:#09090b; --muted:#52525b; --accent:#0891b2; --ok:#059669; --warn:#b45309; --danger:#be123c;
}
```
Contrast: body text at least 4.5:1, large text 3:1, never convey state by colour alone (icon plus label on every badge). Respect `prefers-reduced-motion`.

## 4. Type
- UI and prose: Geist Sans (fallback Inter, system-ui). Weights 400, 500, 600.
- Telemetry, code, Wire View, placeholders: Geist Mono (fallback JetBrains Mono, ui-monospace). Tabular numerals for all metrics.
- Marketing headline only: a restrained serif (e.g. Newsreader) at large size for gravity; everything else sans. Truncate long payloads with a "show full" control, never silently.
- Scale: 12 / 14 / 16 / 20 / 28 / 44. Line length under 72 characters for prose.

## 5. Components (shadcn/ui, no custom kit)
Badge (status: ok, state_loss, scrub_blocked, upstream_error, each with icon and text), Card, ScrollArea, Table, Button, Tabs, Tooltip, Dialog. Entity colours come from one categorical palette used only for the six entity types, consistent in chart, feed and Wire View highlighting.

## 6. Dashboard layout (single page)
- **Top bar:** logo, then entities scrubbed, requests, overhead p50/p95 (rule layer and model layer shown separately), blocked requests, leak-test status (neutral).
- **Left:** Live Feed. New events fade in at the top (150 ms), list does not jump while the user is scrolling or has an item selected.
- **Right:** entity chart by type, over a selectable window.
- **Bottom:** Wire View for the selected request: outbound messages with placeholders highlighted, a "post-scrub only" label, copy-as-JSON.
- **Empty state:** "Waiting for traffic" plus two actions: Seed demo data, and the `demo/agent.py` command.
- **Auth state:** a small "Token required" screen instead of a broken UI when the demo token is wrong.

## 7. Landing layout
Hero (headline, `docker compose up` with copy button, diff visual), Problem (3 facts), How it works (3 steps with the ASCII or SVG core loop), Integration (code), Evidence (table plus link to methodology), Evidence-for-DPO block, Deploy block (VPC / on-prem / Nigeria-hosted), "What Aegis does not do", Design-partner CTA, enterprise-security checklist row, footer. Docs on a separate route (Markdown, search, versioned).

## 8. Motion and imagery
150 ms ease-in-out on hover and feed insertion; no looping animation on data. One abstract topographic or particle graphic at most. No stock photos, no stolen screenshots, no logos you do not have permission to show.

## 9. Voice
Plain, specific, measured. "Reduces", "keeps out", "evidence", "as measured on". Never "guarantee", "military-grade", "zero-knowledge", "100%".
