// Offline regression of the exact FragranceOffers component. No real HTTP,
// analytics, merchant navigation or polling. This is NOT full browser QA.
// Keep the response-boundary regression in the existing prebuild entrypoint.
import './test-offer-contract.mjs';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import vm from 'node:vm';
import { createRequire } from 'node:module';
const require = createRequire(import.meta.url);
const ts = require('typescript');
const source = fs.readFileSync(new URL('../components/FragranceOffers.tsx', import.meta.url), 'utf8');
const INTERVAL = 300_000;
const PRODUCT_A = 'SC-RABANNE-1-MILLION-EDT-100';
const PRODUCT_B = 'SC-YSL-LIBRE-EDP-90';
const offerPayload = (id = PRODUCT_A, price = 71.9) => ({
  product_id: id, best_offer_id: `${id}-offer`, offers: [{
    offer_id: `${id}-offer`, merchant_id: 'fixture-merchant', merchant_name: 'Fixture merchant',
    currency: 'EUR', price, total_price: price + 4.99, shipping_cost: 4.99,
    affiliate_link: true, clickout_path: `/fixture/${id}`, last_updated_at: '2026-10-20T06:00:00Z',
  }],
});
const emptyPayload = (id = PRODUCT_A) => ({ product_id: id, offers: [], best_offer_id: null });

