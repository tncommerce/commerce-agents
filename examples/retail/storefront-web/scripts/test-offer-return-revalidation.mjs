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
const NOW = Date.parse('2026-10-20T06:00:00Z');
const MAX_AGE = 72 * 60 * 60 * 1000;
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
const expiringPayload = (remaining = 1_000, id = PRODUCT_A) => {
  const value = offerPayload(id);
  value.offers[0].last_updated_at = new Date(NOW - MAX_AGE + remaining).toISOString();
  return value;
};

function makeHarness(input = source, { consent = false, productId = PRODUCT_A, intersectionObserver = false } = {}) {
  const compiled = ts.transpileModule(input, { reportDiagnostics: true, compilerOptions: {
    module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2022,
    jsx: ts.JsxEmit.ReactJSX, esModuleInterop: true,
  }});
  assert.deepEqual(compiled.diagnostics, []);
  let now = NOW, index = 0, dirty = false, mounted = true, tree;
  let pendingEffects = [], pendingLayoutEffects = [], props = { productId }, sessionCalls = 0;
  let writesAfterUnmount = 0;
  let nextTimerId = 1, timerSchedules = 0;
  const timers = new Map();
  const slots = [], requests = [], analytics = [], subscribers = new Set();
  const listeners = { document: new Map(), window: new Map() };
  const activeObservers = new Set();
  class FixtureIntersectionObserver {
    constructor(callback, options) {
      this.callback = callback;
      assert.deepEqual(Array.from(options.threshold), [0.35], 'Visibility threshold changed');
    }
    observe(node) {
      assert.ok(node?.fixtureNode, 'Observer must inspect the rendered offers section');
      this.node = node;
      activeObservers.add(this);
    }
    disconnect() {
      this.node = null;
      activeObservers.delete(this);
    }
  }
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
    useLayoutEffect(callback, deps) {
      const slot = useSlot('layout-effect', () => ({ deps: undefined, cleanup: undefined }));
      if (!sameDeps(slot.deps, deps)) pendingLayoutEffects.push({ slot, callback, deps });
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
      appendAcquisitionAttribution: (href) => consent ? `${href}?measurement=granted-v1` : href,
      ensureAnalyticsSession: async () => { sessionCalls += 1; return null; },
      trackAnalyticsEvent: async (event, payload) => { analytics.push({ event, payload }); },
    },
    '@/lib/measurementConsent': {
      measurementAllowed: () => consent,
      subscribeMeasurement: (callback) => { subscribers.add(callback); return () => subscribers.delete(callback); },
    },
    '@/lib/officialProductPages': { OFFICIAL_PRODUCT_PAGES: {} },
    '@/components/AcquisitionInternalLink': { default: () => null },
    '@/components/CatalogReturnLink': { default: () => null },
    './FragranceOffers.module.css': { default: {} },
  };
  const module = { exports: {} };
  vm.runInNewContext(compiled.outputText, {
    module, exports: module.exports, document, window,
    IntersectionObserver: intersectionObserver ? FixtureIntersectionObserver : undefined,
    Date: class ClockDate extends Date { static now() { return now; } },
    require(id) { assert.ok(id in stubs, `Unexpected import ${id}`); return stubs[id]; },
    setTimeout(callback, delay) {
      assert.ok(Number.isFinite(delay) && delay > 0 && delay < 2 ** 31, 'Invalid deadline timer');
      const id = nextTimerId++;
      timerSchedules += 1;
      timers.set(id, { callback, dueAt: now + delay });
      return id;
    },
    clearTimeout(id) { timers.delete(id); },
    setInterval() { throw new Error('Unexpected polling'); },
    fetch() { throw new Error('Real network forbidden in offline regression'); },
  }, { timeout: 1500 });
  const render = () => {
    index = 0; dirty = false; pendingEffects = []; pendingLayoutEffects = [];
    tree = module.exports.default(props);
  };
  const commitLayout = () => {
    // Model DOM-ref attachment and commit-bound ownership before passive effects.
    // This is deterministic phase control, not a replacement for React DOM QA.
    for (const slot of slots) if (slot.kind === 'ref' && slot.value.current?.fixtureNode) slot.value.current = null;
    if (tree?.props.ref) tree.props.ref.current = { fixtureNode: true };
    const effects = pendingLayoutEffects; pendingLayoutEffects = [];
    for (const { slot } of effects) slot.cleanup?.();
    for (const { slot, callback, deps } of effects) { slot.deps = deps; slot.cleanup = callback(); }
  };
  const commitPassive = () => {
    const effects = pendingEffects; pendingEffects = [];
    for (const { slot } of effects) slot.cleanup?.();
    for (const { slot, callback, deps } of effects) { slot.deps = deps; slot.cleanup = callback(); }
  };
  const commit = () => { commitLayout(); commitPassive(); };
  const unmountLayout = () => {
    for (const slot of slots) {
      if (slot.kind === 'layout-effect') { slot.cleanup?.(); slot.cleanup = undefined; }
    }
    mounted = false;
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
    get observedCount() { return activeObservers.size; },
    intersect(ratio, isIntersecting = ratio > 0) {
      for (const observer of [...activeObservers]) {
        observer.callback([{ isIntersecting, intersectionRatio: ratio }]);
      }
    },
    get tree() { return tree; }, get state() { return tree?.props['data-offer-state']; },
    get sessionCalls() { return sessionCalls; }, get writesAfterUnmount() { return writesAfterUnmount; },
    get pendingTimers() { return [...timers.values()]; },
    get timerSchedules() { return timerSchedules; },
    get reloads() { return slots.filter(s => s.kind === 'state')[2].value; },
    advance(ms = INTERVAL) { now += ms; },
    runDueTimers() {
      for (const [id, timer] of [...timers]) {
        if (timer.dueAt <= now) { timers.delete(id); timer.callback(); }
      }
    },
    consent(value) { consent = value; for (const callback of [...subscribers]) callback(); },
    changeProduct(id) { props = { productId: id }; render(); commit(); },
    renderProductBeforeEffects(id) { props = { productId: id }; render(); return tree; },
    renderPropsBeforeEffects(next) { props = { ...props, ...next }; render(); return tree; },
    renderPendingBeforeEffects() { render(); return tree; },
    commitLayoutEffects() { commitLayout(); },
    commitPendingEffects() { commit(); },
    abortProductRender(id) {
      const committedProps = props, committedTree = tree;
      props = { productId: id }; render();
      props = committedProps; tree = committedTree;
      pendingLayoutEffects = []; pendingEffects = [];
    },
    async resolve(index, value) { requests[index].resolve(value); await flush(); },
    async reject(index) { requests[index].reject(new Error('fixture unavailable')); await flush(); },
    unmountLayout,
    unmount() { unmountLayout(); for (const slot of slots) if (slot.kind === 'effect') slot.cleanup?.(); },
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
test('verified merchant CTA remains available while consented analytics session is optional', async () => {
  const h = makeHarness(source, { consent: true });
  await h.resolve(0, offerPayload());
  assert.equal(h.state, 'available');
  assert.equal(merchantLinks(h.tree).length, 1, 'Verified buying cannot wait on optional analytics transport');
  assert.equal(nodes(h.tree, n => n.props?.['data-clickout-preparing']).length, 0);
  assert.equal(h.sessionCalls, 0, 'Component must not block buying on session creation');
  assert.ok(h.analytics.every(event => event.event !== 'merchant_clickout'), 'No clickout before real action');
  h.unmount();
});
test('consent changes never replace a verified CTA with a blocked placeholder', async () => {
  const h = makeHarness();
  await h.resolve(0, offerPayload());
  assert.ok(!merchantLinks(h.tree)[0].props.href.includes('measurement='));
  h.consent(true); await h.flush();
  assert.equal(merchantLinks(h.tree).length, 1);
  assert.ok(merchantLinks(h.tree)[0].props.href.endsWith('?measurement=granted-v1'), 'Consent grant must decorate active merchant href without an API session');
  assert.equal(h.sessionCalls, 0);
  h.consent(false); await h.flush();
  assert.equal(merchantLinks(h.tree).length, 1);
  assert.ok(!merchantLinks(h.tree)[0].props.href.includes('measurement='), 'Withdrawal must immediately strip optional tracking from merchant href');
  assert.equal(nodes(h.tree, n => n.props?.['data-clickout-preparing']).length, 0);
  h.unmount();
});

async function assertNoSyntheticOfferImpression(input = source) {
  const h = makeHarness(input, { consent: true, intersectionObserver: false });
  await h.resolve(0, offerPayload());
  assert.equal(h.state, 'available');
  assert.equal(merchantLinks(h.tree).length, 1, 'Missing observer must not disable functional buying');
  assert.deepEqual(h.analytics.map(e => e.event), ['fragrance_detail_view'],
    'A missing visibility API is not evidence of an offer impression');
  assert.equal(h.observedCount, 0);
  h.unmount();
}
test('unsupported IntersectionObserver does not invent an offer impression', assertNoSyntheticOfferImpression);
test('visible-offer impression only after verified 35% intersection', async () => {
  const h = makeHarness(source, { consent: true, intersectionObserver: true });
  await h.resolve(0, offerPayload());
  assert.equal(h.analytics.length, 1, 'No view before intersection callback');
  assert.equal(h.observedCount, 1);
  h.intersect(0.34); assert.equal(h.analytics.length, 1, 'Below threshold is not a view');
  h.intersect(0.9, false); assert.equal(h.analytics.length, 1, 'Not intersecting is not a view');
  h.intersect(0.35, true);
  assert.deepEqual(h.analytics.map(e => e.event), ['fragrance_detail_view', 'offer_section_view']);
  h.intersect(1, true);
  assert.equal(h.analytics.length, 2, 'Repeated observer callbacks never duplicate events');
  assert.equal(h.observedCount, 0, 'Observer disconnects after success');
  h.unmount();
});
test('no eligible offer does not produce view or observer', async () => {
  const h = makeHarness(source, { consent: true, intersectionObserver: true });
  await h.resolve(0, emptyPayload());
  assert.equal(h.observedCount, 0);
  h.intersect(1);
  assert.deepEqual(h.analytics.map(e => e.event), ['fragrance_detail_view']);
  assert.equal(merchantLinks(h.tree).length, 0); h.unmount();
});
test('grant after load never equates to a visible-offer event', async () => {
  const h = makeHarness(source, { consent: false, intersectionObserver: true });
  await h.resolve(0, offerPayload());
  assert.equal(h.analytics.length, 0);
  h.consent(true); await h.flush();
  assert.deepEqual(h.analytics.map(e => e.event), ['fragrance_detail_view']);
  assert.equal(h.observedCount, 1);
  h.consent(false); await h.flush(); h.intersect(1);
  assert.equal(h.analytics.length, 1, 'Withdrawal prevents view event');
  assert.equal(h.observedCount, 0); h.unmount();
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
  const h = makeHarness(source, { consent: true, intersectionObserver: true }); await h.resolve(0, offerPayload());
  assert.equal(h.analytics.length, 1, 'Loading an offer is not proof of visibility');
  h.intersect(0.5);
  const baseline = h.analytics.length; assert.equal(baseline, 2);
  h.advance(); h.emit('window', 'pageshow'); await h.flush(); await h.resolve(1, offerPayload());
  assert.equal(h.analytics.length, baseline); assert.ok(h.analytics.every(e => e.event !== 'merchant_clickout')); h.unmount();
});
test('consent grant and revoke do not reload functional offers', async () => {
  const h = makeHarness(source, { intersectionObserver: true }); await h.resolve(0, offerPayload()); h.consent(true); await h.flush();
  assert.equal(h.analytics.length, 1, 'Consent alone must not assert offer visibility');
  h.intersect(0.5);
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

test('return render hides old merchant CTA before the passive fetch effect', async () => {
  const h = makeHarness(); await h.resolve(0, offerPayload(PRODUCT_A));
  h.advance(); h.emit('window', 'pageshow');
  const firstRender = h.renderPendingBeforeEffects();
  assert.equal(firstRender.props['data-offer-state'], 'loading');
  assert.equal(merchantLinks(firstRender).length, 0, 'Return render still exposes the old quote');
  h.unmount();
});
test('new product render cannot inherit the previous product error state', async () => {
  const h = makeHarness(); await h.resolve(0, null); assert.equal(h.state, 'error');
  const firstRender = h.renderProductBeforeEffects(PRODUCT_B);
  assert.equal(firstRender.props['data-offer-state'], 'loading');
  assert.equal(merchantLinks(firstRender).length, 0);
  h.unmount();
});

async function visibleDeadline(input = source) {
  const h = makeHarness(input, { consent: true, intersectionObserver: true });
  await h.resolve(0, expiringPayload());
  h.intersect(0.5);
  const measured = h.analytics.length;
  assert.equal(h.pendingTimers.length, 1);
  h.advance(999); h.runDueTimers(); await h.flush();
  assert.equal(h.requests.length, 1, 'A deadline must not become periodic polling');
  h.advance(1); h.runDueTimers();
  const firstRender = h.renderPendingBeforeEffects();
  assert.equal(firstRender.props['data-offer-state'], 'loading');
  assert.equal(merchantLinks(firstRender).length, 0, 'Expired quote survived until the fetch effect');
  h.commitPendingEffects(); await h.flush();
  assert.equal(h.requests.length, 2, 'Continuously visible page did not revalidate at expiry');
  assert.equal(h.pendingTimers.length, 0, 'Pending read must not keep a deadline timer');
  await h.resolve(1, emptyPayload());
  assert.equal(h.state, 'empty');
  assert.equal(merchantLinks(h.tree).length, 0);
  assert.equal(h.analytics.length, measured, 'Functional expiry emitted a measurement event');
  assert.ok(h.analytics.every(event => event.event !== 'merchant_clickout'));
  h.unmount();
}
test('continuously visible page revalidates once at the offer deadline', visibleDeadline);
test('earliest offer expiry triggers a fresh authoritative ranking', async () => {
  const h = makeHarness();
  const first = expiringPayload(1_000);
  const second = { ...expiringPayload(3_000).offers[0], offer_id: 'second-offer', clickout_path: '/fixture/second' };
  first.offers.push(second);
  await h.resolve(0, first);
  assert.equal(h.pendingTimers[0].dueAt, NOW + 1_000);
  h.advance(1_000); h.runDueTimers(); await h.flush();
  assert.equal(merchantLinks(h.tree).length, 0, 'Do not invent a new ranking while revalidating');
  await h.resolve(1, { ...first, offers: [second], best_offer_id: second.offer_id });
  assert.equal(h.state, 'available');
  assert.equal(merchantLinks(h.tree).length, 1);
  assert.equal(h.pendingTimers.length, 1);
  assert.equal(h.pendingTimers[0].dueAt, NOW + 3_000);
  h.unmount();
});
async function staleReplyDoesNotLoop(input = source) {
  const h = makeHarness(input);
  const payload = expiringPayload();
  await h.resolve(0, payload);
  h.advance(1_000); h.runDueTimers(); await h.flush();
  assert.equal(h.requests.length, 2);
  await h.resolve(1, payload);
  assert.equal(h.state, 'error', 'Expired cached response must not restore the CTA');
  assert.equal(merchantLinks(h.tree).length, 0);
  assert.equal(h.pendingTimers.length, 0);
  h.advance(MAX_AGE); h.runDueTimers(); await h.flush();
  assert.equal(h.requests.length, 2, 'Expired response started an automatic retry loop');
  h.unmount();
}
test('expired response settles as an error without an automatic refetch loop', staleReplyDoesNotLoop);
for (const [name, timestamp] of [
  ['invalid', 'not-a-timestamp'],
  ['expired', new Date(NOW - MAX_AGE - 1).toISOString()],
  ['at the expiry boundary', new Date(NOW - MAX_AGE).toISOString()],
  ['materially future-dated', new Date(NOW + INTERVAL + 1).toISOString()],
]) {
  test(`${name} incoming offer timestamp never becomes a purchase option`, async () => {
    const h = makeHarness(); const payload = offerPayload();
    payload.offers[0].last_updated_at = timestamp;
    await h.resolve(0, payload);
    assert.equal(h.state, 'error'); assert.equal(merchantLinks(h.tree).length, 0);
    assert.equal(h.pendingTimers.length, 0); assert.equal(h.requests.length, 1);
    h.unmount();
  });
}
test('consent rerenders keep the same absolute deadline', async () => {
  const h = makeHarness(); await h.resolve(0, expiringPayload());
  h.advance(400); h.consent(true); await h.flush();
  h.consent(false); await h.flush();
  assert.equal(h.timerSchedules, 1, 'Unrelated rerenders restarted the timer');
  assert.equal(h.pendingTimers.length, 1);
  assert.equal(h.pendingTimers[0].dueAt, NOW + 1_000);
  assert.equal(h.requests.length, 1); h.unmount();
});
test('hidden expiry defers its read until return even below five minutes', async () => {
  const h = makeHarness(); await h.resolve(0, expiringPayload());
  h.document.visibilityState = 'hidden';
  h.advance(1_000); h.runDueTimers(); await h.flush();
  assert.equal(h.requests.length, 1, 'Hidden deadline performed an unnecessary fetch');
  assert.equal(h.pendingTimers.length, 0);
  h.document.visibilityState = 'visible'; h.emit('document', 'visibilitychange'); await h.flush();
  assert.equal(h.requests.length, 2, 'Expiry must override the normal return delay');
  assert.equal(h.state, 'loading'); assert.equal(merchantLinks(h.tree).length, 0);
  await h.resolve(1, emptyPayload()); assert.equal(h.state, 'empty'); h.unmount();
});
for (const timerFirst of [true, false]) {
  test(`deadline and return events deduplicate with ${timerFirst ? 'timer' : 'return'} first`, async () => {
    const h = makeHarness(); await h.resolve(0, expiringPayload());
    const queuedTimer = h.pendingTimers[0].callback;
    h.advance(1_000);
    if (timerFirst) h.runDueTimers();
    h.emit('window', 'pageshow'); h.emit('document', 'visibilitychange');
    if (!timerFirst) h.runDueTimers();
    assert.equal(h.reloads, 1); await h.flush(); assert.equal(h.requests.length, 2);
    await h.resolve(1, emptyPayload()); queuedTimer(); await h.flush();
    assert.equal(h.requests.length, 2, 'Queued old deadline restarted a newer request');
    h.unmount();
  });
}
test('committed product change rejects an old queued deadline before passive cleanup', async () => {
  const h = makeHarness(); await h.resolve(0, expiringPayload());
  const queuedTimer = h.pendingTimers[0].callback;
  h.advance(1_000); h.renderProductBeforeEffects(PRODUCT_B); h.commitLayoutEffects(); queuedTimer();
  assert.equal(h.reloads, 0, 'Previous product timer invalidated the new product');
  assert.equal(merchantLinks(h.tree).length, 0);
  h.commitPendingEffects(); await h.flush(); await h.resolve(1, offerPayload(PRODUCT_B));
  assert.equal(h.requests.length, 2); assert.equal(h.pendingTimers.length, 1);
  assert.ok(merchantLinks(h.tree)[0].props.href.includes(PRODUCT_B)); h.unmount();
});
test('unmount cancels deadline and ignores an already queued callback', async () => {
  const h = makeHarness(); await h.resolve(0, expiringPayload());
  const queuedTimer = h.pendingTimers[0].callback;
  h.unmount(); assert.equal(h.pendingTimers.length, 0);
  h.advance(1_000); queuedTimer(); await h.flush();
  assert.equal(h.writesAfterUnmount, 0); assert.equal(h.requests.length, 1);
});
test('expired offer cannot emit a queued visibility impression before timer cleanup', async () => {
  const h = makeHarness(source, { consent: true, intersectionObserver: true });
  await h.resolve(0, expiringPayload());
  h.advance(1_000); h.intersect(0.6);
  assert.deepEqual(h.analytics.map(event => event.event), ['fragrance_detail_view']);
  h.runDueTimers(); await h.flush();
  assert.equal(h.observedCount, 0); assert.equal(h.analytics.length, 1); h.unmount();
});
test('reserved revalidation blocks a queued impression before the next render', async () => {
  const h = makeHarness(source, { consent: true, intersectionObserver: true });
  await h.resolve(0, offerPayload());
  h.advance(); h.emit('window', 'pageshow'); h.intersect(0.6);
  assert.deepEqual(h.analytics.map(event => event.event), ['fragrance_detail_view']);
  await h.flush(); assert.equal(h.observedCount, 0); h.unmount();
});
test('committed product change blocks the previous queued impression before passive cleanup', async () => {
  const h = makeHarness(source, { consent: true, intersectionObserver: true });
  await h.resolve(0, offerPayload());
  h.renderProductBeforeEffects(PRODUCT_B); h.commitLayoutEffects(); h.intersect(0.6);
  assert.equal(h.analytics.filter(event => event.event === 'offer_section_view').length, 0);
  h.commitPendingEffects(); await h.flush(); await h.resolve(1, offerPayload(PRODUCT_B));
  h.intersect(0.6);
  const views = h.analytics.filter(event => event.event === 'offer_section_view');
  assert.equal(views.length, 1); assert.equal(views[0].payload.product_id, PRODUCT_B); h.unmount();
});
async function abortedRenderKeepsDeadline(input = source) {
  const h = makeHarness(input); await h.resolve(0, expiringPayload());
  h.abortProductRender(PRODUCT_B);
  assert.equal(h.state, 'available');
  assert.equal(h.pendingTimers.length, 1);
  h.advance(1_000); h.runDueTimers(); await h.flush();
  assert.equal(h.requests.length, 2, 'Aborted candidate render disabled the committed product deadline');
  assert.equal(h.requests[1].productId, PRODUCT_A);
  assert.equal(h.state, 'loading'); assert.equal(merchantLinks(h.tree).length, 0);
  await h.resolve(1, emptyPayload()); assert.equal(h.state, 'empty'); h.unmount();
}
test('aborted product render preserves the committed visible offer deadline', abortedRenderKeepsDeadline);
test('layout unmount invalidates callbacks before passive cleanup', async () => {
  const h = makeHarness(source, { consent: true, intersectionObserver: true });
  await h.resolve(0, expiringPayload()); const queuedTimer = h.pendingTimers[0].callback;
  h.unmountLayout(); h.advance(1_000); queuedTimer(); h.intersect(0.6);
  h.emit('window', 'pageshow');
  assert.equal(h.writesAfterUnmount, 0); assert.equal(h.requests.length, 1);
  assert.deepEqual(h.analytics.map(event => event.event), ['fragrance_detail_view']); h.unmount();
});
async function impressionOwnershipAfterPropChange(input = source) {
  const h = makeHarness(input, { consent: true, intersectionObserver: true });
  await h.resolve(0, offerPayload());
  h.renderPropsBeforeEffects({ trackProductOpen: false }); h.commitLayoutEffects();
  h.intersect(0.6);
  assert.equal(h.analytics.filter(event => event.event === 'offer_section_view').length, 0,
    'Previous committed observer recorded after ownership changed');
  h.commitPendingEffects(); h.intersect(0.6); h.intersect(0.6);
  const views = h.analytics.filter(event => event.event === 'offer_section_view');
  assert.equal(views.length, 1, 'Current same-product observer was not recreated after prop change');
  assert.equal(views[0].payload.product_id, PRODUCT_A);
  await h.flush(); await h.resolve(1, offerPayload()); h.intersect(0.6);
  assert.equal(h.analytics.filter(event => event.event === 'offer_section_view').length, 1,
    'Settling the functional refresh duplicated the current product impression');
  h.unmount();
}
test('trackProductOpen change replaces observer ownership without losing or duplicating the impression',
  impressionOwnershipAfterPropChange);

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
  { name: 'unsupported observer falsely counts an impression',
    text: source.replace('if (typeof IntersectionObserver === "undefined") {\n        // No viewport proof:',
                         'if (typeof IntersectionObserver === "undefined") {\n        trackImpression();\n        // No viewport proof:'),
    run: assertNoSyntheticOfferImpression },
  { name: 'deadline timer never reaches a continuously visible expiry',
    text: source.replace('Math.max(1, expiresAt - Date.now())', 'Math.max(1, expiresAt - Date.now()) + 60_000'),
    run: visibleDeadline },
  { name: 'expired response re-enters automatic revalidation',
    text: source.replace('deadline === null || deadline <= Date.now()', 'deadline === null'),
    run: staleReplyDoesNotLoop },
  { name: 'candidate render overwrites committed request ownership',
    text: source.replace('  useLayoutEffect(() => {\n    // Only a committed render',
      '  currentRequestRef.current = { expiresAt, revalidationPending: false };\n  useLayoutEffect(() => {\n    // Only a committed render'),
    run: abortedRenderKeepsDeadline },
  { name: 'impression observer misses a committed tracking-prop change',
    text: source.replace('response?.productId, response?.reloadToken, trackProductOpen]);',
      'response?.productId, response?.reloadToken]);'),
    run: impressionOwnershipAfterPropChange },
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
