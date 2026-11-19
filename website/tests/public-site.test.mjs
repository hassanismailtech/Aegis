import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import test from "node:test";
import { GET } from "../app/.well-known/security.txt/route.ts";
import { marketingPaths, sitePages } from "../lib/site-content.ts";
import { applyTheme, readTheme, themeBootstrap, THEME_KEY } from "../lib/theme.ts";
import { runInNewContext } from "node:vm";

function themeRoot() {
  let dark = false;
  return { classList: { toggle(name, enabled) { assert.equal(name, "dark"); dark = enabled; }, contains() { return dark; } } };
}

test("theme defaults to light and accepts only an explicit saved dark preference", () => {
  for (const value of [null, "", "light", "system", "unexpected"]) assert.equal(readTheme({ getItem: () => value }), "light");
  assert.equal(readTheme({ getItem: () => "dark" }), "dark");
  assert.equal(readTheme({ getItem() { throw Error("blocked"); } }), "light");
});

test("theme changes the page and persists a single preference without storing input", () => {
  const root = themeRoot();
  const stored = new Map();
  const storage = { setItem: (key, value) => stored.set(key, value) };
  applyTheme(root, storage, "dark");
  assert.equal(root.classList.contains("dark"), true);
  assert.deepEqual([...stored], [[THEME_KEY, "dark"]]);
  applyTheme(root, storage, "light");
  assert.equal(root.classList.contains("dark"), false);
  assert.deepEqual([...stored], [[THEME_KEY, "light"]]);
});

test("theme still changes when preference storage is blocked", () => {
  const root = themeRoot();
  applyTheme(root, { setItem() { throw Error("blocked"); } }, "dark");
  assert.equal(root.classList.contains("dark"), true);
});

test("pre-paint theme bootstrap restores dark and tolerates inaccessible storage", () => {
  const document = { documentElement: themeRoot() };
  runInNewContext(themeBootstrap, { document, localStorage: { getItem: () => "dark" } });
  assert.equal(document.documentElement.classList.contains("dark"), true);
  runInNewContext(themeBootstrap, { document, localStorage: { getItem: () => "invalid" } });
  assert.equal(document.documentElement.classList.contains("dark"), false);
  const blocked = { document };
  Object.defineProperty(blocked, "localStorage", { get() { throw Error("blocked"); } });
  assert.doesNotThrow(() => runInNewContext(themeBootstrap, blocked));
});

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
});

test("design-partner interest opens the confirmed mailbox with a subject", () => {
  const links = sitePages["company/design-partners"].related;
  assert.equal(links.length, 1);
  const target = new URL(links[0].href);
  assert.equal(target.protocol, "mailto:");
  assert.equal(target.pathname, "hello@seclume.tech");
  assert.equal(target.searchParams.get("subject"), "Design partner");
});

test("contact and disclosure pages expose the confirmed channels", () => {
  const contacts = sitePages["company/contact"].related.map(link => link.href);
  assert.ok(contacts.includes("mailto:hello@seclume.tech"));
  assert.ok(contacts.includes("mailto:privacy@seclume.tech"));
  const security = sitePages["trust/security"].related.map(link => link.href);
  assert.ok(security.includes("mailto:security@seclume.tech"));
  assert.ok(security.includes("https://github.com/hassanismailtech/seclume/security/advisories/new"));
});

test("publishing the privacy contact retains the policy review qualification", () => {
  const privacy = sitePages["legal/privacy"];
  assert.equal(privacy.status, "Publication review");
  assert.ok(privacy.related.some(link => link.href === "mailto:privacy@seclume.tech"));
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
  assert.match(body, /^Contact: mailto:security@seclume\.tech$/m);
  assert.match(body, /^Contact: https:\/\/github.com\/hassanismailtech\/seclume\/security\/advisories\/new$/m);
  assert.equal(body.match(/^Contact: /gm).length, 2);
  assert.match(body, /^Policy: https:\/\/github.com\/hassanismailtech\/seclume\/security\/policy$/m);
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
