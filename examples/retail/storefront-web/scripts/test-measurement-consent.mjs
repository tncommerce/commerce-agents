import assert from 'node:assert/strict';
import fs from 'node:fs';
import vm from 'node:vm';
import { webcrypto } from 'node:crypto';
import { createRequire } from 'node:module';
const require=createRequire(import.meta.url);
const ts=require(process.env.TYPESCRIPT_PATH || 'typescript');
const ROOT=new URL('../',import.meta.url);
const PKEY='dufynd_measurement_preference_v1', AKEY='dufynd_analytics_session_v1', CKEY='dufynd_acquisition_attribution_v1';
const compile=file=>{
 const r=ts.transpileModule(fs.readFileSync(new URL(file,ROOT),'utf8'),{fileName:file,reportDiagnostics:true,compilerOptions:{target:ts.ScriptTarget.ES2022,module:ts.ModuleKind.CommonJS,jsx:ts.JsxEmit.ReactJSX}});
 assert.deepEqual(r.diagnostics,[],`Syntax diagnostics for ${file}`);return r.outputText;
};
const compiled={consent:compile('lib/measurementConsent.ts'),analytics:compile('lib/analytics.ts')};
compile('components/MeasurementPreferences.tsx');compile('app/layout.tsx');
let cases=0;
const pass=name=>{cases++; console.log(`PASS ${name}`);};
const deferred=()=>{let resolve;const promise=new Promise(r=>resolve=r);return {promise,resolve};};
async function drain(){for(let i=0;i<12;i++) await Promise.resolve();}
function fixture({local=new Map(),session=new Map(),blockedLocal=false,blockedSession=false,href='https://dufynd.test/duft/rabanne-1-million?src=instagram&cmp=launch',referrer='',initialize,post,ssr=false}={}){
 let now=1780000000000;const log={initializations:0,posts:[],optionalReads:0,optionalWrites:0,removals:[],acquisition:0};
 const events=new Map(),documentEvents=new Map(),timers=new Map();let ti=0;
 const anchors=[{href:'https://dufynd.test/duft?sid=old_identifier_12345&src=instagram&q=rose#duft'},{href:'https://api.dufynd.test/api/clickout/offer?sid=old_identifier_12345&measurement=granted-v1'},{href:'https://external.test/?sid=their_id'}];
 let loc=new URL(href);
 const storage=(store,blocked,optional)=>({
  getItem(k){if(optional)log.optionalReads++;if(blocked)throw Error('blocked');return store.get(k)||null;},
  setItem(k,v){if(optional)log.optionalWrites++;if(blocked)throw Error('blocked');store.set(k,v);},
  removeItem(k){log.removals.push(k);if(blocked)throw Error('blocked');store.delete(k);},
 });
 const api={base:'https://api.dufynd.test/api',session:null,headers:()=>({'X-Session-Id':api.session})};
 const win={get location(){return loc;},localStorage:storage(local,blockedLocal,false),sessionStorage:storage(session,blockedSession,true),
   addEventListener:(type,fn)=>{events.set(type,[...(events.get(type)||[]),fn]);},
   history:{state:{},replaceState(_s,_t,url){loc=new URL(url,loc);}},};
 const doc={referrer,visibilityState:'visible',querySelectorAll:()=>anchors,
   addEventListener:(type,fn)=>{documentEvents.set(type,[...(documentEvents.get(type)||[]),fn]);}};
 class Clock extends Date {static now(){return now;}}
 const scope=vm.createContext({URL,URLSearchParams,Promise,AbortController,crypto:webcrypto,Date:Clock,
   ...(ssr?{}:{window:win,document:doc}),Element:class {},
   setTimeout:(fn,ms)=>{timers.set(++ti,{fn,ms});return ti;},clearTimeout:id=>timers.delete(id),
   fetch:(url,init)=>{const item={url,init,body:JSON.parse(init.body)};log.posts.push(item);return post?post(item):Promise.resolve({ok:true});},
 });
 const cache={};
 function load(key){
  if(cache[key])return cache[key].exports;
  const module={exports:{}};cache[key]=module;
  const localRequire=name=>{
   if(name==='./measurementConsent')return load('consent');
   if(name==='./api')return {api,initializeAnalyticsSession:()=>{log.initializations++;return initialize?initialize(log.initializations):Promise.resolve('transport_session_123456');}};
   if(name==='./acquisitionEntry')return {resolveAcquisitionEntry:(search,_ref,_org,prior)=>{log.acquisition++; const q=new URLSearchParams(search);return q.get('src')?{source:q.get('src'),campaign_id:q.get('cmp')||undefined,content_id:q.get('content')||undefined}:prior||{source:'direct'};}};
   throw Error(name);
  };
  const fn=vm.runInContext(`(function(require,module,exports){${compiled[key]}\n})`,scope);
  fn(localRequire,module,module.exports);return module.exports;
 }
 const analytics=load('analytics'),consent=load('consent');
 return {analytics,consent,api,log,session,local,anchors,win,timers,
  advance:ms=>now+=ms,
  dispatch:(type,e={})=>{for(const fn of events.get(type)||[])fn(e);},
  preference:choice=>local.set(PKEY,JSON.stringify({version:1,choice,savedAt:now})),
 };
}
{
 const f=fixture();f.api.session='functional_advisor_1234';f.session.set('dufynd_wishlist','["SC-KEEP"]');
 f.analytics.initializeMeasurementPrivacy(); await f.analytics.trackAnalyticsEvent('page_view');await f.analytics.trackCatalogSearch('Libre',1);
 assert.equal(f.consent.measurementChoice(),'unknown');assert.equal(f.log.initializations,0);assert.equal(f.log.posts.length,0);assert.equal(f.log.acquisition,0);assert.equal(f.log.optionalReads,0);
 assert.equal(f.api.session,'functional_advisor_1234');assert.equal(f.session.get('dufynd_wishlist'),'["SC-KEEP"]');
 const u=new URL(f.analytics.appendAcquisitionAttribution('/duft?q=rose&src=x&sid=old_id'));assert.equal(u.searchParams.get('q'),'rose');assert.equal(u.searchParams.get('sid'),null);assert.equal(u.searchParams.get('src'),null);
 assert.equal(new URL(f.anchors[1].href).searchParams.get('measurement'),null);assert.equal(f.anchors[2].href,'https://external.test/?sid=their_id');
 pass('default off, no optional reads/initialization/telemetry; functional data retained');
}
{
 const f=fixture({href:'https://dufynd.test/?qa=1&measurement=granted-v1&sid=old_identifier_12345'});
 await f.analytics.trackAnalyticsEvent('page_view');assert.equal(f.log.posts.length,0);assert.equal(f.consent.measurementChoice(),'unknown');
 pass('neither QA marker nor URL transport signal grants consent');
}
{
 const f=fixture();f.consent.setMeasurementChoice('granted');await f.analytics.trackAnalyticsEvent('page_view');
 assert.equal(f.log.posts.length,1);assert.match(f.log.posts[0].url,/measurement=granted-v1/);
 const id=f.log.posts[0].body.analytics_session_id;assert.match(id,/^[a-f0-9-]{36}$/);assert.notEqual(id,f.api.session);
 const url=new URL(f.analytics.appendAcquisitionAttribution('https://api.dufynd.test/api/merchant-partners/perfumetrader/clickout'));
 assert.equal(url.searchParams.get('sid'),id);assert.equal(url.searchParams.get('measurement'),'granted-v1');
 f.consent.setMeasurementChoice('denied');assert.equal(f.session.has(AKEY),false);assert.equal(f.session.has(CKEY),false);assert.equal(f.api.session,null);
 assert.equal(new URL(f.analytics.appendAcquisitionAttribution(url.toString())).searchParams.get('measurement'),null);
 f.advance(1);f.consent.setMeasurementChoice('granted');await f.analytics.trackAnalyticsEvent('product_open');assert.notEqual(f.log.posts[1].body.analytics_session_id,id);
 pass('grant permits actual telemetry; withdrawal clears optional identity; regrant rotates identity');
}
{
 const old=deferred(),fresh=deferred();const f=fixture({initialize:i=>i===1?old.promise:fresh.promise});
 f.consent.setMeasurementChoice('granted');const first=f.analytics.trackAnalyticsEvent('page_view');await drain();
 const queued=f.analytics.trackAnalyticsEvent('product_open');
 f.consent.setMeasurementChoice('denied');f.advance(1);f.consent.setMeasurementChoice('granted');
 const newest=f.analytics.trackAnalyticsEvent('comparison_start');await drain();assert.equal(f.log.initializations,2);
 old.resolve('late_transport_123456');await first;await queued;await drain();
 const shared=f.analytics.ensureAnalyticsSession();assert.equal(f.log.initializations,2);assert.equal(f.api.session,null);
 fresh.resolve('fresh_transport_123456');await newest;await shared;
 assert.equal(f.log.posts.length,1);assert.equal(f.log.posts[0].body.event,'comparison_start');assert.equal(f.api.session,'fresh_transport_123456');
 pass('late initialization and old queue cannot restore revoked generation or clobber new initializer');
}
{
 let stopped=false;const f=fixture({post:item=>new Promise((_r,reject)=>item.init.signal.addEventListener('abort',()=>{stopped=true;reject(Error('aborted'));}))});
 f.consent.setMeasurementChoice('granted');const first=f.analytics.trackAnalyticsEvent('page_view');await drain();
 const queued=f.analytics.trackAnalyticsEvent('product_open');f.consent.setMeasurementChoice('denied');await Promise.all([first,queued]);
 assert.equal(stopped,true);assert.equal(f.log.posts.length,1);assert.equal(f.log.initializations,1);assert.equal(f.timers.size,0);
 pass('withdrawal aborts pending analytics fetch, prevents retry and drops queued events');
}
{
 const f=fixture();f.consent.setMeasurementChoice('granted');f.api.session='advisor_active_123456';
 await f.analytics.trackAnalyticsEvent('consultation_start');f.consent.setMeasurementChoice('denied');
 assert.equal(f.api.session,'advisor_active_123456');pass('functional advisor session survives optional-measurement withdrawal');
}
for(const options of [{blockedLocal:true},{blockedSession:true},{blockedLocal:true,blockedSession:true}]){
 const f=fixture(options);f.consent.setMeasurementChoice('granted');await f.analytics.trackAnalyticsEvent('page_view');assert.equal(f.log.posts.length,1);
 f.consent.setMeasurementChoice('denied');await f.analytics.trackAnalyticsEvent('product_open');assert.equal(f.log.posts.length,1);
 const next=fixture({...options,local:f.local,session:f.session});assert.notEqual(next.consent.measurementChoice(),'granted');
 pass(`blocked storage never forces analytics or shopping failure ${JSON.stringify(options)}`);
}
{
 const local=new Map();const a=fixture({local}),b=fixture({local});a.consent.setMeasurementChoice('granted');
 assert.equal(b.consent.measurementChoice(),'granted');await b.analytics.trackAnalyticsEvent('page_view');
 a.consent.setMeasurementChoice('denied');b.dispatch('storage',{key:PKEY});assert.equal(b.consent.measurementAllowed(),false);
 assert.equal(b.session.has(AKEY),false);await b.analytics.trackAnalyticsEvent('product_open');assert.equal(b.log.posts.length,1);
 pass('cross-tab withdrawal clears other tab identity and stops its future telemetry');
}
{
 const f=fixture();f.consent.setMeasurementChoice('granted');await f.analytics.trackAnalyticsEvent('page_view');f.advance(180*24*60*60*1000+1);
 await f.analytics.trackAnalyticsEvent('product_open');assert.equal(f.log.posts.length,1);assert.equal(f.consent.measurementChoice(),'unknown');
 pass('expired consent preference cannot keep analytics enabled');
}
for(const raw of ['broken','{"version":0,"choice":"granted","savedAt":1780000000000}','{"version":1,"choice":"granted","savedAt":9999999999999}']){
 const local=new Map([[PKEY,raw]]);const f=fixture({local});await f.analytics.trackAnalyticsEvent('page_view');assert.equal(f.log.posts.length,0);pass('invalid preference fails closed '+raw);
}
{
 const f=fixture({ssr:true});f.consent.setMeasurementChoice('granted');await f.analytics.trackAnalyticsEvent('page_view');
 assert.equal(f.consent.measurementChoice(),'unknown');assert.equal(f.log.posts.length,0);assert.equal(f.analytics.appendAcquisitionAttribution('/duft'),'/duft');
 pass('SSR never establishes shared measurement permission');
}
{
 const f=fixture({href:'https://dufynd.test/duft?q=rose&cmp=x&sid=old_identifier_12345#offers'});f.analytics.initializeMeasurementPrivacy();
 f.consent.setMeasurementChoice('denied');assert.equal(f.win.location.search,'?q=rose');assert.equal(f.win.location.hash,'#offers');
 pass('withdrawal cleans optional URL fields while preserving functional query and fragment');
}
{
 const f=fixture();f.consent.setMeasurementChoice('granted');f.local.delete(PKEY);f.dispatch('pageshow');
 assert.equal(f.consent.measurementAllowed(),false);pass('bfcache/pageshow rechecks current persisted choice');
}
{
 const f=fixture();const before={...f.log};assert.equal(f.analytics.appendAcquisitionAttribution('https://evil.test/?src=theirs'),'https://evil.test/?src=theirs');
 assert.equal(f.log.optionalReads,before.optionalReads);assert.equal(f.log.optionalWrites,before.optionalWrites);assert.equal(f.log.acquisition,before.acquisition);
 pass('untrusted destinations remain untouched with no optional-data side effects');
}

