// Offline tests of the actual TypeScript API boundary, not a copy of its logic.
// No dependencies beyond the storefront's existing TypeScript and Node runtime.
import assert from 'node:assert/strict';
import fs from 'node:fs';
import vm from 'node:vm';
import { createRequire } from 'node:module';
const require = createRequire(import.meta.url);
const ts = require('typescript');
const root = new URL('../lib/', import.meta.url);
const apiSource = fs.readFileSync(new URL('api.ts', root), 'utf8');
const baselinePath = process.env.DUFYND_BASELINE_API;
const selectedSource = baselinePath ? fs.readFileSync(baselinePath, 'utf8') : apiSource;
function compile(source) {
  const result = ts.transpileModule(source, {reportDiagnostics:true,compilerOptions:{
    module:ts.ModuleKind.CommonJS,target:ts.ScriptTarget.ES2022,esModuleInterop:true,
  }});
  assert.deepEqual(result.diagnostics, []);
  return result.outputText;
}
function evaluate(source, deps, extra={}) {
  const module={exports:{}};
  vm.runInNewContext(compile(source), {module,exports:module.exports,require(id){
    assert.ok(id in deps, `Unexpected dependency ${id}`);return deps[id];
  },...extra}, {timeout:1500});return module.exports;
}
const ID='SC-RABANNE-1-MILLION-EDT-100';
const OTHER='SC-YSL-LIBRE-EDP-90';
const OFFER='perfumetrader-rabanne-1-million-edt-100';
const payload=()=>({product_id:ID,best_offer_id:OFFER,affiliate_disclosure:'Werbung · Partnerlinks',offers:[{
  product_id:ID,offer_id:OFFER,merchant_id:'perfumetrader',merchant_name:'Perfumetrader',
  merchant_product_id:'16978322',price:71.9,currency:'EUR',shipping_cost:4.99,
  shipping_label:'Fixture shipping',total_price:76.89,in_stock:true,variant_label:'100 ml · EDT',
  clickout_path:`/api/clickout/${OFFER}`,affiliate_link:true,last_updated_at:'2026-10-20T02:16:00Z',
}]});
const cases=[];
const add=(name,mutate,accepted=false)=>{const p=payload();const replacement=mutate(p);cases.push({name,data:replacement===undefined?p:replacement,accepted});};
add('valid exact offer is unchanged',()=>{},true);
add('valid zero offers remain an empty success',p=>{p.offers=[];p.best_offer_id=null},true);
add('empty offers without best ID remain valid',p=>{p.offers=[];delete p.best_offer_id},true);
add('unknown shipping stays unknown',p=>{delete p.offers[0].shipping_cost;delete p.offers[0].total_price;delete p.offers[0].shipping_label},true);
add('free shipping is accepted',p=>{p.offers[0].shipping_cost=0;p.offers[0].total_price=71.9},true);
add('non-affiliate verified offer is accepted',p=>{p.offers[0].affiliate_link=false},true);
add('null optional labels remain valid',p=>{p.offers[0].merchant_product_id=null;p.offers[0].shipping_label=null;p.offers[0].variant_label=null},true);
add('null body',()=>null);
add('array body',()=>[]);
add('string body',()=>'<html>Error</html>');
add('wrong top-level product ID',p=>{p.product_id=OTHER});
add('wrong offer-row product ID',p=>{p.offers[0].product_id=OTHER});
add('missing offers array',p=>{delete p.offers});
add('null offers array',p=>{p.offers=null});
add('object offers array',p=>{p.offers={}});
add('null offer row',p=>{p.offers=[null]});
add('unknown best offer',p=>{p.best_offer_id='different-offer'});
add('missing best offer with non-empty offers',p=>{delete p.best_offer_id});
add('empty offers cannot retain a best offer',p=>{p.offers=[]});
add('duplicate offer IDs',p=>{p.offers.push({...p.offers[0]})});
add('external clickout destination',p=>{p.offers[0].clickout_path='https://example.invalid/other'});
add('mismatched clickout offer',p=>{p.offers[0].clickout_path='/api/clickout/another-offer'});
add('query parameter injection',p=>{p.offers[0].clickout_path+='?redirect=other'});
add('path traversal in offer ID',p=>{p.offers[0].offer_id='../session';p.offers[0].clickout_path='/api/clickout/../session';p.best_offer_id='../session'});
add('empty merchant name',p=>{p.offers[0].merchant_name=' '});
add('object merchant label',p=>{p.offers[0].merchant_name={text:'Perfumetrader'}});
add('missing merchant ID',p=>{delete p.offers[0].merchant_id});
add('string price',p=>{p.offers[0].price='71.90'});
add('negative price',p=>{p.offers[0].price=-1});
add('zero price',p=>{p.offers[0].price=0});
add('NaN price',p=>{p.offers[0].price=NaN});
add('infinite price',p=>{p.offers[0].price=Infinity});
add('negative shipping',p=>{p.offers[0].shipping_cost=-1});
add('string shipping',p=>{p.offers[0].shipping_cost='4.99'});
add('invalid total price',p=>{p.offers[0].total_price=Infinity});
add('unavailable offer row',p=>{p.offers[0].in_stock=false});
add('string stock flag',p=>{p.offers[0].in_stock='true'});
add('string affiliate flag',p=>{p.offers[0].affiliate_link='true'});
add('unsupported currency',p=>{p.offers[0].currency='USD'});
add('invalid date',p=>{p.offers[0].last_updated_at='not-a-date'});
add('missing date',p=>{delete p.offers[0].last_updated_at});
add('object shipping label',p=>{p.offers[0].shipping_label={cost:4.99}});
add('object variant label',p=>{p.offers[0].variant_label={size:100}});
add('object merchant product ID',p=>{p.offers[0].merchant_product_id={id:1}});
add('missing disclosure',p=>{delete p.affiliate_disclosure});
add('empty disclosure',p=>{p.affiliate_disclosure=' '});

