import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { createRequire } from 'node:module';
import { runInNewContext } from 'node:vm';
const require = createRequire(import.meta.url);
const ts = require('typescript');
const file = process.argv[2] || new URL('../lib/analytics.ts', import.meta.url);
const source = readFileSync(file, 'utf8');
const compilation = ts.transpileModule(source, {
  fileName: 'analytics.ts', reportDiagnostics: true,
  compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2022 },
});
assert.deepEqual(compilation.diagnostics, [], 'TypeScript syntactic diagnostics');
const SID = 'qa_no_real_user_session_123456';
function fixture({ blockedStorage=false, ssr=false, apiBase='https://api.dufynd.test/api', origin='https://dufynd.test', qa=false }={}) {
  const touched = { reads: 0, writes: 0, acquisition: 0, network: 0 };
  const values = new Map();
  const api = { base: apiBase, session: SID };
  const scope = {
    exports:{}, URL, URLSearchParams, Promise, setTimeout, clearTimeout,
    document: { referrer: '' },
    require(name) {
      if (name === './api') return { api, initializeAnalyticsSession:()=>{throw Error('No session initialization allowed');} };
      if (name === './acquisitionEntry') return {
        resolveAcquisitionEntry:()=>{touched.acquisition++; return {source:'instagram',campaign_id:'qa_cmp',content_id:'qa_content'};},
      };
      throw Error(`Unexpected module ${name}`);
    },
    fetch:()=>{ touched.network++; throw Error('No network allowed'); },
  };
  if(!ssr) scope.window={ location:{origin, search:qa?'?qa=1':'', hostname:new URL(origin).hostname}, sessionStorage:{
    getItem(k){touched.reads++;if(blockedStorage)throw Error('blocked');return values.get(k)||null;},
    setItem(k,v){touched.writes++;if(blockedStorage)throw Error('blocked');values.set(k,v);},
  }};
  runInNewContext(compilation.outputText,scope,{timeout:1000});
  return { append:scope.exports.appendAcquisitionAttribution, touched, api };
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
 '/api/session','/api/chat','/api/analytics/events','/api/clickout/','/api/clickout/a/b',
 'https://other.test/?src=their_source&cmp=their_campaign&sid=their_value#ref',
];
let cases=0;
for(const qa of [false,true]) for(const url of blocked) {
  const f=fixture({qa});
  assert.equal(f.append(url),url,`Reject enrichment, preserve original target: ${url}`);
  assert.deepEqual(f.touched,{reads:0,writes:0,acquisition:0,network:0},'Rejected destination must be side-effect free');
  cases++;
}
const allowed=[
 '/duft?q=Libre#angebote','/marken','/vergleich?left=SC-XERJOFF-NAXOS-100',
 'https://dufynd.test/duft/rabanne-1-million',
 '//dufynd.test/duft',
 '/api/clickout/perfumetrader-rabanne-1-million-edt-100',
 'https://api.dufynd.test/api/clickout/perfumetrader-rabanne-1-million-edt-100',
 'https://API.DUFYND.TEST:443/api/clickout/offer1',
];
for(const blockedStorage of [false,true]) for(const qa of [false,true]) for(const url of allowed) {
  const f=fixture({blockedStorage,qa});const actual=new URL(f.append(url));const original=new URL(url,'https://dufynd.test');
  assert.equal(actual.origin,original.origin); assert.equal(actual.pathname,original.pathname);assert.equal(actual.hash,original.hash);
  for(const [k,v] of original.searchParams) assert.equal(actual.searchParams.get(k),v);
  for(const [k,v] of [['src','instagram'],['cmp','qa_cmp'],['content','qa_content'],['sid',SID]]) assert.equal(actual.searchParams.get(k),v);
  assert.equal(actual.searchParams.get('qa'),qa?'1':null);assert.equal(f.touched.network,0);
  assert.equal(f.api.session,SID,'Do not mutate the advisor/session transport');
  cases++;
}
for(const url of ['/duft','https://other.test/source']) {
 const f=fixture({ssr:true});assert.equal(f.append(url),url);assert.equal(f.touched.network,0);cases++;
}
for(const apiBase of ['https://api.dufynd.test/api/','https://api.dufynd.test/service/api']) {
 const f=fixture({apiBase});const prefix=apiBase.replace(/\/$/,'');
 assert.equal(new URL(f.append(prefix+'/clickout/offer1')).searchParams.get('sid'),SID);cases++;
}
{
 const f=fixture({origin:'http://localhost:3000',apiBase:'http://localhost:8000/api'});
 assert.equal(new URL(f.append('http://localhost:8000/api/clickout/offer1')).searchParams.get('sid'),SID);
 assert.equal(f.append('http://127.0.0.1:8000/api/clickout/offer1'),'http://127.0.0.1:8000/api/clickout/offer1');cases+=2;
}
{
 const f=fixture({apiBase:'%%%invalid'});
 assert.equal(f.append('https://other.test/api/clickout/offer1'),'https://other.test/api/clickout/offer1');cases++;
}

