import assert from 'node:assert/strict';
import { deferred, drain, measurementClient } from './measurement-vm-fixture.mjs';

const UUID = /^[a-f0-9]{8}-[a-f0-9]{4}-4[a-f0-9]{3}-[89ab][a-f0-9]{3}-[a-f0-9]{12}$/;
let cases = 0;
const pass = () => { cases++; };
// Existing positive ownership/recovery cases now deliberately grant permission.
// No runtime QA flag or production bypass is used to do so.
const client = (initialize, post, browserWindow, referrer = '') => measurementClient({
  initialize, post, browserWindow, referrer, choice: 'granted',
});
const browser = (session, search = '', blocked = false) => ({
  location: { origin: 'https://dufynd.test', search },
  sessionStorage: {
    getItem(key) { if (blocked) throw Error('denied'); return session.get(key) ?? null; },
    setItem(key, value) { if (blocked) throw Error('denied'); session.set(key, value); },
    removeItem(key) { if (blocked) throw Error('denied'); session.delete(key); },
  },
});

// Concurrent standalone reads share one initialization and retain normal retry.
{
  const pending = deferred(), env = client(() => pending.promise);
  const reads = [env.ensureAnalyticsSession(), env.ensureAnalyticsSession()];
  assert.equal(env.initializations, 1);
  pending.resolve('analytics-1');
  assert.deepEqual(await Promise.all(reads), ['analytics-1', 'analytics-1']);
  assert.equal(env.api.session, 'analytics-1'); pass();
}

// Advisor ownership wins over successful or failed late standalone initialization.
for (const lateResult of ['late-analytics', null]) {
  const pending = deferred(), env = client(() => pending.promise, async () => ({ ok: false }));
  const read = env.ensureAnalyticsSession();
  env.api.session = 'advisor-current'; pending.resolve(lateResult);
  assert.equal(await read, 'advisor-current');
  await env.trackAnalyticsEvent('page_view');
  assert.equal(env.requests[0].init.headers['X-Session-Id'], 'advisor-current');
  assert.equal(env.initializations, 1, 'Analytics cannot renew an advisor-owned session');
  assert.equal(env.api.session, 'advisor-current');
  assert.equal(env.timers.size, 0); pass();
}

// Failed telemetry cannot erase an advisor session established during that POST.
{
  const firstPost = deferred(), postStarted = deferred();
  const env = client(async attempt => `analytics-${attempt}`, attempt => {
    if (attempt === 1) { postStarted.resolve(); return firstPost.promise; }
    return Promise.resolve({ ok: true });
  });
  await env.ensureAnalyticsSession();
  const first = env.trackAnalyticsEvent('page_view');
  const queued = env.trackAnalyticsEvent('product_open', { product_id: 'SC-TEST' });
  await postStarted.promise;
  env.api.session = 'advisor-current'; firstPost.resolve({ ok: false });
  await Promise.all([first, queued]);
  assert.equal(env.api.session, 'advisor-current'); assert.equal(env.initializations, 1);
  assert.equal(env.requests.length, 2);
  assert.equal(env.requests[0].payload.event, 'page_view');
  assert.equal(env.requests[0].init.headers['X-Session-Id'], 'analytics-1');
  assert.equal(env.requests[1].payload.event, 'product_open');
  assert.equal(env.requests[1].init.headers['X-Session-Id'], 'advisor-current');
  assert.equal(env.requests[1].payload.analytics_session_id, env.requests[0].payload.analytics_session_id);
  assert.equal(env.timers.size, 0); pass();
}

// Bounded standalone recovery retains one logical event and independent funnel ID.
for (const retryOk of [true, false]) {
  const env = client(async attempt => `analytics-${attempt}`, async attempt => ({ ok: attempt > 1 && retryOk }));
  env.rememberAcquisitionAttribution({ source: 'tiktok', campaignId: 'session_qa' });
  await env.trackAnalyticsEvent('page_view');
  assert.equal(env.initializations, 2); assert.equal(env.requests.length, 2);
  assert.equal(env.requests[0].init.headers['X-Session-Id'], 'analytics-1');
  assert.equal(env.requests[1].init.headers['X-Session-Id'], 'analytics-2');
  assert.equal(env.requests[1].payload.campaign_id, 'session_qa');
  assert.match(env.requests[0].payload.event_id, UUID);
  assert.equal(env.requests[0].payload.event_id, env.requests[1].payload.event_id);
  const id = env.requests[0].payload.analytics_session_id;
  assert.match(id, UUID); assert.notEqual(id, 'analytics-1'); assert.notEqual(id, 'analytics-2');
  assert.equal(env.requests[1].payload.analytics_session_id, id);
  assert.equal(env.api.session, 'analytics-2'); assert.equal(env.timers.size, 0); pass();
}
{
  const env = client(async () => null);
  await env.trackAnalyticsEvent('page_view');
  assert.equal(env.api.session, null); assert.equal(env.requests.length, 0);
  assert.equal(env.timers.size, 0); pass();
}

