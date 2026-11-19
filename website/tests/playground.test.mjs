import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import test from "node:test";
import { ENTITY_TYPES, EXAMPLES, MAX_CHARS, playgroundEndpoint, scrubPlayground, splitPlaceholders } from "../lib/playground.ts";
import { marketingPaths, sitePages } from "../lib/site-content.ts";

const base = "https://example.test";
const counts = Object.fromEntries(ENTITY_TYPES.map(type => [type, type === "BVN" ? 1 : 0]));
const payload = { scrubbed: "Check [[BVN_1]].", simulated_reply: "Received [[BVN_1]].", counts, overhead_ms: 1.25, mode: "lite" };
const call = (text = EXAMPLES[0].text, signal = new AbortController().signal) => scrubPlayground(base, text, signal);

test("API base is normalized without credentials, query strings or fragments", () => {
  assert.equal(playgroundEndpoint(" https://example.test/proxy/ "), "https://example.test/proxy/v1/playground/scrub");
  for (const value of [undefined, "", "   ", "not a URL", "/relative", "file:///tmp/api", "https://user:secret@example.test", "https://example.test?key=x", "https://example.test#x"]) {
    assert.equal(playgroundEndpoint(value), null);
  }
});

test("missing configuration and invalid input send no request", async t => {
  const fetch = t.mock.method(globalThis, "fetch", () => { throw Error("unexpected request"); });
  for (const text of ["", "  ", "x".repeat(MAX_CHARS + 1)]) assert.equal((await call(text)).ok, false);
  assert.equal((await scrubPlayground(undefined, EXAMPLES[0].text, new AbortController().signal)).ok, false);
  assert.equal(fetch.mock.callCount(), 0);
});

test("success sends a bounded POST and selects only scrubbed contract fields", async t => {
  const fetch = t.mock.method(globalThis, "fetch", async () => Response.json({ ...payload, reinjected_reply: "discarded", entities: [] }));
  const controller = new AbortController();
  assert.deepEqual(await call("x".repeat(MAX_CHARS), controller.signal), { ok: true, result: payload });
  const [url, options] = fetch.mock.calls[0].arguments;
  assert.equal(url, `${base}/v1/playground/scrub`);
  assert.equal(options.method, "POST");
  assert.equal(options.body, JSON.stringify({ text: "x".repeat(MAX_CHARS) }));
  assert.deepEqual(options.headers, { "Content-Type": "application/json" });
  assert.equal(options.cache, "no-store");
  assert.equal(options.credentials, "omit");
  assert.equal(options.redirect, "error");
  assert.equal(options.signal, controller.signal);
});

for (const mode of ["full", "lite"]) test(`retains actual ${mode} mode`, async t => {
  t.mock.method(globalThis, "fetch", async () => Response.json({ ...payload, mode }));
  assert.equal((await call()).result.mode, mode);
});

for (const status of [404, 422, 429, 503, 500]) test(`HTTP ${status} never displays server error bodies`, async t => {
  let bodyRead = false;
  t.mock.method(globalThis, "fetch", async () => ({ ok: false, status, headers: new Headers(), json() { bodyRead = true; throw Error("must not read"); } }));
  const result = await call();
  assert.equal(result.ok, false);
  assert.ok(result.message.length > 0);
  assert.equal(bodyRead, false);
  if (status === 422) assert.match(result.message, /input was rejected/);
});

test("rate limit uses only a bounded numeric Retry-After", async t => {
  let retry = "17";
  t.mock.method(globalThis, "fetch", async () => new Response(null, { status: 429, headers: { "Retry-After": retry } }));
  assert.match((await call()).message, /17 seconds/);
  for (retry of ["-1", "0", "61", "99999999999999999999999", "arbitrary text", "Wed, 21 Oct 2015 07:28:00 GMT"]) {
    assert.equal((await call()).message, "Too many requests. Please wait before trying again.");
  }
});

test("network and JSON failures return static errors", async t => {
  const fetch = t.mock.method(globalThis, "fetch", async () => { throw Error("private transport details"); });
  const network = await call();
  fetch.mock.mockImplementation(async () => new Response("<html>private response</html>"));
  assert.deepEqual(await call(), network);
  assert.equal(network.ok, false);
  assert.equal(network.message.includes("private"), false);
});

test("the request can be cancelled", async t => {
  t.mock.method(globalThis, "fetch", (_url, { signal }) => new Promise((_resolve, reject) => {
    signal.addEventListener("abort", () => reject(new DOMException("Aborted", "AbortError")), { once: true });
  }));
  const controller = new AbortController();
  const pending = call(EXAMPLES[0].text, controller.signal);
  controller.abort();
  assert.equal((await pending).ok, false);
});

test("malformed success payloads are rejected", async t => {
  let value;
  t.mock.method(globalThis, "fetch", async () => Response.json(value));
  for (value of [null, [], {}, { ...payload, scrubbed: 3 }, { ...payload, simulated_reply: null },
    { ...payload, mode: "unknown" }, { ...payload, overhead_ms: -1 }, { ...payload, overhead_ms: "1" },
    { ...payload, counts: {} }, { ...payload, counts: { ...counts, BVN: -1 } },
    { ...payload, counts: { ...counts, PERSON: 0.5 } }]) assert.equal((await call()).ok, false);
});

test("Placeholder splitting preserves hostile text as plain text", () => {
  const text = '<script>alert("x")</script> [[ACCOUNT_NO_12]][[PERSON_1]] [[UNKNOWN_1]]';
  const parts = splitPlaceholders(text);
  assert.equal(parts.map(part => part.text).join(""), text);
  assert.deepEqual(parts.filter(part => part.placeholder).map(part => part.text), ["[[ACCOUNT_NO_12]]", "[[PERSON_1]]"]);
  assert.equal(splitPlaceholders("ordinary text")[0].placeholder, false);
});

test("examples reuse approved demo fixtures", async () => {
  const fixtures = JSON.parse(await readFile(new URL("../../demo/prompts.json", import.meta.url), "utf8"));
  assert.equal(EXAMPLES.length, 3);
  for (const example of EXAMPLES) {
    assert.ok(fixtures.some(fixture => fixture.text === example.text));
    assert.ok(example.text.length <= MAX_CHARS);
  }
});

test("dedicated playground route stays in the sitemap without the old catch-all copy", () => {
  assert.equal(sitePages.playground, undefined);
  assert.equal(marketingPaths.filter(path => path === "playground").length, 1);
});
