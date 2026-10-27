import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { mkdir, writeFile } from 'node:fs/promises';
import path from 'node:path';

const OPTIONAL=['dufynd_analytics_session_v1','dufynd_acquisition_attribution_v1','dufynd_internal_qa_v1'];
const FIELDS=['sid','src','cmp','content','measurement'];
// Consent QA never sends merchant-media requests to third parties. The
// exact, rights-scoped original-photo registry is the ONLY recognized exception
// to the unexpected-request diagnostic; recognized requests are still ABORTED.
const APPROVED_EXTERNAL_ORIGINAL_URLS=new Set(
  JSON.parse(readFileSync(new URL('../lib/generated/original-photos.json',import.meta.url),'utf8'))
    .filter(photo=>typeof photo?.url==='string'&&photo.url.startsWith('https://')&&
      typeof photo.rights_basis_id==='string'&&photo.rights_basis_id.length>0)
    .map(photo=>photo.url),
);
const PID='SC-RABANNE-1-MILLION-EDT-100';
const OFFER='qa-consent-rabanne';
const entry='/duft/rabanne-1-million?qa=1&measurement=granted-v1&sid=qa_untrusted_shared_123456&src=instagram&cmp=qa_consent26&content=qa_product';
const merchant=page=>page.locator(`[data-merchant-offers] a[href*="/api/clickout/${OFFER}"]`).first();

