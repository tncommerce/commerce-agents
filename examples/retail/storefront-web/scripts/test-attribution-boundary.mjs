import assert from 'node:assert/strict';
import { measurementClient } from './measurement-vm-fixture.mjs';

const SID = 'qa_no_real_user_session_123456';
const UUID = /^[a-f0-9]{8}-[a-f0-9]{4}-4[a-f0-9]{3}-[89ab][a-f0-9]{3}-[a-f0-9]{12}$/;
const analyticsFile = process.argv[2] || new URL('../lib/analytics.ts', import.meta.url);
function fixture(options = {}) {
  return measurementClient({
    apiSession: SID, analyticsFile,
    search: '?src=instagram&cmp=qa_cmp&content=qa_content' + (options.qa ? '&qa=1' : ''),
    // Every positive destination case deliberately grants; negative consent
    // cases below call measurementClient directly without this wrapper.
    choice: 'granted', ...options,
  });
}
function untouched(f, url) {
  const before = { ...f.touched };
  assert.equal(f.appendAcquisitionAttribution(url), url, `Do not enrich: ${url}`);
  assert.deepEqual(f.touched, before, 'Rejected destination must not touch consent, optional storage or transport');
  assert.equal(f.initializations, 0);
}
function correctTarget(f, url, qa = false) {
  const actual = new URL(f.appendAcquisitionAttribution(url));
  const original = new URL(url, f.window.location.origin);
  assert.equal(actual.origin, original.origin); assert.equal(actual.pathname, original.pathname);
  assert.equal(actual.hash, original.hash);
  for (const [key, value] of original.searchParams) assert.equal(actual.searchParams.get(key), value);
  for (const [key, value] of [['src', 'instagram'], ['cmp', 'qa_cmp'], ['content', 'qa_content']]) {
    assert.equal(actual.searchParams.get(key), value);
  }
  const id = actual.searchParams.get('sid');
  assert.match(id, UUID); assert.notEqual(id, f.api.session, 'Measurement identity is not functional advisor transport');
  const repeated = new URL(f.appendAcquisitionAttribution(url));
  assert.equal(repeated.searchParams.get('sid'), id, 'One consented document keeps a stable measurement ID');
  const redirect = /\/(?:clickout\/[^/]+|merchant-partners\/[^/]+\/clickout)$/.test(actual.pathname);
  assert.equal(actual.searchParams.get('measurement'), redirect ? 'granted-v1' : null);
  assert.equal(actual.searchParams.get('qa'), qa ? '1' : null);
  assert.equal(f.touched.network, 0); assert.equal(f.initializations, 0);
}
const blocked = [
 'https://other.test/source',
 'https://other.test/api/clickout/offer1',
 'https://api.dufynd.test.evil.test/api/clickout/offer1',
 'https://dufynd.test.evil.test/duft',
 '//other.test/api/clickout/offer1',
 'https://user:password@dufynd.test/duft',
 'https://api.dufynd.test@other.test/api/clickout/offer1',
 'https://api.dufynd.test:444/api/clickout/offer1',
 'http://api.dufynd.test/api/clickout/offer1',
 'mailto:contact@example.test', 'tel:+49123456789',
 'javascript:void(0)', 'data:text/plain,hello', 'ftp://files.test/item',
 'https://[invalid',
 'https://api.dufynd.test/api/session',
 'https://api.dufynd.test/api/chat',
 'https://api.dufynd.test/api/analytics/events',
 'https://api.dufynd.test/api/clickout/',
 'https://api.dufynd.test/api/clickout/one/two',
 'https://api.dufynd.test/api/clickout/a%2Fb',
 'https://api.dufynd.test/api/clickout/a%5Cb',
 'https://api.dufynd.test/api/clickout/%zz',
 'https://api.dufynd.test/api/clickout/%20',
 'https://api.dufynd.test/api/clickout/%00',
 'https://api.dufynd.test/api/clickout/%2E%2E/session',
 'https://api.dufynd.test/clickout/offer1',
 '/api/session', '/api/chat', '/api/analytics/events', '/api/clickout/', '/api/clickout/a/b',
 'https://other.test/?src=their_source&cmp=their_campaign&sid=their_value#ref',
];
let cases = 0;
for (const qa of [false, true]) for (const url of blocked) {
  untouched(fixture({ qa }), url); cases++;
}
const allowed = [
 '/duft?q=Libre#angebote', '/marken', '/vergleich?left=SC-XERJOFF-NAXOS-100',
 'https://dufynd.test/duft/rabanne-1-million', '//dufynd.test/duft',
 '/api/clickout/perfumetrader-rabanne-1-million-edt-100',
 'https://api.dufynd.test/api/clickout/perfumetrader-rabanne-1-million-edt-100',
 'https://API.DUFYND.TEST:443/api/clickout/offer1',
];
for (const blockedStorage of [false, true]) for (const qa of [false, true]) for (const url of allowed) {
  const f = fixture({ blockedStorage, qa }); correctTarget(f, url, qa);
  assert.equal(f.api.session, SID); cases++;
}
for (const url of ['/duft', 'https://other.test/source']) {
  untouched(fixture({ ssr: true }), url); cases++;
}
for (const apiBase of ['https://api.dufynd.test/api/', 'https://api.dufynd.test/service/api']) {
  const f = fixture({ apiBase }); correctTarget(f, apiBase.replace(/\/$/, '') + '/clickout/offer1'); cases++;
}
{
  const f = fixture({ origin: 'http://localhost:3000', apiBase: 'http://localhost:8000/api' });
  correctTarget(f, 'http://localhost:8000/api/clickout/offer1');
  untouched(f, 'http://127.0.0.1:8000/api/clickout/offer1'); cases += 2;
}
{
  untouched(fixture({ apiBase: '%%%invalid' }), 'https://other.test/api/clickout/offer1'); cases++;
}
for (const apiBase of ['https://api.dufynd.test/api', 'https://api.dufynd.test/service/api/']) {
  const root = apiBase.replace(/\/$/, '');
  for (const blockedStorage of [false, true]) for (const qa of [false, true]) {
    for (const session of [SID, null]) for (const url of [
      `${root}/merchant-partners/perfumetrader/clickout?existing=1#merchant`,
      'https://dufynd.test/api/merchant-partners/perfumetrader/clickout',
    ]) {
      const f = fixture({ apiBase, blockedStorage, qa, apiSession: session });
      correctTarget(f, url, qa); assert.equal(f.api.session, session); cases++;
    }
  }
  for (const path of [
    '/merchant-partners', '/merchant-partners/', '/merchant-partners/perfumetrader',
    '/merchant-partners//clickout', '/merchant-partners/a/b/clickout',
    '/merchant-partners/perfumetrader/clickout/extra', '/merchant-partners/perfumetrader/clickout/',
    '/merchant-partners/%2f/clickout', '/merchant-partners/%5c/clickout',
    '/merchant-partners/%00/clickout', '/merchant-partners/%20/clickout',
    '/merchant-partners/%zz/clickout', '/merchant-partners/%2E%2E/clickout',
  ]) for (const origin of [root, 'https://dufynd.test/api']) {
    untouched(fixture({ apiBase, qa: true }), origin + path); cases++;
  }
}
for (const url of [
  'https://other.test/api/merchant-partners/perfumetrader/clickout',
  'https://api.dufynd.test.evil.test/api/merchant-partners/perfumetrader/clickout',
  'https://api.dufynd.test:444/api/merchant-partners/perfumetrader/clickout',
  'http://api.dufynd.test/api/merchant-partners/perfumetrader/clickout',
]) { untouched(fixture({ qa: true }), url); cases++; }
assert.equal(cases, 193, 'The original destination matrix is fully retained');