// The existing merchant-discovery route is distinct from product-offer clickouts.
// Cover both route shapes without permitting arbitrary configured-API endpoints.
for (const apiBase of ['https://api.dufynd.test/api', 'https://api.dufynd.test/service/api/']) {
  const root=apiBase.replace(/\/$/,'');
  for (const blockedStorage of [false,true]) for (const qa of [false,true]) {
    for (const session of [SID,null]) for (const url of [
      `${root}/merchant-partners/perfumetrader/clickout?existing=1#merchant`,
      'https://dufynd.test/api/merchant-partners/perfumetrader/clickout',
    ]) {
      const f=fixture({apiBase,blockedStorage,qa});f.api.session=session;
      const original=new URL(url),result=new URL(f.append(url));
      assert.equal(result.origin,original.origin);assert.equal(result.pathname,original.pathname);
      assert.equal(result.hash,original.hash);
      for(const [key,value] of original.searchParams) assert.equal(result.searchParams.get(key),value);
      for(const [key,value] of [['src','instagram'],['cmp','qa_cmp'],['content','qa_content'],['sid',session]]) {
        assert.equal(result.searchParams.get(key),value,'Configured merchant-partner redirect preserves available attribution');
      }
      assert.equal(result.searchParams.get('qa'),qa?'1':null);
      assert.equal(f.api.session,session);assert.equal(f.touched.network,0);cases++;
    }
  }
  for(const path of [
    '/merchant-partners', '/merchant-partners/', '/merchant-partners/perfumetrader',
    '/merchant-partners//clickout','/merchant-partners/a/b/clickout',
    '/merchant-partners/perfumetrader/clickout/extra','/merchant-partners/perfumetrader/clickout/',
    '/merchant-partners/%2f/clickout','/merchant-partners/%5c/clickout',
    '/merchant-partners/%00/clickout','/merchant-partners/%20/clickout',
    '/merchant-partners/%zz/clickout', '/merchant-partners/%2E%2E/clickout',
  ]) for(const origin of [root,'https://dufynd.test/api']) {
    const f=fixture({apiBase,qa:true}),url=origin+path;
    assert.equal(f.append(url),url,'Reject malformed/other merchant API endpoints');
    assert.deepEqual(f.touched,{reads:0,writes:0,acquisition:0,network:0});cases++;
  }
}
for (const url of [
  'https://other.test/api/merchant-partners/perfumetrader/clickout',
  'https://api.dufynd.test.evil.test/api/merchant-partners/perfumetrader/clickout',
  'https://api.dufynd.test:444/api/merchant-partners/perfumetrader/clickout',
  'http://api.dufynd.test/api/merchant-partners/perfumetrader/clickout',
]) {
  const f=fixture({qa:true});assert.equal(f.append(url),url);
  assert.deepEqual(f.touched,{reads:0,writes:0,acquisition:0,network:0});cases++;
}

console.log(JSON.stringify({status:'PASS',cases,networkRequests:0,productionMutations:0,scope:'Compiled actual analytics.ts with in-memory browser/API fixtures; not full browser E2E'},null,2));