function makeHarness(input = source, { consent = false, productId = PRODUCT_A } = {}) {
  const compiled = ts.transpileModule(input, { reportDiagnostics: true, compilerOptions: {
    module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2022,
    jsx: ts.JsxEmit.ReactJSX, esModuleInterop: true,
  }});
  assert.deepEqual(compiled.diagnostics, []);
  let now = 100_000, index = 0, dirty = false, mounted = true, tree;
  let pendingEffects = [], props = { productId }, sessionCalls = 0;
  let writesAfterUnmount = 0;
  const slots = [], requests = [], analytics = [], subscribers = new Set();
  const listeners = { document: new Map(), window: new Map() };
  const sameDeps = (a, b) => a && b && a.length === b.length && a.every((v, i) => Object.is(v, b[i]));
  const useSlot = (kind, create) => {
    const at = index++;
    if (!(at in slots)) slots[at] = { kind, ...create() };
    assert.equal(slots[at].kind, kind, 'Hook order changed');
    return slots[at];
  };
  const react = {
    useState(initial) {
      const slot = useSlot('state', () => ({ value: typeof initial === 'function' ? initial() : initial }));
      slot.setter ??= (next) => {
        if (!mounted) { writesAfterUnmount += 1; return; }
        const value = typeof next === 'function' ? next(slot.value) : next;
        if (!Object.is(value, slot.value)) { slot.value = value; dirty = true; }
      };
      return [slot.value, slot.setter];
    },
    useRef(initial) { return useSlot('ref', () => ({ value: { current: initial } })).value; },
    useEffect(callback, deps) {
      const slot = useSlot('effect', () => ({ deps: undefined, cleanup: undefined }));
      if (!sameDeps(slot.deps, deps)) pendingEffects.push({ slot, callback, deps });
    },
  };
  function eventTarget(scope) {
    return {
      addEventListener(event, callback) {
        if (!listeners[scope].has(event)) listeners[scope].set(event, new Set());
        listeners[scope].get(event).add(callback);
      },
      removeEventListener(event, callback) {
        const group = listeners[scope].get(event); group?.delete(callback);
        if (group?.size === 0) listeners[scope].delete(event);
      },
    };
  }
  const document = { visibilityState: 'visible', ...eventTarget('document') };
  const window = eventTarget('window');
  const jsx = (type, properties, key) => ({ type, props: properties ?? {}, key });
  const stubs = {
    react, 'react/jsx-runtime': { jsx, jsxs: jsx },
    'web-shared': { formatMoney: (n) => String(n) },
    '@/lib/api': {
      fetchMerchantOffers(id) {
        let resolve, reject;
        const promise = new Promise((ok, no) => { resolve = ok; reject = no; });
        requests.push({ productId: id, resolve, reject }); return promise;
      },
      merchantClickoutUrl: (path) => path,
    },
    '@/lib/analytics': {
      appendAcquisitionAttribution: (href) => href,
      ensureAnalyticsSession: async () => { sessionCalls += 1; return null; },
      trackAnalyticsEvent: async (event, payload) => { analytics.push({ event, payload }); },
    },
    '@/lib/measurementConsent': {
      measurementAllowed: () => consent,
      subscribeMeasurement: (callback) => { subscribers.add(callback); return () => subscribers.delete(callback); },
    },
    '@/lib/officialProductPages': { OFFICIAL_PRODUCT_PAGES: {} },
    '@/components/AcquisitionInternalLink': { default: () => null },
    './FragranceOffers.module.css': { default: {} },
  };
  const module = { exports: {} };
  vm.runInNewContext(compiled.outputText, {
    module, exports: module.exports, document, window,
    Date: class ClockDate extends Date { static now() { return now; } },
    require(id) { assert.ok(id in stubs, `Unexpected import ${id}`); return stubs[id]; },
    setTimeout() { throw new Error('Unexpected timer'); },
    setInterval() { throw new Error('Unexpected polling'); },
    fetch() { throw new Error('Real network forbidden in offline regression'); },
  }, { timeout: 1500 });
  const render = () => {
    index = 0; dirty = false; pendingEffects = [];
    tree = module.exports.default(props);
  };
  const commit = () => {
    // Model refs and effect cleanup/setup; scheduling is deterministic, not React DOM.
    for (const slot of slots) if (slot.kind === 'ref' && slot.value.current?.fixtureNode) slot.value.current = null;
    if (tree?.props.ref) tree.props.ref.current = { fixtureNode: true };
    const effects = pendingEffects; pendingEffects = [];
    for (const { slot } of effects) slot.cleanup?.();
    for (const { slot, callback, deps } of effects) { slot.deps = deps; slot.cleanup = callback(); }
  };
  async function flush() {
    for (let i = 0; i < 12; i += 1) {
      if (dirty) { render(); commit(); }
      await Promise.resolve();
    }
    assert.equal(dirty, false, 'State updates did not settle');
  }
  const emit = (scope, event) => { for (const callback of listeners[scope].get(event) ?? []) callback(); };
  render(); commit();
  return {
    requests, analytics, listeners, subscribers, document, flush, emit,
    get tree() { return tree; }, get state() { return tree?.props['data-offer-state']; },
    get sessionCalls() { return sessionCalls; }, get writesAfterUnmount() { return writesAfterUnmount; },
    get reloads() { return slots.filter(s => s.kind === 'state')[2].value; },
    advance(ms = INTERVAL) { now += ms; },
    consent(value) { consent = value; for (const callback of [...subscribers]) callback(); },
    changeProduct(id) { props = { productId: id }; render(); commit(); },
    renderProductBeforeEffects(id) { props = { productId: id }; render(); return tree; },
    async resolve(index, value) { requests[index].resolve(value); await flush(); },
    async reject(index) { requests[index].reject(new Error('fixture unavailable')); await flush(); },
    unmount() { for (const slot of slots) if (slot.kind === 'effect') slot.cleanup?.(); mounted = false; },
  };
}
function nodes(tree, predicate) {
  if (!tree || typeof tree !== 'object') return [];
  if (Array.isArray(tree)) return tree.flatMap(t => nodes(t, predicate));
  return [...(predicate(tree) ? [tree] : []), ...nodes(tree.props?.children, predicate)];
}
const merchantLinks = tree => nodes(tree, n => n.type === 'a' && n.props.href?.startsWith('/fixture/'));
const tests = [];
const test = (name, run) => tests.push({ name, run });

