import assert from "node:assert/strict";
import fs from "node:fs";
import vm from "node:vm";
import ts from "typescript";
import { webcrypto } from "node:crypto";

const code = ts.transpileModule(fs.readFileSync(new URL("../lib/analytics.ts", import.meta.url), "utf8"), {
  compilerOptions: { module: ts.ModuleKind.CommonJS },
}).outputText;

function deferred() {
  let resolve;
  const promise = new Promise((done) => { resolve = done; });
  return { promise, resolve };
}

function client(initialize, post = async () => ({ ok: true }), browserWindow) {
  const requests = [];
  const timers = new Map();
  let initializations = 0;
  let timerId = 0;
  const api = {
    session: null,
    base: "https://api.dufynd.test/api",
    headers: () => ({ "X-Session-Id": api.session }),
  };
  const module = { exports: {} };
  vm.runInNewContext(code, {
    module, exports: module.exports, AbortController, URL, URLSearchParams, crypto: webcrypto,
    ...(browserWindow ? { window: browserWindow } : {}),
    require: (name) => {
      assert.equal(name, "./api");
      return { api, initializeAnalyticsSession: () => initialize(++initializations) };
    },
    fetch: (url, init) => {
      requests.push({ url, init, payload: JSON.parse(init.body) });
      return post(requests.length, init);
    },
    setTimeout: (callback, delay) => {
      const id = ++timerId;
      timers.set(id, { callback, delay });
      return id;
    },
    clearTimeout: (id) => timers.delete(id),
  });
  return { api, ...module.exports, requests, timers, get initializations() { return initializations; } };
}

// Concurrent standalone reads share one initialization and retain normal retry.
{
  const pending = deferred();
  const env = client(() => pending.promise);
  const reads = [env.ensureAnalyticsSession(), env.ensureAnalyticsSession()];
  assert.equal(env.initializations, 1);
  pending.resolve("analytics-1");
  assert.deepEqual(await Promise.all(reads), ["analytics-1", "analytics-1"]);
  assert.equal(env.api.session, "analytics-1");
}

// A session installed by the advisor while analytics is pending wins, whether
// the standalone initialization succeeds or fails.
for (const lateResult of ["late-analytics", null]) {
  const pending = deferred();
  const env = client(() => pending.promise, async () => ({ ok: false }));
  const read = env.ensureAnalyticsSession();
  env.api.session = "advisor-current";
  pending.resolve(lateResult);
  assert.equal(await read, "advisor-current");
  assert.equal(env.api.session, "advisor-current");
  await env.trackAnalyticsEvent("page_view");
  assert.equal(env.requests[0].init.headers["X-Session-Id"], "advisor-current");
  assert.equal(env.initializations, 1, "an advisor session must never be renewed by analytics failure");
  assert.equal(env.api.session, "advisor-current");
  assert.equal(env.timers.size, 0);
}

// A failed analytics POST must not erase an advisor session established after
// the POST began. The next queued event uses the advisor without a retry/init.
{
  const firstPost = deferred();
  const postStarted = deferred();
  const env = client(async (attempt) => `analytics-${attempt}`, (attempt) => {
    if (attempt === 1) { postStarted.resolve(); return firstPost.promise; }
    return Promise.resolve({ ok: true });
  });
  await env.ensureAnalyticsSession();
  const first = env.trackAnalyticsEvent("page_view");
  const queued = env.trackAnalyticsEvent("product_open", { product_id: "SC-TEST" });
  await postStarted.promise;
  env.api.session = "advisor-current";
  firstPost.resolve({ ok: false });
  await Promise.all([first, queued]);
  assert.equal(env.api.session, "advisor-current");
  assert.equal(env.initializations, 1);
  assert.equal(env.requests.length, 2);
  assert.equal(env.requests[0].payload.event, "page_view");
  assert.equal(env.requests[0].init.headers["X-Session-Id"], "analytics-1");
  assert.equal(env.requests[1].payload.event, "product_open");
  assert.equal(env.requests[1].init.headers["X-Session-Id"], "advisor-current");
  assert.equal(env.timers.size, 0);
}

