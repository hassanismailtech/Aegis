import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import test from "node:test";
import { GET } from "../app/.well-known/security.txt/route.ts";
import { marketingPaths, sitePages } from "../lib/site-content.ts";

const removedPaths = [
  "product/compare", "product/cloud", "product/cloud/managed-nodes", "product/cloud/audit-exports",
  "product/cloud/multi-region-failover", "product/cloud/tenant-controls", "product/cloud/jurisdiction-packs",
  "product/cloud/support", "trust/status", "trust/dpia-pack",
];
const read = path => readFile(new URL(`../${path}`, import.meta.url), "utf8");

test("unshipped roadmap routes are absent from the page registry and sitemap paths", () => {
  for (const path of removedPaths) {
    assert.equal(sitePages[path], undefined, path);
    assert.equal(marketingPaths.includes(path), false, path);
  }
  assert.equal(Object.values(sitePages).some(page => page.status === "Roadmap"), false);
});

test("navigation, footer, landing, and related links resolve to retained pages or redirects", async () => {
  const config = await read("next.config.ts");
  const redirects = [...config.matchAll(/source: "([^"]+)", destination: "([^"]+)"/g)];
  const routes = new Set(["/", ...marketingPaths.map(path => `/${path}`)]);
  const valid = new Set([...routes, ...redirects.map(match => match[1])]);
  for (const match of redirects) assert.ok(routes.has(match[2]), `redirect ${match[1]}`);
  const links = Object.values(sitePages).flatMap(page => page.related?.map(link => link.href) ?? []);
  for (const file of ["components/GlobalNav.tsx", "components/SiteFooter.tsx", "app/(marketing)/page.tsx"]) {
    const source = await read(file);
    links.push(...[...source.matchAll(/["'](\/[^"'\s]*)["']/g)].map(match => match[1]));
    assert.equal(source.includes("mailto:?"), false, file);
  }
  for (const href of links.filter(href => href.startsWith("/"))) {
    assert.ok(valid.has(new URL(href, "https://example.test").pathname), `unresolved link ${href}`);
  }
  const partnerLink = sitePages["company/design-partners"].related.find(link => link.href.startsWith("https://github.com/"));
  assert.equal(new URL(partnerLink.href).pathname, "/hassanismailtech/Aegis/issues/new");
});

function siteOrigin(t, value) {
  const previous = process.env.NEXT_PUBLIC_SITE_URL;
  if (value === undefined) delete process.env.NEXT_PUBLIC_SITE_URL;
  else process.env.NEXT_PUBLIC_SITE_URL = value;
  t.after(() => {
    if (previous === undefined) delete process.env.NEXT_PUBLIC_SITE_URL;
    else process.env.NEXT_PUBLIC_SITE_URL = previous;
  });
}

test("security contact has a single expiry, private report link, and HTTPS canonical from configuration", async t => {
  siteOrigin(t, "https://example.test/some-path?ignored=true");
  const response = GET();
  assert.equal(response.status, 200);
  assert.equal(response.headers.get("Content-Type"), "text/plain; charset=utf-8");
  const body = await response.text();
  assert.match(body, /^Contact: https:\/\/github.com\/hassanismailtech\/Aegis\/security\/advisories\/new$/m);
  assert.equal(body.match(/^Expires: /gm).length, 1);
  assert.match(body, /^Expires: 2027-11-18T00:00:00.000Z$/m);
  assert.match(body, /^Canonical: https:\/\/example.test\/\.well-known\/security.txt$/m);
  assert.ok(body.endsWith("\n"));
});

for (const origin of [undefined, "", "invalid", "http://example.test", "https://user:secret@example.test"]) {
  test(`security contact omits unverified canonical (${origin === undefined ? "unset" : origin === "" ? "empty" : "invalid origin"})`, async t => {
    siteOrigin(t, origin);
    const body = await GET().text();
    assert.equal(body.includes("Canonical:"), false);
    assert.equal(body.includes("secret"), false);
    assert.match(body, /^Expires: /m);
  });
}