async function settle(page){
  await page.evaluate(()=>new Promise(resolve=>requestAnimationFrame(()=>requestAnimationFrame(resolve))));
}
async function settledRequestCount(page,stats){
  let last=-1,stable=0;
  for(let n=0;n<40;n++){
    await page.waitForTimeout(50);
    const current=stats.requests.length;
    if(current===last) stable+=1; else { last=current; stable=0; }
    if(current>0&&stable>=4) return current;
  }
  return stats.requests.length;
}
async function expectChoice(page,value){
  await page.waitForFunction(value=>document.querySelector('[data-measurement-choice]')?.getAttribute('data-measurement-choice')===value,value);
}
async function expectNoOptional(page){
  const keys=await page.evaluate(keys=>keys.filter(key=>sessionStorage.getItem(key)!==null),OPTIONAL);
  assert.deepEqual(keys,[],'No optional session or acquisition storage without consent');
  const link=merchant(page);await link.focus();
  const url=new URL(await link.getAttribute('href'));
  for(const key of FIELDS)assert.equal(url.searchParams.has(key),false,`Denied merchant href must omit ${key}`);
}
async function isolatedContext(browser,baseUrl,width,{hold=false,blocked=false}={}){
  const context=await browser.newContext({viewport:{width,height:844},serviceWorkers:'block'});
  const stats={events:[],requests:[],unexpected:[],clickouts:0,aborted:0,held:[],session:0};
  if(blocked)await context.addInitScript(()=>{
    Object.defineProperty(window,'localStorage',{get(){throw new DOMException('QA storage unavailable','SecurityError');}});
  });
  const origin=new URL(baseUrl).origin;
  // Default deny for every remote request. No merchant redirect is followed.
  await context.route('**/*',async route=>{
    const request=route.request(),url=new URL(request.url());
    if(url.pathname==='/api/session'){
      stats.session++;
      return route.fulfill({json:{session_id:`qa-functional-transport-${stats.session}-123456`}});
    }
    if(url.pathname==='/api/analytics/events'){
      stats.requests.push(request.url());
      assert.equal(url.searchParams.get('measurement'),'granted-v1');
      const event=request.postDataJSON();
      if(hold){stats.held.push(route);return;}
      stats.events.push(event);
      return route.fulfill({json:{ok:true}});
    }
    if(url.pathname===`/api/merchant-offers/${PID}`){
      return route.fulfill({json:{product_id:PID,best_offer_id:OFFER,affiliate_disclosure:'Isolated QA fixture',offers:[{
        offer_id:OFFER,product_id:PID,merchant_id:'perfumetrader',merchant_name:'Perfumetrader',
        price:99,currency:'EUR',shipping_cost:0,total_price:99,in_stock:true,affiliate_link:true,
        clickout_path:`/api/clickout/${OFFER}`,last_updated_at:new Date().toISOString(),
      }]}});
    }
    if(url.pathname.includes('/clickout/')||/\/merchant-partners\/[^/]+\/clickout$/.test(url.pathname)){
      stats.clickouts++;return route.abort('blockedbyclient');
    }
    if(url.origin===origin&&!url.pathname.startsWith('/api/'))return route.continue();
    if(APPROVED_EXTERNAL_ORIGINAL_URLS.has(request.url())){
      // An approved original image is expected on this product page, but
      // loading its bytes would leak the QA visitor to the merchant host.
      stats.approvedMediaBlocked=(stats.approvedMediaBlocked||0)+1;
      return route.abort('blockedbyclient');
    }
    // These discovery endpoints are fixture-only too, never forwarded.
    if(url.pathname==='/api/products')return route.fulfill({json:{products:[]}});
    if(url.pathname==='/api/merchant-partners')return route.fulfill({json:{partners:[],affiliate_disclosure:'QA'}});
    stats.unexpected.push(`${url.origin}${url.pathname}`);return route.abort('blockedbyclient');
  });
  context.on('requestfailed',request=>{if(new URL(request.url()).pathname==='/api/analytics/events')stats.aborted++;});
  return {context,stats};
}
async function open(page,baseUrl){
  await page.goto(baseUrl+entry,{waitUntil:'domcontentloaded'});
  await page.locator('[data-measurement-panel]').waitFor({state:'visible'});
  await merchant(page).waitFor({state:'visible'});await settle(page);
}
async function approve(page){
  await page.getByRole('button',{name:'Analyse erlauben',exact:true}).click();
  await expectChoice(page,'granted');
}
async function screen(page,out,name){
  await page.screenshot({path:path.join(out,name+'.png'),fullPage:false});
}
export async function verifyMeasurementBrowser(browser,baseUrl,outputDir){
  const root=new URL(baseUrl);
  assert.ok(['localhost','127.0.0.1','[::1]'].includes(root.hostname),'Consent QA only runs against an isolated loopback build');
  const out=path.join(outputDir,'consent26');await mkdir(out,{recursive:true});
  const results=[];
  for(const width of [320,390,768,1440]){
    const {context,stats}=await isolatedContext(browser,baseUrl,width);
    try{
      const page=await context.newPage();await open(page,baseUrl);
      await expectChoice(page,'unknown');
      assert.equal(stats.requests.length,0,'qa=1 or a copied measurement parameter cannot grant consent');
      await expectNoOptional(page);
      const buttons=page.locator('[data-measurement-panel] button');
      const geometry=await buttons.evaluateAll(nodes=>nodes.map(node=>{
        const b=node.getBoundingClientRect(),s=getComputedStyle(node);return {x:b.x,width:b.width,height:b.height,background:s.backgroundColor,color:s.color};
      }));
      assert.equal(geometry.length,2);assert.equal(geometry[0].background,geometry[1].background);
      assert.equal(geometry[0].color,geometry[1].color);
      for(const b of geometry)assert.ok(b.x>=0&&b.x+b.width<=width&&b.height>=40,'Both real choice controls fit and are usable');
      assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth+1),false);
      await screen(page,out,`unknown-${width}`);
      await page.getByRole('button',{name:'Nur notwendige Funktionen',exact:true}).click();
      await expectChoice(page,'denied');await expectNoOptional(page);
      assert.equal(stats.requests.length,0);
      await page.getByRole('button',{name:'Datenschutz-Einstellungen',exact:true}).click();await approve(page);
      await page.waitForFunction(()=>sessionStorage.getItem('dufynd_analytics_session_v1')!==null);
      await merchant(page).focus();
      const allowed=new URL(await merchant(page).getAttribute('href'));
      const sid=allowed.searchParams.get('sid');assert.match(sid||'',/^[a-f0-9-]{36}$/);
      assert.equal(allowed.searchParams.get('measurement'),'granted-v1');
      assert.notEqual(sid,'qa_untrusted_shared_123456');
      await page.evaluate(()=>localStorage.setItem('qa_non_measurement_keep','preserve'));
      await page.getByRole('button',{name:'Analyse widerrufen',exact:true}).click();
      await expectChoice(page,'denied');await expectNoOptional(page);await settle(page);
      assert.equal(await page.evaluate(()=>localStorage.getItem('qa_non_measurement_keep')),'preserve');
      const count=stats.requests.length;
      await page.reload({waitUntil:'domcontentloaded'});await merchant(page).waitFor();await expectChoice(page,'denied');await settle(page);
      assert.equal(stats.requests.length,count,'Reload after withdrawal must not send telemetry');
      await expectNoOptional(page);await screen(page,out,`denied-${width}`);
      assert.equal(stats.clickouts,0);assert.deepEqual(stats.unexpected,[]);
      results.push({width,defaultOff:true,explicitChoice:true,withdrawal:true,reloadDenied:true,merchantNavigation:'href verified, not clicked'});
    }finally{await context.close();}
  }
  {
    const {context,stats}=await isolatedContext(browser,baseUrl,390);
    try{
      const first=await context.newPage();await open(first,baseUrl);await approve(first);
      const second=await context.newPage();await second.goto(baseUrl+entry,{waitUntil:'domcontentloaded'});
      await expectChoice(second,'granted');await merchant(second).waitFor();
      await first.getByRole('button',{name:'Analyse widerrufen',exact:true}).click();
      await expectChoice(first,'denied');await expectChoice(second,'denied');await expectNoOptional(second);
      assert.equal(stats.clickouts,0);assert.deepEqual(stats.unexpected,[]);
      results.push({case:'cross-tab-withdrawal',passed:true});
    }finally{await context.close();}
  }
  {
    const {context,stats}=await isolatedContext(browser,baseUrl,390,{hold:true});
    try{
      const page=await context.newPage();await open(page,baseUrl);await approve(page);
      for(let n=0;n<100&&stats.held.length===0;n++)await page.waitForTimeout(25);
      assert.ok(stats.held.length>0,'A genuine analytics fetch is held before testing withdrawal');
      await page.getByRole('button',{name:'Analyse widerrufen',exact:true}).click();
      await expectChoice(page,'denied');await expectNoOptional(page);
      for(let n=0;n<100&&stats.aborted===0;n++)await page.waitForTimeout(25);
      assert.ok(stats.aborted>0,'Withdrawal aborts an actual browser analytics fetch');
      const count=stats.requests.length;
      for(const route of stats.held){try{await route.fulfill({json:{ok:false}});}catch{/* Already aborted. */}}
      await settle(page);await page.waitForTimeout(100);
      assert.equal(stats.requests.length,count,'A late failure must not initiate a consentless retry');
      assert.equal(stats.clickouts,0);assert.deepEqual(stats.unexpected,[]);
      results.push({case:'in-flight-withdrawal',passed:true});
    }finally{await context.close();}
  }
  {
    const {context,stats}=await isolatedContext(browser,baseUrl,390,{blocked:true});
    try{
      const page=await context.newPage();await open(page,baseUrl);assert.equal(stats.requests.length,0);
      await approve(page);await expectChoice(page,'granted');
      for(let n=0;n<100&&stats.requests.length===0;n++)await page.waitForTimeout(25);
      assert.ok(stats.requests.length>0,'Explicit in-memory permission enables an actual analytics request');
      const count=await settledRequestCount(page,stats);
      await page.reload({waitUntil:'domcontentloaded'});await merchant(page).waitFor();await expectChoice(page,'unknown');await settle(page);
      assert.equal(stats.requests.length,count,'Unpersisted consent does not survive reload');
      await expectNoOptional(page);assert.equal(stats.clickouts,0);assert.deepEqual(stats.unexpected,[]);
      results.push({case:'blocked-preference-storage',passed:true});
    }finally{await context.close();}
  }
  await writeFile(path.join(out,'report.json'),JSON.stringify({status:'PASS',cases:results.length,results,realMerchantClicks:0,externalRequests:0},null,2));
  return results;
}
