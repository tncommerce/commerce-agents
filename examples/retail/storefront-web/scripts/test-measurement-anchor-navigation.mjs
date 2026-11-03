// Compiled production modules; synthetic anchors, never a browser/network claim.
import assert from 'node:assert/strict';
import { pathToFileURL } from 'node:url';
import { measurementClient } from './measurement-vm-fixture.mjs';

const analyticsFile = process.argv[2] ? pathToFileURL(process.argv[2]) : undefined;
const origin = 'https://dufynd.test';
const page = `${origin}/duft/rabanne-1-million?audience=men`;
let cases = 0;
function fixture(choice) {
  return measurementClient({choice, analyticsFile, browserWindow: {
    location: {origin, href: page, search: '?audience=men'},
  }});
}
for (const choice of ['unknown', 'denied', 'granted']) {
  for (const fragment of ['#duftkatalog', '#angebote', '#', '#duftprofil']) {
    const f = fixture(choice), before = {...f.touched};
    assert.equal(f.appendAcquisitionAttribution(fragment), fragment,
      'Same-document anchors must remain raw, not acquire a homepage or identity');
    assert.deepEqual(f.touched, before, 'Fragment navigation needs no consent or optional storage read');
    assert.equal(f.initializations, 0);cases++;
  }
  for (const [href, pathname] of [
    ['?audience=women#duftkatalog', '/duft/rabanne-1-million'],
    ['./lancome-la-vie-est-belle#angebote', '/duft/lancome-la-vie-est-belle'],
    ['../marken', '/marken'],
  ]) {
    const f = fixture(choice), actual = new URL(f.appendAcquisitionAttribution(href), page);
    assert.equal(actual.origin, origin);assert.equal(actual.pathname, pathname);
    assert.equal(actual.hash, new URL(href, page).hash);
    assert.equal(actual.searchParams.has('sid'), choice === 'granted');
    if (href.startsWith('?')) assert.equal(actual.searchParams.get('audience'), 'women');
    assert.equal(f.touched.network, 0);cases++;
  }
}
function anchor(f, href) {
  let raw = href;
  return {
    get href() { return new URL(raw, f.window.location.href).href; },
    set href(value) { raw = String(value); },
    getAttribute(name) { return name === 'href' ? raw : null; },
  };
}
for (const choice of ['unknown', 'denied', 'granted']) {
  const f = fixture(choice);
  const anchors = [
    anchor(f, '#duftkatalog'), anchor(f, '/marken'),
    anchor(f, 'https://other.test/?sid=not_ours&src=their_campaign'),
    anchor(f, '/api/clickout/qa-offer?sid=old&cmp=old&measurement=granted-v1&sort=price#offers'),
  ];
  f.document.querySelectorAll = () => anchors;
  f.initializeMeasurementPrivacy();
  if (choice === 'granted') f.consent.setMeasurementChoice('denied');
  assert.equal(anchors[0].getAttribute('href'), '#duftkatalog');
  assert.equal(anchors[1].getAttribute('href'), '/marken');
  assert.equal(anchors[2].getAttribute('href'), 'https://other.test/?sid=not_ours&src=their_campaign');
  const redirect = new URL(anchors[3].href);
  for (const field of ['sid', 'cmp', 'measurement']) assert.equal(redirect.searchParams.has(field), false);
  assert.equal(redirect.pathname, '/api/clickout/qa-offer');
  assert.equal(redirect.searchParams.get('sort'), 'price');assert.equal(redirect.hash, '#offers');
  assert.equal(f.touched.network, 0);cases++;
}
// Hydration must see the same functional href as SSR. Deleting an absent URL
// parameter would still normalize %20 to + and turn a relative URL absolute.
for (const choice of ['unknown', 'denied', 'granted']) {
  const f = fixture(choice);
  const functional = [
    '/duft?q=Rosa%20Pfeffer#duftkatalog',
    '/duft?q=Thail%C3%A4ndisches%20Basilikum&marke=Essential%20Parfums',
    '/duft?q=Amber+wood&sort=brand',
  ];
  const anchors = functional.map(href => anchor(f, href));
  f.document.querySelectorAll = () => anchors;
  f.initializeMeasurementPrivacy();
  if (choice === 'granted') f.consent.setMeasurementChoice('denied');
  assert.deepEqual(anchors.map(item => item.getAttribute('href')), functional,
    'Privacy cleanup must not rewrite an untouched functional SSR link');
  assert.equal(f.touched.network, 0);cases++;
}
for (const field of ['sid', 'src', 'cmp', 'content', 'measurement', 'utm_source', 'utm_medium', 'utm_campaign', 'utm_content', 'utm_term']) {
  const f = fixture('denied');
  const decorated = anchor(f, `/duft?q=Rosa%20Pfeffer&${field}=old&${field}=#duftkatalog`);
  f.document.querySelectorAll = () => [decorated];
  f.initializeMeasurementPrivacy();
  const cleaned = new URL(decorated.href);
  assert.equal(cleaned.searchParams.has(field), false, `Remove all ${field} values, including empty duplicates`);
  assert.equal(cleaned.searchParams.get('q'), 'Rosa Pfeffer');
  assert.equal(cleaned.hash, '#duftkatalog');
  assert.equal(f.touched.network, 0);cases++;
}
console.log(JSON.stringify({status:'PASS',cases,networkRequests:0,
  scope:'Actual consent/acquisition/analytics modules in VM; no full-browser claim'}, null, 2));