test('initial functional load requires no consent', async () => {
  const h = makeHarness(); await h.flush(); assert.equal(h.requests.length, 1);
  assert.equal(h.state, 'loading'); await h.resolve(0, offerPayload());
  assert.equal(h.state, 'available'); assert.equal(merchantLinks(h.tree).length, 1);
  assert.equal(h.analytics.length, 0); assert.equal(h.sessionCalls, 0); h.unmount();
});
test('hidden tabs do not fetch', async () => {
  const h = makeHarness(); await h.resolve(0, offerPayload()); h.advance();
  h.document.visibilityState = 'hidden'; h.emit('document', 'visibilitychange');
  h.emit('window', 'pageshow'); await h.flush(); assert.equal(h.requests.length, 1); h.unmount();
});
test('return below threshold stays idle', async () => {
  const h = makeHarness(); await h.resolve(0, offerPayload()); h.advance(INTERVAL - 1);
  h.emit('document', 'visibilitychange'); await h.flush(); assert.equal(h.requests.length, 1); h.unmount();
});
async function realReload(input = source) {
  const h = makeHarness(input); await h.resolve(0, offerPayload()); h.advance();
  h.emit('document', 'visibilitychange'); await h.flush();
  assert.equal(h.requests.length, 2, 'Return must execute a second GET, not only update a counter');
  assert.equal(h.state, 'loading'); assert.equal(merchantLinks(h.tree).length, 0);
  await h.resolve(1, emptyPayload()); assert.equal(h.state, 'empty');
  assert.equal(merchantLinks(h.tree).length, 0); h.unmount();
}
test('actual second GET replaces old offer with authoritative empty state', () => realReload());
test('simultaneous events deduplicate before commit', async () => {
  const h = makeHarness(); await h.resolve(0, offerPayload()); h.advance();
  h.emit('document', 'visibilitychange'); h.emit('window', 'pageshow'); h.emit('document', 'visibilitychange');
  assert.equal(h.reloads, 1); await h.flush(); assert.equal(h.requests.length, 2); h.unmount();
});
test('later back-forward restoration fetches again', async () => {
  const h = makeHarness(); await h.resolve(0, offerPayload());
  for (let i = 1; i <= 2; i++) { h.advance(); h.emit('window', 'pageshow'); await h.flush();
    assert.equal(h.requests.length, i + 1); await h.resolve(i, emptyPayload()); }
  h.unmount();
});
test('initial error has working functional retry', async () => {
  const h = makeHarness(); await h.reject(0); assert.equal(h.state, 'error');
  const button = nodes(h.tree, n => n.type === 'button')[0]; assert.ok(button);
  button.props.onClick(); await h.flush(); assert.equal(h.requests.length, 2);
  await h.resolve(1, offerPayload()); assert.equal(h.state, 'available'); h.unmount();
});
test('failed revalidation cannot restore old merchant CTA', async () => {
  const h = makeHarness(); await h.resolve(0, offerPayload()); h.advance(); h.emit('window', 'pageshow');
  await h.flush(); await h.reject(1); assert.equal(h.state, 'error');
  assert.equal(merchantLinks(h.tree).length, 0); h.unmount();
});
test('null response is error rather than empty success', async () => {
  const h = makeHarness(); await h.resolve(0, null); assert.equal(h.state, 'error'); h.unmount();
});
async function lateReply(input = source) {
  const h = makeHarness(input); await h.flush(); h.advance(); h.emit('window', 'pageshow');
  await h.flush(); assert.equal(h.requests.length, 2); await h.resolve(1, emptyPayload());
  await h.resolve(0, offerPayload()); assert.equal(h.state, 'empty', 'Old response replaced newer result'); h.unmount();
}
test('late earlier response is ignored after return', () => lateReply());
test('late former product response cannot replace current product', async () => {
  const h = makeHarness(); await h.flush(); h.changeProduct(PRODUCT_B); await h.flush();
  assert.equal(h.requests[1].productId, PRODUCT_B); await h.resolve(1, offerPayload(PRODUCT_B));
  await h.resolve(0, offerPayload(PRODUCT_A)); assert.ok(merchantLinks(h.tree)[0].props.href.includes(PRODUCT_B)); h.unmount();
});
test('unmount removes listeners and ignores pending response', async () => {
  const h = makeHarness(); await h.flush(); h.unmount();
  assert.equal(h.listeners.document.size, 0); assert.equal(h.listeners.window.size, 0); assert.equal(h.subscribers.size, 0);
  await h.resolve(0, offerPayload()); assert.equal(h.writesAfterUnmount, 0);
});
test('consented refresh never creates duplicate view or clickout events', async () => {
  const h = makeHarness(source, { consent: true }); await h.resolve(0, offerPayload());
  const baseline = h.analytics.length; assert.equal(baseline, 2);
  h.advance(); h.emit('window', 'pageshow'); await h.flush(); await h.resolve(1, offerPayload());
  assert.equal(h.analytics.length, baseline); assert.ok(h.analytics.every(e => e.event !== 'merchant_clickout')); h.unmount();
});
test('consent grant and revoke do not reload functional offers', async () => {
  const h = makeHarness(); await h.resolve(0, offerPayload()); h.consent(true); await h.flush();
  assert.equal(h.requests.length, 1); assert.equal(h.analytics.length, 2);
  h.consent(false); await h.flush(); assert.equal(h.requests.length, 1); h.unmount();
});
test('listeners remain single across product switches', async () => {
  const h = makeHarness(); await h.resolve(0, offerPayload()); h.changeProduct(PRODUCT_B); await h.flush();
  assert.equal(h.listeners.document.get('visibilitychange').size, 1);
  assert.equal(h.listeners.window.get('pageshow').size, 1); h.unmount();
});

