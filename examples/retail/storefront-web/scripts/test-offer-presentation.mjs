// Isolated React server-render checks; no API, sessions, or clickouts.
import assert from 'node:assert/strict';
import fs from 'node:fs';
import vm from 'node:vm';
import { createRequire } from 'node:module';
import ts from 'typescript';
import { renderToStaticMarkup } from 'react-dom/server';
const require = createRequire(import.meta.url);
// Keep the historical formatting fixture fresh only inside this isolated VM.
// Production expiry still uses the real clock; no source timestamp is renewed.
const NOW = Date.parse('2026-10-12T20:00:00Z');
const OFFER_MAX_AGE_MS = 72 * 60 * 60 * 1000;
const compile = (path, dependencies, now = NOW) => {
  const module = {exports:{}};
  vm.runInNewContext(ts.transpileModule(fs.readFileSync(new URL(path, import.meta.url),'utf8'), {
    compilerOptions:{module:ts.ModuleKind.CommonJS,jsx:ts.JsxEmit.ReactJSX,esModuleInterop:true},
  }).outputText, {
    module,exports:module.exports,require:dependencies,Intl,
    Date: class FixtureDate extends Date { static now() { return now; } },
  });
  return module.exports;
};
const money = compile('../../../web-shared/format.ts',require);
const fixture = {
  offer_id:'qa-offer',product_id:'SC-QA',merchant_id:'qa',merchant_name:'QA Händler',
  price:40,currency:'EUR',shipping_cost:4,total_price:44,shipping_label:'4 € Versand',
  in_stock:true,variant_label:'100 ml · Eau de Toilette',
  clickout_path:'/api/clickout/qa-offer',affiliate_link:true,last_updated_at:'2026-10-12T19:58:00Z',
};
function render({offers=[fixture],focusedLanding=false,error=false,loading=false,responseProductId='SC-QA',responseReloadToken=0,now=NOW}={}) {
  let stateIndex = 0;
  const payload={offers,product_id:'SC-QA',best_offer_id:'qa-offer',affiliate_disclosure:'QA'};
  // Seed the atomic request-bound state, not a pre-hardening bare payload.
  const response={productId:responseProductId,reloadToken:responseReloadToken,payload};
  const states=[loading?undefined:response,error,0,0];
  const source=compile('../components/FragranceOffers.tsx',(id)=>{
    if(id==='react')return {...require('react'),useState:()=>[states[stateIndex++],()=>{}],useEffect:()=>{},useRef:()=>({current:null})};
    if(id==='react/jsx-runtime')return require(id);
    if(id==='web-shared')return money;
    if(id==='@/lib/api')return {fetchMerchantOffers:()=>{throw Error('No API allowed')},merchantClickoutUrl:p=>p};
    if(id==='@/lib/analytics')return {appendAcquisitionAttribution:p=>p+'?src=qa&cmp=isolated&sid=qa-session',ensureAnalyticsSession:()=>{throw Error('No sessions allowed')},trackAnalyticsEvent:()=>{throw Error('No events allowed')}};
    // This suite renders supplied presentation states with effects disabled.
    // It must never invent consent or run the browser subscription during SSR.
    if(id==='@/lib/measurementConsent')return {
      measurementAllowed:()=>{throw Error('No consent reads in isolated SSR presentation')},
      subscribeMeasurement:()=>{throw Error('No browser subscriptions in isolated SSR presentation')},
    };
    if(id==='@/lib/officialProductPages')return {OFFICIAL_PRODUCT_PAGES:{}};
    if(id==='@/components/AcquisitionInternalLink' || id==='@/components/CatalogReturnLink')return {__esModule:true,default:({children,...props})=>require('react').createElement('a',props,children)};
    if(id.endsWith('.module.css'))return {__esModule:true,default:new Proxy({}, {get:(_,key)=>String(key)})};
    throw Error('Unexpected dependency '+id);
  },now);
  return renderToStaticMarkup(require('react').createElement(source.default,{productId:'SC-QA',focusedLanding}));
}
let cases=0;
for(const focusedLanding of [false,true]) {
  const html=render({focusedLanding});
  assert.match(html,/data-offer-breakdown/);
  assert.match(html,/44,00/); assert.match(html,/40,00/); assert.match(html,/4,00/);
  assert.match(html,/100 ml · Eau de Toilette/);
  assert.match(html,/12.10.2026, 21:58/);
  assert.match(html,/href="\/api\/clickout\/qa-offer\?src=qa&amp;cmp=isolated&amp;sid=qa-session"/);
  assert.match(html,/rel="sponsored noopener noreferrer"/);
  assert.match(html,/title="Öffnet einen neuen Tab"/);
  const action=html.match(/<a[^>]+href="\/api\/clickout[^>]*>(.*?)<\/a>/s)?.[1];
  assert.ok(action);
  // The decorative arrow is excluded; the accessible link name remains stable.
  assert.equal(action.replace(/<span aria-hidden="true"[^>]*>.*?<\/span>/s,'').trim(),'Bei QA Händler ansehen');
  assert.match(html,/<details/); assert.match(html,/Provision/); assert.match(html,/Retouren/);
  cases++;
}
const unknown=render({offers:[{...fixture,total_price:null,shipping_cost:null,shipping_label:null}]});
assert.match(unknown,/Artikelpreis · Versand beim Händler prüfen/);
assert.doesNotMatch(unknown,/Gesamtpreis inkl. Versand|data-offer-breakdown|44,00/);cases++;
const free=render({offers:[{...fixture,total_price:40,shipping_cost:0}]});
assert.match(free,/data-offer-breakdown/);assert.match(free,/0,00/);cases++;
// An offered purchase must not wait for analytics/session effects during SSR.
const withoutAnalyticsSession=render();
assert.doesNotMatch(withoutAnalyticsSession,/data-clickout-preparing/);
assert.match(withoutAnalyticsSession,/href="\/api\/clickout\/qa-offer/);cases++;
const external=render({offers:[{...fixture,affiliate_link:false}]});
assert.doesNotMatch(external,/sponsored|Werbung · Partnerlink/);assert.match(external,/keine Provision/);cases++;
for(const state of [{loading:true},{error:true},{offers:[]}]) {
 const html=render(state);assert.doesNotMatch(html,/href="\/api\/clickout|44,00/);cases++;
}
for(const state of [{responseProductId:'SC-OTHER'},{responseReloadToken:1}]) {
 const html=render(state);assert.match(html,/data-offer-state="loading"/);
 assert.doesNotMatch(html,/href="\/api\/clickout|data-offer-breakdown|44,00/);cases++;
}

// The VM clock must exercise the real expiry guard, not bypass it to make
// presentation fixtures pass. A visible price/CTA disappears at the deadline.
const deadline = Date.parse(fixture.last_updated_at) + OFFER_MAX_AGE_MS;
const beforeDeadline = render({now:deadline-1});
assert.match(beforeDeadline,/data-offer-state="available"/);
assert.match(beforeDeadline,/href="\/api\/clickout\/qa-offer/);cases++;
for(const now of [deadline,deadline+1]) {
 const html=render({now});assert.match(html,/data-offer-state="error"/);
 assert.doesNotMatch(html,/href="\/api\/clickout|data-offer-breakdown|44,00/);cases++;
}
for(const last_updated_at of ['invalid',new Date(NOW+5*60*1000+1).toISOString()]) {
 const html=render({offers:[{...fixture,last_updated_at}]});
 assert.match(html,/data-offer-state="error"/);
 assert.doesNotMatch(html,/href="\/api\/clickout|data-offer-breakdown|44,00/);cases++;
}

// Regression: editorial homepage spotlights cannot claim a live merchant offer.
// This is rendering-only; it never creates analytics sessions or affiliate clicks.
const spotlightFixtures = [
  {
    product_id: 'SC-LANCOME-LA-VIE-EST-BELLE-EDP-100',
    slug: 'lancome-la-vie-est-belle',
    brand: 'Lancôme', name: 'La Vie Est Belle',
    concentration: 'EDP', volume_ml: 100,
    notes: { top: [], heart: [], base: [], key: [] },
  },
  {
    product_id: 'SC-YSL-LIBRE-EDP-90',
    slug: 'yves-saint-laurent-libre',
    brand: 'Yves Saint Laurent', name: 'Libre',
    concentration: 'EDP', volume_ml: 90,
    notes: { top: [], heart: [], base: [], key: [] },
  },
];
const spotlight = compile('../components/AtelierSelection.tsx', id => {
  if(id==='react' || id==='react/jsx-runtime') return require(id);
  if(id==='@/lib/fragranceCatalog') return {
    LIVE_FRAGRANCES: spotlightFixtures,
    originalPhotoFor: () => ({ url: 'https://example.invalid/qa-only.png' }),
  };
  if(id==='@/lib/noteLabels') return {noteLabel: String};
  if(id==='@/lib/analytics') return {trackAnalyticsEvent: () => {
    throw Error('No analytics writes allowed during homepage render QA');
  }};
  if(id==='./AcquisitionInternalLink') return {__esModule:true,default:({children,onClick,...props}) =>
    require('react').createElement('a',props,children)};
  if(id==='./FragranceVisual') return {__esModule:true,default:({alt}) =>
    require('react').createElement('span',{'aria-label':alt})};
  if(id==='./ImageAttribution') return {__esModule:true,default:() => null};
  throw Error('Unexpected spotlight dependency '+id);
});
const spotlightMarkup = renderToStaticMarkup(require('react').createElement(spotlight.default));
assert.match(spotlightMarkup,/data-dufynd-home-selected-stage/);
assert.equal((spotlightMarkup.match(/Duftprofil entdecken/g)||[]).length,2);
assert.doesNotMatch(spotlightMarkup,/Duftprofil\s*&(amp;)?\s*Angebote/);
assert.doesNotMatch(spotlightMarkup,/Händlerangebote prüfen|Bei .* ansehen/);
assert.match(spotlightMarkup,/href="\/duft\/lancome-la-vie-est-belle"/);
assert.match(spotlightMarkup,/href="\/duft\/yves-saint-laurent-libre"/);
assert.doesNotMatch(spotlightMarkup,/href="[^"]*\/api\/clickout\//);
cases++;

console.log(JSON.stringify({status:'PASS',cases,networkRequests:0,merchantClicks:0,scope:'SSR offer presentation; no browser layout claim'}));
