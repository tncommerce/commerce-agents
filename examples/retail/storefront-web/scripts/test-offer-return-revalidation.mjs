// Exercise the shipped FragranceOffers effect, not a duplicate revalidation helper.
// Browser-return checks are functional commerce reads and must not depend on
// optional measurement consent, cause periodic polling, or fire click events.
import assert from "node:assert/strict";
import fs from "node:fs";
import vm from "node:vm";
import { createRequire } from "node:module";

const require = createRequire(import.meta.url);
const ts = require("typescript");
const source = fs.readFileSync(new URL("../components/FragranceOffers.tsx", import.meta.url), "utf8");
const compiled = ts.transpileModule(source, {
  reportDiagnostics: true,
  compilerOptions: {
    module: ts.ModuleKind.CommonJS,
    target: ts.ScriptTarget.ES2022,
    jsx: ts.JsxEmit.ReactJSX,
    esModuleInterop: true,
  },
});
assert.deepEqual(compiled.diagnostics, []);

let now = 100_000;
const listeners = { document: new Map(), window: new Map() };
const state = [];
let stateIndex = 0;
const effects = [];
let functionalFetches = 0;
let analyticsCalls = 0;

const react = {
  useState(initial) {
    const index = stateIndex++;
    state[index] = initial;
    return [state[index], (next) => {
      state[index] = typeof next === "function" ? next(state[index]) : next;
    }];
  },
  useRef(initial) { return { current: initial }; },
  useEffect(callback) { effects.push(callback); },
};

const document = {
  visibilityState: "visible",
  addEventListener(event, callback) { listeners.document.set(event, callback); },
  removeEventListener(event, callback) {
    assert.equal(listeners.document.get(event), callback);
    listeners.document.delete(event);
  },
};
const window = {
  addEventListener(event, callback) { listeners.window.set(event, callback); },
  removeEventListener(event, callback) {
    assert.equal(listeners.window.get(event), callback);
    listeners.window.delete(event);
  },
};

const module = { exports: {} };
const stubs = {
  react,
  "react/jsx-runtime": { jsx: () => null, jsxs: () => null },
  "web-shared": { formatMoney: () => "" },
  "@/lib/api": {
    fetchMerchantOffers: async () => {
      functionalFetches += 1;
      return { product_id: "SC-TEST", offers: [], best_offer_id: null };
    },
    merchantClickoutUrl: (path) => path,
  },
  "@/lib/analytics": {
    appendAcquisitionAttribution: (href) => href,
    ensureAnalyticsSession: async () => null,
    trackAnalyticsEvent: async () => { analyticsCalls += 1; },
  },
  "@/lib/measurementConsent": {
    measurementAllowed: () => false,
    subscribeMeasurement: () => () => {},
  },
  "@/lib/officialProductPages": { OFFICIAL_PRODUCT_PAGES: {} },
  "@/components/AcquisitionInternalLink": { default: () => null },
  "./FragranceOffers.module.css": { default: {} },
};
const context = {
  module, exports: module.exports,
  document, window,
  Date: class ClockDate extends Date { static now() { return now; } },
  require(id) {
    if (!(id in stubs)) throw new Error("Unexpected import: " + id);
    return stubs[id];
  },
};

vm.runInNewContext(compiled.outputText, context, { timeout: 1500 });
module.exports.default({ productId: "SC-RABANNE-1-MILLION-EDT-100" });
const cleanups = effects.map((run) => run()).filter((f) => typeof f === "function");

assert.equal(functionalFetches, 1, "Offers must load without analytics consent");
assert.equal(state[2], 0, "No revalidation on mount");
assert.equal(listeners.document.has("visibilitychange"), true);
assert.equal(listeners.window.has("pageshow"), true);

const emit = (scope, event) => {
  const callback = listeners[scope].get(event);
  assert.equal(typeof callback, "function");
  callback();
};

now += 5 * 60 * 1000;
document.visibilityState = "hidden";
emit("document", "visibilitychange");
assert.equal(state[2], 0, "Hidden tabs may not trigger network rechecks");

document.visibilityState = "visible";
now -= 1;
emit("document", "visibilitychange");
assert.equal(state[2], 0, "A tab returning just before the threshold stays idle");

now += 1;
emit("document", "visibilitychange");
assert.equal(state[2], 1, "A stale tab returning to foreground revalidates once");

// Browsers may emit both visibilitychange and pageshow before React re-renders.
emit("window", "pageshow");
emit("document", "visibilitychange");
assert.equal(state[2], 1, "Near-simultaneous return events must not double-refresh");

now += 5 * 60 * 1000;
emit("window", "pageshow");
assert.equal(state[2], 2, "A later back-forward restore revalidates again");

assert.equal(analyticsCalls, 0, "Functional commerce refresh may not emit optional analytics");
assert.equal(listeners.document.size, 1, "Only one non-periodic document listener");
assert.equal(listeners.window.size, 1, "Only one non-periodic window listener");
for (const cleanup of cleanups) cleanup();
assert.equal(listeners.document.size, 0);
assert.equal(listeners.window.size, 0);
console.log(JSON.stringify({
  status: "PASS",
  cases: 10,
  functionalReads: functionalFetches,
  optionalAnalyticsEvents: analyticsCalls,
  realNetworkRequests: 0,
  pollingTimers: 0,
}));