// Existing standalone recovery still renews once and drains the event queue.
for (const retryOk of [true, false]) {
  const env = client(async (attempt) => `analytics-${attempt}`, async (attempt) => ({ ok: attempt > 1 && retryOk }));
  env.rememberAcquisitionAttribution({ source: "tiktok", campaignId: "session_qa" });
  await env.trackAnalyticsEvent("page_view");
  assert.equal(env.initializations, 2);
  assert.equal(env.requests.length, 2, "retry remains bounded to once");
  assert.equal(env.requests[0].init.headers["X-Session-Id"], "analytics-1");
  assert.equal(env.requests[1].init.headers["X-Session-Id"], "analytics-2");
  assert.equal(env.requests[1].payload.campaign_id, "session_qa");
  assert.match(env.requests[0].payload.event_id, /^[a-f0-9-]{36}$/);
  assert.equal(env.requests[0].payload.event_id, env.requests[1].payload.event_id);
  assert.equal(env.api.session, "analytics-2");
  assert.equal(env.timers.size, 0);
}

{
  const env = client(async () => null);
  await env.trackAnalyticsEvent("page_view");
  assert.equal(env.api.session, null);
  assert.equal(env.requests.length, 0);
  assert.equal(env.timers.size, 0);
}

console.log("DUFYND analytics session ownership: late initialization, advisor takeover, queued events and bounded standalone retry passed.");

// A full document navigation establishes a new transport session but retains
// the tab's first-party funnel identity and acquisition fields.
for (const original of [
  "11111111-1111-4111-8111-111111111111",
  "qa_URLsafe-session_1234567890-abcd",
]) {
  const storage = new Map();
  const window = {
    location: { origin: "https://dufynd.test" },
    sessionStorage: { getItem: (key) => storage.get(key) ?? null, setItem: (key, value) => storage.set(key, value) },
  };
  const replacement = "22222222-2222-4222-8222-222222222222";
  const first = client(async () => original, undefined, window);
  first.rememberAcquisitionAttribution({ source: "instagram", campaignId: "fm_campaign", contentId: "fm_content" });
  await first.trackAnalyticsEvent("page_view");
  const nextDocument = client(async () => replacement, undefined, window);
  await nextDocument.trackAnalyticsEvent("fragrance_detail_view", { product_id: "SC-TEST" });
  assert.equal(nextDocument.api.session, replacement, "do not restore an API/advisor session from analytics storage");
  assert.equal(first.requests[0].payload.analytics_session_id, original);
  assert.equal(nextDocument.requests[0].payload.analytics_session_id, original);
  assert.equal(nextDocument.requests[0].init.headers["X-Session-Id"], replacement);
  assert.equal(nextDocument.requests[0].payload.content_id, "fm_content");
  const target = new URL(nextDocument.appendAcquisitionAttribution("/api/clickout/qa-offer"));
  assert.equal(target.searchParams.get("sid"), original);
  assert.equal(target.searchParams.get("cmp"), "fm_campaign");
}

// API-session recovery must not split the analytics session. Invalid persisted
// identifiers are replaced, and blocked storage still works within a document.
for (const blocked of [false, true]) {
  const storage = new Map([["dufynd_analytics_session_v1", "invalid@example.com"]]);
  const window = {
    location: { origin: "https://dufynd.test" },
    sessionStorage: {
      getItem: (key) => { if (blocked) throw new Error("blocked"); return storage.get(key) ?? null; },
      setItem: (key, value) => { if (blocked) throw new Error("blocked"); storage.set(key, value); },
    },
  };
  const env = client(async (n) => `qa-transport-session-${n}-1234567890`, async (n) => ({ ok: n > 1 }), window);
  await env.trackAnalyticsEvent("page_view");
  assert.equal(env.initializations, 2);
  assert.equal(env.requests[0].payload.analytics_session_id, "qa-transport-session-1-1234567890");
  assert.equal(env.requests[1].payload.analytics_session_id, "qa-transport-session-1-1234567890");
  assert.equal(env.api.session, "qa-transport-session-2-1234567890");
}
console.log("DUFYND analytics funnel identity: document navigation, transport recovery, invalid and blocked storage passed.");

// Explicit internal QA persists across navigation and un-attributed clickouts.
{
  const storage = new Map();
  const browserWindow = {
    location: { origin: "https://dufynd.test", search: "?qa=1" },
    sessionStorage: { getItem: (key) => storage.get(key) ?? null, setItem: (key, value) => storage.set(key, value) },
  };
  const env = client(async () => "valid_analytics_session_123", undefined, browserWindow);
  await env.trackAnalyticsEvent("page_view");
  assert.equal(env.requests[0].payload.internal_qa, true);
  browserWindow.location.search = "";
  const nextPage = client(async () => "valid_analytics_session_123", undefined, browserWindow);
  await nextPage.trackAnalyticsEvent("fragrance_detail_view");
  assert.equal(nextPage.requests[0].payload.internal_qa, true);
  assert.equal(new URL(nextPage.appendAcquisitionAttribution("/api/clickout/fixture")).searchParams.get("qa"), "1");
}