// Re-exercise the prior strict boundary together with the new permission state.
let boundaryCases=0;
const rejected=[
 'https://other.test/source','https://other.test/api/clickout/offer1',
 'https://api.dufynd.test.evil.test/api/clickout/offer1','https://dufynd.test.evil.test/duft',
 '//other.test/api/clickout/offer1','https://user:password@dufynd.test/duft',
 'https://api.dufynd.test@other.test/api/clickout/offer1',
 'https://api.dufynd.test:444/api/clickout/offer1','http://api.dufynd.test/api/clickout/offer1',
 'mailto:contact@example.test','tel:+49123456789','javascript:void(0)',
 'data:text/plain,hello','ftp://files.test/item','https://[invalid',
 'https://api.dufynd.test/api/session','https://api.dufynd.test/api/chat',
 'https://api.dufynd.test/api/analytics/events','https://api.dufynd.test/api/clickout/',
 'https://api.dufynd.test/api/clickout/one/two','https://api.dufynd.test/api/clickout/a%2Fb',
 'https://api.dufynd.test/api/clickout/a%5Cb','https://api.dufynd.test/api/clickout/%zz',
 'https://api.dufynd.test/api/clickout/%20','https://api.dufynd.test/api/clickout/%00',
 'https://api.dufynd.test/api/clickout/%2E%2E/session','https://api.dufynd.test/clickout/offer1',
 '/api/session','/api/chat','/api/analytics/events','/api/clickout/','/api/clickout/a/b',
 'https://other.test/?src=theirs&cmp=theirs&sid=theirs#ref',
];
for(const prefix of ['https://api.dufynd.test/api','https://dufynd.test/api']) {
 for(const part of ['','/','/perfumetrader','//clickout','/a/b/clickout',
  '/perfumetrader/clickout/extra','/perfumetrader/clickout/','/%2f/clickout',
  '/%5c/clickout','/%00/clickout','/%20/clickout','/%zz/clickout','/%2E%2E/clickout']) rejected.push(prefix+'/merchant-partners'+part);
}
for(const choice of ['unknown','denied','granted']) for(const url of rejected){
 const f=fixture();if(choice!=='unknown')f.consent.setMeasurementChoice(choice);
 const before=[f.log.optionalReads,f.log.optionalWrites,f.log.acquisition];
 assert.equal(f.analytics.appendAcquisitionAttribution(url),url,url);
 assert.deepEqual([f.log.optionalReads,f.log.optionalWrites,f.log.acquisition],before);
 assert.equal(f.log.posts.length,0);boundaryCases++;
}
for(const choice of ['unknown','denied','granted']) for(const blockedSession of [false,true]){
 for(const url of ['/duft?q=rose#angebote','/marken',
  '/api/clickout/offer1','https://api.dufynd.test/api/clickout/offer1',
  'https://api.dufynd.test/api/merchant-partners/perfumetrader/clickout',
  '/api/merchant-partners/perfumetrader/clickout']){
  const f=fixture({blockedSession});if(choice!=='unknown')f.consent.setMeasurementChoice(choice);
  const next=new URL(f.analytics.appendAcquisitionAttribution(url)),original=new URL(url,'https://dufynd.test');
  assert.equal(next.pathname,original.pathname);assert.equal(next.origin,original.origin);assert.equal(next.hash,original.hash);
  assert.equal(Boolean(next.searchParams.get('sid')),choice==='granted');
  if(url.includes('/api/')) assert.equal(next.searchParams.get('measurement'),choice==='granted'?'granted-v1':null);
  assert.equal(f.log.posts.length,0);boundaryCases++;
 }
}
console.log(`PASS ${boundaryCases} combined consent/destination-boundary cases`);
console.log(JSON.stringify({status:'PASS',scenarioGroups:cases,boundaryCases,realNetworkRequests:0,scope:'Actual transpiled consent + analytics modules in synthetic DOM/storage/API fixtures; not full browser E2E'},null,2));