// Fresh/default and denied choices are real states, not an always-granted stub.
for (const choice of ['unknown', 'denied']) for (const blockedStorage of [false, true]) {
  for (const path of [
    '/duft', '/marken', '/api/clickout/offer1', '/api/merchant-partners/perfumetrader/clickout',
  ]) {
    const f = measurementClient({ choice, blockedStorage, analyticsFile, apiSession: SID,
      search: '?qa=1&measurement=granted-v1&src=instagram&sid=shared_identifier_12345' });
    const actual = new URL(f.appendAcquisitionAttribution(`${path}?q=rose&sid=old&src=x&cmp=y&content=z&measurement=granted-v1#offers`));
    for (const key of ['sid', 'src', 'cmp', 'content', 'measurement']) assert.equal(actual.searchParams.get(key), null);
    assert.equal(actual.pathname, path); assert.equal(actual.searchParams.get('q'), 'rose');
    assert.equal(actual.hash, '#offers'); assert.equal(f.api.session, SID);
    assert.equal(f.touched.reads, 0); assert.equal(f.touched.writes, 0);
    assert.equal(f.initializations, 0); assert.equal(f.touched.network, 0); cases++;
  }
}
for (const choice of ['unknown', 'denied']) for (const target of [
  'https://api.dufynd.test/api/clickout/offer1',
  'https://api.dufynd.test/api/merchant-partners/perfumetrader/clickout',
]) {
  const f = measurementClient({ choice, analyticsFile, search: '?qa=1&measurement=granted-v1' });
  const actual = new URL(f.appendAcquisitionAttribution(target));
  assert.equal(actual.toString(), target); assert.equal(f.consent.measurementAllowed(), false);
  assert.equal(f.touched.reads, 0); assert.equal(f.touched.writes, 0); assert.equal(f.initializations, 0); cases++;
}
console.log(JSON.stringify({ status: 'PASS', cases, originalDestinationCases: 193, unseededOrDeniedCases: 20,
  realNetworkRequests: 0, scope: 'actual consent/acquisition/analytics modules in one isolated VM' }));