async function runApi(data,{status=200,jsonError=false,transportError=false}={}) {
  let started=0,cleared=0,requests=[];
  class AgentApi {constructor(url,path){this.base=url+path}headers(){return {}}}
  const api=evaluate(selectedSource,{'web-shared':{AgentApi}},{
    process:{env:{NEXT_PUBLIC_API_URL:'https://dufynd-qa.invalid',NODE_ENV:'production'}},
    AbortController,
    setTimeout(){started++;return started},clearTimeout(){cleared++},
    async fetch(url,options){requests.push({url,options});if(transportError)throw new Error('offline fixture');return {
      ok:status>=200&&status<300,async json(){if(jsonError)throw new SyntaxError('malformed json');return data},
    }},
  });
  const output=await api.fetchMerchantOffers(ID);
  assert.equal(requests.length,1);assert.equal(started,1);assert.equal(cleared,1);
  assert.equal(requests[0].url,`https://dufynd-qa.invalid/api/merchant-offers/${ID}`);
  assert.equal(requests[0].options.signal instanceof AbortSignal,true);
  return output;
}
const results=[];
for(const c of cases){try{
  const before=structuredClone(c.data);
  const output=await runApi(c.data);
  assert.equal(output!==null,c.accepted);
  if(c.accepted)assert.equal(output,c.data,'Validated data must not be rewritten');
  assert.deepEqual(c.data,before,'Validator mutated API data');
  results.push({name:c.name,status:'PASS'});
}catch(e){results.push({name:c.name,status:'FAIL',detail:e.message})}}
for(const c of [{name:'HTTP 503 returns error, never offers',status:503},
{name:'HTTP 404 is error, not empty success',status:404},
{name:'invalid JSON is caught',jsonError:true},{name:'transport failure is caught',transportError:true}]){
try{assert.equal(await runApi(payload(),c),null);results.push({name:c.name,status:'PASS'})}
catch(e){results.push({name:c.name,status:'FAIL',detail:e.message})}}
const pass=results.every(r=>r.status==='PASS');
console.log(JSON.stringify({status:pass?'PASS':'FAIL',baseline:!!baselinePath,cases:results.length,results,
 realNetworkRequests:0,merchantClickouts:0,fixtureOnly:true},null,2));
if(!pass)process.exitCode=1;