test('new product render never exposes previous product merchant CTA before effects', async () => {
  const h = makeHarness(); await h.resolve(0, offerPayload(PRODUCT_A));
  assert.equal(merchantLinks(h.tree).length, 1);
  const firstRender = h.renderProductBeforeEffects(PRODUCT_B);
  assert.equal(merchantLinks(firstRender).length, 0, 'Product B temporarily displays product A merchant link');
  assert.equal(firstRender.props['data-offer-state'], 'loading'); h.unmount();
});
test('wrong-product API response cannot become a purchase option', async () => {
  const h = makeHarness(); await h.resolve(0, offerPayload(PRODUCT_B));
  assert.equal(h.state, 'error', 'Mismatched response was treated as available');
  assert.equal(merchantLinks(h.tree).length, 0); h.unmount();
});

const results = [];
for (const { name, run } of tests) {
  try { await run(); results.push({ name, status: 'PASS' }); }
  catch (error) { results.push({ name, status: 'FAIL', detail: error.message }); }
}
const dependencyAnchor = '  }, [analyticsSurface, productId, reloadToken, trackProductOpen]);\n\n  useEffect(() => {\n    const recheckOnReturn';
assert.ok(source.includes(dependencyAnchor));
const mutants = [
  { name: 'missing functional reload dependency', text: source.replace(dependencyAnchor, dependencyAnchor.replace('productId, reloadToken,', 'productId,')), run: realReload },
  { name: 'old response guard removed', text: source.replace('      .then((value) => {\n        if (!active) return;', '      .then((value) => {'), run: lateReply },
];
const mutationResults = [];
for (const mutant of mutants) {
  assert.notEqual(mutant.text, source, 'Mutation did not change source: ' + mutant.name);
  try { await mutant.run(mutant.text); mutationResults.push({ name: mutant.name, status: 'SURVIVED' }); }
  catch (error) { mutationResults.push({ name: mutant.name, status: 'KILLED', detail: error.message }); }
}
const ok = results.every(r => r.status === 'PASS') && mutationResults.every(r => r.status === 'KILLED');
console.log(JSON.stringify({ status: ok ? 'PASS' : 'FAIL', cases: results.length, results, mutationResults,
  realNetworkRequests: 0, merchantClickouts: 0, pollingTimers: 0,
  limitation: 'Deterministic source-transpiled hook/JSX tests, not React DOM, browser, iPhone, full build or deployed CI.' }, null, 2));
if (!ok) process.exitCode = 1;