// Full document navigation preserves the consented funnel ID, never the transport.
for (const original of ['11111111-1111-4111-8111-111111111111', 'qa_URLsafe-session_1234567890-abcd']) {
  const session = new Map(), window = browser(session);
  const replacement = '22222222-2222-4222-8222-222222222222';
  const first = client(async () => original, undefined, window);
  first.rememberAcquisitionAttribution({ source: 'instagram', campaignId: 'fm_campaign', contentId: 'fm_content' });
  await first.trackAnalyticsEvent('page_view');
  const id = first.requests[0].payload.analytics_session_id;
  assert.match(id, UUID); assert.notEqual(id, original);
  const nextDocument = client(async () => replacement, undefined, window);
  await nextDocument.trackAnalyticsEvent('fragrance_detail_view', { product_id: 'SC-TEST' });
  assert.equal(nextDocument.api.session, replacement, 'Never restore advisor transport from analytics storage');
  assert.equal(nextDocument.requests[0].payload.analytics_session_id, id);
  assert.equal(nextDocument.requests[0].init.headers['X-Session-Id'], replacement);
  assert.equal(nextDocument.requests[0].payload.content_id, 'fm_content');
  const target = new URL(nextDocument.appendAcquisitionAttribution('/api/clickout/qa-offer'));
  assert.equal(target.searchParams.get('sid'), id); assert.equal(target.searchParams.get('cmp'), 'fm_campaign');
  assert.equal(target.searchParams.get('measurement'), 'granted-v1'); pass();
}

// Invalid persisted identifiers or blocked optional storage cannot split retries.
for (const blocked of [false, true]) {
  const session = new Map([['dufynd_analytics_session_v1', 'invalid@example.com']]);
  const env = client(async n => `qa-transport-session-${n}-1234567890`, async n => ({ ok: n > 1 }), browser(session, '', blocked));
  await env.trackAnalyticsEvent('page_view');
  assert.equal(env.initializations, 2);
  const id = env.requests[0].payload.analytics_session_id;
  assert.match(id, UUID); assert.notEqual(id, 'qa-transport-session-1-1234567890');
  assert.equal(env.requests[1].payload.analytics_session_id, id);
  assert.equal(env.api.session, 'qa-transport-session-2-1234567890'); pass();
}

// A stored permission plus proven internal navigation may continue a URL ID.
// The same shared URL, missing referrer or impostor origin must not adopt it.
for (const referrer of ['https://dufynd.test/duft', 'https://instagram.com/', '', 'https://dufynd.test.evil.test/']) {
  const original = 'qa-original-funnel-123456789', replacement = 'qa-new-transport-123456789';
  const window = browser(new Map(), `?sid=${original}&src=tiktok&cmp=qa_site13&content=qa_profile`, true);
  const env = client(async () => replacement, undefined, window, referrer);
  await env.trackAnalyticsEvent('fragrance_detail_view', { product_id: 'SC-TEST' });
  const id = env.requests[0].payload.analytics_session_id;
  if (referrer === 'https://dufynd.test/duft') assert.equal(id, original);
  else { assert.match(id, UUID); assert.notEqual(id, original); }
  assert.notEqual(id, replacement); assert.equal(env.api.session, replacement);
  assert.equal(env.requests[0].payload.campaign_id, 'qa_site13'); pass();
}

// Classification persists only within a separately consented measurement flow.
{
  const window = browser(new Map(), '?qa=1');
  const env = client(async () => 'valid_analytics_session_123', undefined, window);
  await env.trackAnalyticsEvent('page_view'); assert.equal(env.requests[0].payload.internal_qa, true);
  window.location.search = '';
  const next = client(async () => 'valid_analytics_session_123', undefined, window);
  await next.trackAnalyticsEvent('fragrance_detail_view');
  assert.equal(next.requests[0].payload.internal_qa, true);
  assert.equal(new URL(next.appendAcquisitionAttribution('/api/clickout/fixture')).searchParams.get('qa'), '1'); pass();
}

// Negative controls are deliberately not passed through the positive wrapper.
for (const choice of ['unknown', 'denied']) {
  const env = measurementClient({ choice, search: '?qa=1&measurement=granted-v1', apiSession: 'advisor-keep' });
  assert.equal(await env.ensureAnalyticsSession(), null);
  await env.trackAnalyticsEvent('page_view'); await env.trackCatalogSearch('Libre', 1);
  assert.equal(env.initializations, 0); assert.equal(env.requests.length, 0);
  assert.equal(env.touched.reads, 0); assert.equal(env.touched.writes, 0);
  assert.equal(env.api.session, 'advisor-keep'); assert.equal(env.isInternalQa(), false); pass();
}
{
  const pending = deferred(); const env = measurementClient({ choice: 'granted', initialize: () => pending.promise });
  const read = env.ensureAnalyticsSession(); env.consent.setMeasurementChoice('denied');
  env.api.session = 'new-functional-advisor'; pending.resolve('revoked-late-analytics');
  assert.equal(await read, null); assert.equal(env.api.session, 'new-functional-advisor');
  assert.equal(await env.ensureAnalyticsSession(), null); pass();
}
{
  let aborted = false;
  const env = measurementClient({ choice: 'granted', post: (_n, init) => new Promise((_resolve, reject) => {
    init.signal.addEventListener('abort', () => { aborted = true; reject(Error('withdrawn')); });
  }) });
  const first = env.trackAnalyticsEvent('page_view'); await drain();
  const queued = env.trackAnalyticsEvent('product_open'); env.consent.setMeasurementChoice('denied');
  await Promise.all([first, queued]);
  assert.equal(aborted, true); assert.equal(env.requests.length, 1); assert.equal(env.initializations, 1);
  assert.equal(env.timers.size, 0); pass();
}
{
  const env = measurementClient({ ssr: true, choice: 'granted', apiSession: 'server-functional-session' });
  assert.equal(await env.ensureAnalyticsSession(), null); await env.trackAnalyticsEvent('page_view');
  assert.equal(env.requests.length, 0); assert.equal(env.api.session, 'server-functional-session'); pass();
}
console.log(JSON.stringify({ status: 'PASS', cases, suite: 'real consent/acquisition/analytics ownership integration', realNetworkRequests: 0 }));
