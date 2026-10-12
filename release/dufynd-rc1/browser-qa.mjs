import assert from 'node:assert/strict';
import path from 'node:path';
import {readFileSync,writeFileSync,mkdirSync} from 'node:fs';
import {pathToFileURL} from 'node:url';
import {chromium} from 'playwright';
const [baseUrl,candidate,output,observedFile]=process.argv.slice(2);
assert.ok(['127.0.0.1','localhost'].includes(new URL(baseUrl).hostname));
const origin=new URL(baseUrl).origin, product='SC-RABANNE-1-MILLION-EDT-100';
const observed=JSON.parse(readFileSync(observedFile));
assert.equal(observed.kind,'recorded_public_api_observation_not_current_quote');
assert.equal(observed.body.product_id,product);
const quote=observed.body.offers.find(o=>o.offer_id==='perfumetrader-rabanne-1-million-edt-100');
assert.ok(quote?.affiliate_link);assert.equal(quote.variant_label,'100 ml · Eau de Toilette');
const fixture={...quote,offer_id:'qa-rc1-fixture',price:90,shipping_cost:5,shipping_label:'5,00 € Versand (künstliche QA)',total_price:95,clickout_path:'/api/clickout/qa-rc1-fixture'};
mkdirSync(output,{recursive:true});
const browser=await chromium.launch({headless:true});
const checks=[],forbidden=[],events=[];
let activePage;
try {
 for(const width of [390,1440]) for(const source of ['instagram','youtube']) {
  const context=await browser.newContext({viewport:{width,height:900},serviceWorkers:'block',reducedMotion:'reduce'});
  let mode='observed', releaseLoading, offerRequests=0;
  const localEvents=[],session=`qa-rc1-session-${width}-${source}`;
  await context.route('**/*',async route=>{
   const u=new URL(route.request().url());
   if(u.pathname.startsWith('/api/clickout/')) {forbidden.push(u.pathname);return route.abort();}
   if(u.pathname==='/api/session') return route.fulfill({json:{session_id:session}});
   if(u.pathname==='/api/analytics/events') {localEvents.push(route.request().postDataJSON());return route.fulfill({json:{ok:true}});}
   if(u.pathname===`/api/merchant-offers/${product}`) {
    offerRequests++;
    if(mode==='loading') await new Promise(r=>{releaseLoading=r;});
    if(mode==='error') return route.fulfill({status:503,json:{detail:'isolated QA unavailable'}});
    if(mode==='empty') return route.fulfill({json:{product_id:product,best_offer_id:null,offers:[]}});
    if(mode==='observed') return route.fulfill({json:observed.body});
    let offers=[fixture];
    if(mode==='unknown_shipping') offers=[{...fixture,total_price:null,shipping_cost:null,shipping_label:null}];
    if(mode==='multiple') offers=[fixture,{...fixture,offer_id:'qa-rc1-second',merchant_name:'QA second',total_price:100}];
    return route.fulfill({json:{product_id:product,best_offer_id:fixture.offer_id,offers,affiliate_disclosure:'Artificial isolated QA'}});
   }
   if(u.pathname.startsWith('/api/')) {forbidden.push(u.pathname);return route.abort();}
   if(u.origin!==origin)return route.abort();
   return route.continue();
  });
  const page=await context.newPage();activePage=page;
  const params=source==='instagram'?'src=instagram&cmp=qa_rc1&content=qa_landing':'utm_source=youtube&utm_campaign=qa_rc1&utm_content=qa_landing';
  await page.goto(`${baseUrl}/duft/rabanne-1-million?qa=1&${params}`);
  const merchant=page.getByRole('link',{name:'Bei Perfumetrader ansehen',exact:true});await merchant.waitFor();
  await page.evaluate(()=>document.fonts.ready);
  const hero=page.locator('.dufynd-fragrance-hero');
  assert.equal(await hero.getAttribute('data-product-id'),product);
  assert.equal(await hero.getAttribute('data-dufynd-photo-hold'),'true');
  assert.equal(await hero.locator('img,model-viewer,canvas').count(),0);
  assert.match(await hero.innerText(),/Rabanne/i);assert.match(await hero.innerText(),/1 Million/);
  assert.match(await hero.innerText(),/Eau de Toilette[\s\S]*100 ml/);
  assert.match(await hero.innerText(),/Originalfoto in Prüfung/);
  assert.doesNotMatch(await page.locator('body').innerText(),/Preisreferenz|67,95/);
  const metrics=await page.evaluate(()=>({stage:document.querySelector('.dufynd-fragrance-stage-shell').getBoundingClientRect().height,cta:document.querySelector('#dufynd-hero-offer-cta').getBoundingClientRect().bottom,offers:document.querySelector('#angebote').getBoundingClientRect().top,overflow:document.documentElement.scrollWidth>innerWidth}));
  assert.ok(metrics.stage<=(width===390?64:96),JSON.stringify(metrics));
  assert.ok(metrics.cta<(width===390?520:500),JSON.stringify(metrics));
  assert.ok(metrics.offers<(width===390?780:650),JSON.stringify(metrics));assert.equal(metrics.overflow,false);
  assert.ok((await page.locator('#dufynd-hero-offer-cta').boundingBox()).height>=44);
  assert.ok((await merchant.boundingBox()).height>=44);
  const section=page.locator('[data-merchant-offers]');
  assert.match(await section.innerText(),/76,89[\s\S]*Gesamtpreis inkl. Versand/);
  assert.match(await section.innerText(),/Artikel 71,90 € · 4,99 €/);
  assert.match(await section.innerText(),/Werbung · Partnerlink/i);
  assert.doesNotMatch(await section.innerText(),/Bester Gesamtpreis|Beste verfügbare Option/i);
  const href=new URL(await merchant.getAttribute('href'),baseUrl);
  assert.equal(href.pathname,quote.clickout_path);
  for(const [k,v] of [['src',source],['cmp','qa_rc1'],['content','qa_landing'],['sid',session]])assert.equal(href.searchParams.get(k),v);
  assert.match(await merchant.getAttribute('rel'),/sponsored/);
  const catalog=page.locator('nav[aria-label="Breadcrumb"] a').filter({hasText:'Düfte'});
  const catalogHref=new URL(await catalog.getAttribute('href'),baseUrl);
  for(const [k,v] of [['src',source],['cmp','qa_rc1'],['content','qa_landing']])assert.equal(catalogHref.searchParams.get(k),v);
  const schemas=await page.locator('script[type="application/ld+json"]').allTextContents();
  const schema=schemas.map(s=>JSON.parse(s)).find(s=>s['@type']==='Product');assert.equal(schema.sku,product);assert.equal(schema.image,undefined);
  assert.equal(await page.locator('meta[property="og:image"]').count(),0);
  if(source==='instagram') {
   await page.screenshot({path:path.join(output,`rc1-offer-${width}.png`),fullPage:true});
   await section.screenshot({path:path.join(output,`rc1-offer-${width}-section.png`)});
  }
  await page.locator('#dufynd-hero-offer-cta').click();await page.waitForFunction(()=>location.hash==='#angebote');
  for(let i=0;i<40&&!localEvents.some(e=>e.event==='offer_section_open');i++)await page.waitForTimeout(50);
  assert.ok(localEvents.some(e=>e.event==='fragrance_detail_view'&&e.product_id===product));
  assert.ok(localEvents.some(e=>e.event==='offer_section_open'));
  checks.push({test:'identity-offer-attribution',source,width,metrics,status:'passed'});
  if(source==='instagram') {
   for(const state of ['error','empty']) {
    mode=state;await page.goto(`${baseUrl}/duft/rabanne-1-million?qa=1&${params}`);
    const panel=page.locator(`[data-offer-state="${state}"]`);await panel.waitFor();
    assert.match(await panel.innerText(),state==='error'?/Angebote gerade nicht erreichbar/:/Zurzeit kein aktuelles Angebot/);
    assert.equal(await panel.locator('a[target="_blank"]').count(),0);
    assert.equal(await page.locator('[data-merchant-offers]').count(),0);
    assert.doesNotMatch(await page.locator('body').innerText(),/Preisreferenz|67,95|71,90|76,89|95,00/);
    assert.ok(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth));
    await page.screenshot({path:path.join(output,`rc1-${state}-${width}.png`),fullPage:true});
    if(state==='error') {
     mode='fixture';const requests=offerRequests;
     const retry=page.getByRole('button',{name:'Angebote erneut prüfen',exact:true});assert.ok((await retry.boundingBox()).height>=44);
     await retry.click();await merchant.waitFor();assert.ok(offerRequests>requests);
     assert.equal(await page.locator('[data-offer-state="error"]').count(),0);
     const recovered=new URL(await merchant.getAttribute('href'),baseUrl);
     for(const [k,v] of [['src',source],['cmp','qa_rc1'],['content','qa_landing']])assert.equal(recovered.searchParams.get(k),v);
     assert.match(await section.innerText(),/95,00/);
    }
    checks.push({test:state==='error'?'error-and-retry':'empty',width,status:'passed'});
   }
   mode='loading';await page.goto(`${baseUrl}/duft/rabanne-1-million?qa=1&${params}`,{waitUntil:'domcontentloaded'});
   await page.locator('[data-offer-state="loading"][aria-busy="true"]').waitFor();
   assert.equal(await page.locator('[data-merchant-offers]').count(),0);
   assert.ok(releaseLoading);mode='fixture';releaseLoading();await merchant.waitFor();
   checks.push({test:'loading-resolves',width,status:'passed'});
   for(const variant of ['unknown_shipping','multiple']) {
    mode=variant;await page.reload();await merchant.waitFor();
    if(variant==='unknown_shipping') {assert.equal(await page.locator('[data-offer-price-basis]').count(),0);assert.match(await section.innerText(),/zzgl. ggf. Versand/);}
    else assert.match(await section.innerText(),/Bester Gesamtpreis · hier gelistet/i);
    checks.push({test:variant,width,status:'passed'});
   }
  }
  for(const event of localEvents) {assert.equal(event.internal_qa,true);assert.equal(event.acquisition_source,source);assert.equal(event.campaign_id,'qa_rc1');assert.equal(event.content_id,'qa_landing');}
  events.push(...localEvents);await context.close();
 }
 // Reuse the integration base's actual start -> catalog -> detail funnel tests.
 const {verifyFirstMoneyFunnel}=await import(pathToFileURL(path.join(candidate,'examples/retail/storefront-web/scripts/first-money-funnel-qa.mjs')));
 const isolatedBrowser={async newContext(options){const c=await browser.newContext({...options,serviceWorkers:'block'});await c.route('**/*',route=>{const u=new URL(route.request().url());if(u.pathname.startsWith('/api/clickout/')){forbidden.push(u.pathname);return route.abort();}if(u.origin!==origin||u.pathname.startsWith('/api/'))return route.abort();return route.continue();});return c;}};
 const funnelCases=await verifyFirstMoneyFunnel(isolatedBrowser,baseUrl);assert.equal(funnelCases,4);
 checks.push({test:'unchanged-base-start-catalog-detail-funnel',cases:funnelCases,status:'passed'});
 assert.deepEqual(forbidden,[]);
 writeFileSync(path.join(output,'browser.json'),JSON.stringify({status:'passed',checks,offer_evidence:observed,real_merchant_clickouts:0,production_events:0,intercepted_internal_qa_events:events.length},null,2));
 console.log(JSON.stringify({status:'passed',checks:checks.length,funnel_cases:funnelCases}));
} catch(error) {
 if(activePage&&!activePage.isClosed())await activePage.screenshot({path:path.join(output,'failure.png'),fullPage:true}).catch(()=>{});
 writeFileSync(path.join(output,'browser-failure.json'),JSON.stringify({error:String(error),stack:error.stack,checks},null,2));throw error;
} finally {await browser.close();}
