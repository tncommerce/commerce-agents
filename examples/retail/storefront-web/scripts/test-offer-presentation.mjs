// Isolated React server-render checks; no API, sessions, or clickouts.
import assert from 'node:assert/strict';
import fs from 'node:fs';
import vm from 'node:vm';
import { createRequire } from 'node:module';
import ts from 'typescript';
import { renderToStaticMarkup } from 'react-dom/server';
const require = createRequire(import.meta.url);
const compile = (path, dependencies) => {
  const module = {exports:{}};
  vm.runInNewContext(ts.transpileModule(fs.readFileSync(new URL(path, import.meta.url),'utf8'), {
    compilerOptions:{module:ts.ModuleKind.CommonJS,jsx:ts.JsxEmit.ReactJSX,esModuleInterop:true},
  }).outputText, {module,exports:module.exports,require:dependencies,Date,Intl});
  return module.exports;
};
const money = compile('../../../web-shared/format.ts',require);
const fixture = {
  offer_id:'qa-offer',product_id:'SC-QA',merchant_id:'qa',merchant_name:'QA Händler',
  price:40,currency:'EUR',shipping_cost:4,total_price:44,shipping_label:'4 € Versand',
  in_stock:true,variant_label:'100 ml · Eau de Toilette',
  clickout_path:'/api/clickout/qa-offer',affiliate_link:true,last_updated_at:'2026-10-12T19:58:00Z',
};
function render({offers=[fixture],focusedLanding=false,ready=true,error=false,loading=false}={}) {
  let stateIndex = 0;
  const payload={offers,product_id:'SC-QA',best_offer_id:'qa-offer',affiliate_disclosure:'QA'};
  const states=[loading?undefined:payload,error,0,ready];
  const source=compile('../components/FragranceOffers.tsx',(id)=>{
    if(id==='react')return {...require('react'),useState:()=>[states[stateIndex++],()=>{}],useEffect:()=>{},useRef:()=>({current:null})};
    if(id==='react/jsx-runtime')return require(id);
    if(id==='web-shared')return money;
    if(id==='@/lib/api')return {fetchMerchantOffers:()=>{throw Error('No API allowed')},merchantClickoutUrl:p=>p};
    if(id==='@/lib/analytics')return {appendAcquisitionAttribution:p=>p+'?src=qa&cmp=isolated&sid=qa-session',ensureAnalyticsSession:()=>{throw Error('No sessions allowed')},trackAnalyticsEvent:()=>{throw Error('No events allowed')}};
    if(id==='@/lib/officialProductPages')return {OFFICIAL_PRODUCT_PAGES:{}};
    if(id==='@/components/AcquisitionInternalLink')return {__esModule:true,default:({children,...props})=>require('react').createElement('a',props,children)};
    if(id.endsWith('.module.css'))return {__esModule:true,default:new Proxy({}, {get:(_,key)=>String(key)})};
    throw Error('Unexpected dependency '+id);
  });
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
  assert.match(html,/öffnet einen neuen Tab/);
  assert.match(html,/<details/); assert.match(html,/Provision/); assert.match(html,/Retouren/);
  cases++;
}
const unknown=render({offers:[{...fixture,total_price:null,shipping_cost:null,shipping_label:null}]});
assert.match(unknown,/Artikelpreis · Versand beim Händler prüfen/);
assert.doesNotMatch(unknown,/Gesamtpreis inkl. Versand|data-offer-breakdown|44,00/);cases++;
const free=render({offers:[{...fixture,total_price:40,shipping_cost:0}]});
assert.match(free,/data-offer-breakdown/);assert.match(free,/0,00/);cases++;
const pending=render({ready:false});assert.match(pending,/data-clickout-preparing/);assert.doesNotMatch(pending,/href="\/api\/clickout/);cases++;
const external=render({offers:[{...fixture,affiliate_link:false}]});
assert.doesNotMatch(external,/sponsored|Werbung · Partnerlink/);assert.match(external,/keine Provision/);cases++;
for(const state of [{loading:true},{error:true},{offers:[]}]) {
 const html=render(state);assert.doesNotMatch(html,/href="\/api\/clickout|44,00/);cases++;
}
console.log(JSON.stringify({status:'PASS',cases,networkRequests:0,merchantClicks:0,scope:'SSR offer presentation; no browser layout claim'}));
