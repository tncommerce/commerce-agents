import { chooseMeasurement } from "./measurement-choice-qa.mjs";
import assert from 'node:assert/strict';

// Route readiness is verified by the semantic headings and controls below.
// Network-idle is not a valid readiness gate while analytics, image decoding or
// async search are active; it can deadlock on an otherwise functional page.
export async function verifyConversionSearch(browser, baseUrl, outputDir) {
  const cases=[];
  for (const width of [390,1440]) {
    const context=await browser.newContext({viewport:{width,height:900}});
    const events=[];
    await context.route('**/api/session',r=>r.fulfill({json:{session_id:'qa-conversion-search-session'}}));
    await context.route((url) => url.pathname === '/api/analytics/events',async r=>{const event=r.request().postDataJSON();events.push(event);if(event.event==='catalog_search') await new Promise(resolve=>setTimeout(resolve,150));return r.fulfill({json:{ok:true}}).catch(()=>{});});
    await context.route('**/api/clickout/**',r=>{throw new Error('Conversion QA must never trigger a clickout');});
    await context.route('**/api/merchant-offers/**',r=>r.fulfill({json:{offers:[],best_offer_id:null}}));
    const page=await context.newPage();
    try {
      await page.goto(`${baseUrl}/?qa=1&src=instagram&cmp=qa_conversion&content=qa_search`,{waitUntil:'domcontentloaded'});
      await chooseMeasurement(page, 'granted');
      await page.locator('#dufynd-home-search').fill('YSL Libre EDP 90ml');
      await page.getByRole('search',{name:'DUFYND Duftkatalog durchsuchen'}).getByRole('button',{name:'Suchen',exact:true}).click();
      await page.getByRole('heading',{name:'Libre',exact:true}).waitFor();
      assert.equal(new URL(page.url()).searchParams.get('src'),'instagram');
      assert.equal(new URL(page.url()).searchParams.get('cmp'),'qa_conversion');
      if(outputDir) await page.screenshot({path:`${outputDir}/conversion-search-${width}-catalog.png`,fullPage:true});
      // Catalog offer claims must be bound to the only published affiliate
      // product; a non-offered fragrance must never show a buy-intent link.
      assert.equal(await page.locator('a[data-dufynd-catalog-rc1-offer]').count(),0);
      assert.equal(
        (await page.locator('.dufynd-catalog-card-cta').first().innerText()).trim(),
        'Duftprofil entdecken →',
      );
      await page.goto(`${baseUrl}/duft?q=Rabanne%201%20Million&qa=1&src=instagram&cmp=qa_conversion&content=qa_search`,{waitUntil:'domcontentloaded'});
      const verifiedRc1Entry=page.locator('a[data-dufynd-catalog-rc1-offer]');
      await verifiedRc1Entry.waitFor({state:'visible'});
      assert.equal(await verifiedRc1Entry.count(),1,'Exact RC1 alone has a catalog offer shortcut');
      const rc1Target=new URL(await verifiedRc1Entry.getAttribute('href'),baseUrl);
      assert.equal(rc1Target.pathname,'/duft/rabanne-1-million');
      assert.equal(rc1Target.hash,'#angebote');
      assert.match(await verifiedRc1Entry.getAttribute('aria-label'),/Rabanne 1 Million.*100 ml/);
      const rc1Layout=await verifiedRc1Entry.evaluate(link=>{
        const [label,arrow]=link.querySelectorAll(':scope > span');
        if(!label||!arrow) return null;
        const rect=node=>{const b=node.getBoundingClientRect();return {x:b.x,y:b.y,w:b.width,h:b.height,right:b.right,centerY:b.y+b.height/2};};
        const card=link.closest('article');
        const actions=card?.querySelector('.dufynd-catalog-card-actions');
        return {button:rect(link),label:rect(label),arrow:rect(arrow),actions:actions?rect(actions):null,caption:label.textContent?.trim()};
      });
      assert.ok(rc1Layout,'Exact RC1 must have a meaningful label and separate arrow');
      assert.equal(rc1Layout.caption,'Händlerangebote prüfen');
      assert.ok(rc1Layout.button.h>=44 && rc1Layout.button.h<=64,'RC1 CTA must remain a compact accessible button');
      assert.ok(Math.abs(rc1Layout.label.centerY-rc1Layout.arrow.centerY)<=5,
        `${width}: CTA arrow must share the text line (not wrap below it)`);
      assert.ok(rc1Layout.arrow.x>rc1Layout.label.x+rc1Layout.label.w,
        `${width}: arrow must be placed after the text`);
      if(width>=1024) assert.ok(rc1Layout.actions &&
        rc1Layout.actions.x>=rc1Layout.button.x-2 &&
        rc1Layout.actions.right<=rc1Layout.button.right+2,
        'Desktop archive action buttons must share the RC1 right-hand column');
      assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth+1),false,
        'RC1 catalog CTA must not add horizontal overflow');
      if(outputDir) await page.locator('.dufynd-catalog-card').filter({has:verifiedRc1Entry}).screenshot({path:`${outputDir}/conversion-search-${width}-rc1-catalog.png`});
      await verifiedRc1Entry.click();
      await page.waitForURL(url=>url.pathname==='/duft/rabanne-1-million'&&url.hash==='#angebote');
      assert.equal(new URL(page.url()).searchParams.get('src'),'instagram','Catalog RC1 offer link preserves campaign source');
      assert.equal(new URL(page.url()).searchParams.get('cmp'),'qa_conversion','Catalog RC1 offer link preserves campaign ID');
      await page.locator('#angebote').waitFor({state:'visible'});
      await page.goto(`${baseUrl}/duft?q=YSL%20Libre%2050ml&qa=1`,{waitUntil:'domcontentloaded'});
      await page.getByRole('heading',{name:'Keine passenden Düfte gefunden',exact:true}).waitFor();
      await page.goto(`${baseUrl}/start?qa=1&src=instagram&cmp=qa_conversion&content=qa_search`,{waitUntil:'domcontentloaded'});
      const input=page.getByLabel('Duft oder Marke suchen',{exact:true});
      await input.fill('Libre YSL EDP 90ml');
      const results=page.locator('[data-dufynd-social-live-results]');
      await results.getByRole('link').first().waitFor();
      assert.match(await results.innerText(),/Eau de Parfum · 90 ml/);
      if(outputDir) await page.screenshot({path:`${outputDir}/conversion-search-${width}-start.png`,fullPage:true});
      if(width===390) await input.press('Enter');
      else await results.getByRole('link').first().click();
      await page.waitForURL('**/duft/yves-saint-laurent-libre**');
      assert.equal(new URL(page.url()).searchParams.get('src'),'instagram');
      await page.locator('#dufynd-hero-offer-cta').click();
      assert.ok(await page.locator('#angebote').evaluate(el => {const r=el.getBoundingClientRect();return r.top < innerHeight && r.bottom > 0;}), 'offer anchor must reach the offers section');
      assert.match(await page.locator('.dufynd-journey-offers').innerText(),/kein ausreichend aktuelles/);
      assert.equal(await page.locator('a[href*="/api/clickout/"]').count(),0);
      assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth),false);
      const deadline=Date.now()+3000;
      while(!events.some(e=>e.event==='product_open'&&e.product_id==='SC-YSL-LIBRE-EDP-90') && Date.now()<deadline) await new Promise(resolve=>setTimeout(resolve,50));
      assert.ok(events.some(e=>e.event==='product_open'&&e.product_id==='SC-YSL-LIBRE-EDP-90'), 'product_open survives delayed search receipt and navigation');
      assert.ok(events.every(e=>e.internal_qa===true));
      if(width===390) {
        // A previous delayed receipt may still be outstanding. Full network
        // quiet is not a readiness condition; the visible search control is.
        await page.goto(`${baseUrl}/start?qa=1`,{waitUntil:'load'});
        const stalledSearch=page.getByLabel('Duft oder Marke suchen',{exact:true});
        await stalledSearch.waitFor({state:'visible'});
        await context.route((url) => url.pathname === '/api/analytics/events',()=>{});
        await stalledSearch.fill('PDM Delina 75ml');
        const started=Date.now();
        await stalledSearch.press('Enter');
        await page.waitForURL('**/duft/parfums-de-marly-delina**',{waitUntil:'domcontentloaded',timeout:5000});
        assert.ok(Date.now()-started<4000,'stalled analytics must not block navigation');
      }
      cases.push({width,home_search:true,social_search:true,wrong_variant_excluded:true,attribution:true,catalog_rc1_offer_route:true,non_rc1_offer_claim_suppressed:true,empty_offer_fallback:true,clickouts:0});
    } finally {await context.close();}
  }
  cases.push(...await verifyProductNameAliases(browser, baseUrl, outputDir));
  return cases;
}

// Existing social content uses #onemillion. All spelling variants must reach
// the same exact published fragrance, without expanding size or concentration.
export async function verifyProductNameAliases(browser, baseUrl, outputDir) {
  assert.ok(['127.0.0.1','localhost','[::1]'].includes(new URL(baseUrl).hostname));
  const cases=[];
  for(const width of [320,390,768,1440]) {
    const consent=[390,1440].includes(width)?'granted':'denied';
    const context=await browser.newContext({viewport:{width,height:900},hasTouch:width<1024,
      reducedMotion:consent==='denied'?'reduce':'no-preference'});
    const events=[],clickouts=[],errors=[];
    await context.route('**/api/**',route=>{
      const request=route.request(),url=new URL(request.url());
      if(url.pathname.includes('/clickout/')) {clickouts.push(url.pathname);return route.abort();}
      if(url.pathname==='/api/session') return route.fulfill({json:{session_id:'qa-rc1-alias-session'}});
      if(url.pathname==='/api/analytics/events') {events.push(request.postDataJSON());return route.fulfill({json:{ok:true}});}
      if(url.pathname==='/api/products') return route.fulfill({json:{products:[]}});
      if(url.pathname.startsWith('/api/merchant-offers/')) return route.fulfill({json:{offers:[],best_offer_id:null}});
      return route.fulfill({status:503,json:{detail:'Isolated alias QA fixture'}});
    });
    const page=await context.newPage();
    page.on('pageerror',error=>errors.push(error.message));
    try {
      const attribution='qa=1&src=instagram&cmp=qa_rc1_alias&content=qa_one_million';
      await page.goto(`${baseUrl}/start?${attribution}`,{waitUntil:'load'});
      await chooseMeasurement(page,consent);
      const input=page.getByLabel('Duft oder Marke suchen',{exact:true});
      const results=page.locator('[data-dufynd-social-live-results]');
      for(const query of ['One Million','onemillion','1million','Paco Rabanne One Million EDT 100ml']) {
        await input.fill(query);
        const link=results.getByRole('link');
        await link.first().waitFor({state:'visible'});
        assert.equal(await link.count(),1,`${width}: ${query} resolves only the published RC1`);
        assert.match(await link.innerText(),/Eau de Toilette · 100 ml/);
        assert.equal(new URL(await link.getAttribute('href'),baseUrl).pathname,'/duft/rabanne-1-million');
      }
      await input.fill('onemillion');
      const result=results.getByRole('link').first();
      await result.waitFor({state:'visible'});
      const bounds=await result.boundingBox();
      assert.ok(bounds && bounds.height>=44 && bounds.x>=0 && bounds.x+bounds.width<=width+1);
      assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth+1),false);
      if(outputDir) await page.screenshot({path:`${outputDir}/alias44-${width}-social.png`,fullPage:true});
      if(width<1024) await result.tap(); else {await result.focus();await result.press('Enter');}
      await page.waitForURL(url=>url.pathname==='/duft/rabanne-1-million');
      if(consent==='granted') {
        assert.equal(new URL(page.url()).searchParams.get('src'),'instagram');
        assert.equal(new URL(page.url()).searchParams.get('cmp'),'qa_rc1_alias');
      }
      for(const query of ['One Million EDT 100ml','onemillion','1million']) {
        await page.goto(`${baseUrl}/duft?q=${encodeURIComponent(query)}&${attribution}`,{waitUntil:'load'});
        const offer=page.locator('a[data-dufynd-catalog-rc1-offer]');
        await offer.waitFor({state:'visible'});
        assert.equal(await offer.count(),1);
        assert.equal(await page.locator('.dufynd-catalog-card').count(),1);
        assert.equal(new URL(await offer.getAttribute('href'),baseUrl).pathname,'/duft/rabanne-1-million');
        assert.equal(new URL(await offer.getAttribute('href'),baseUrl).hash,'#angebote');
        assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth+1),false);
      }
      if(outputDir) await page.screenshot({path:`${outputDir}/alias44-${width}-catalog.png`,fullPage:true});
      await page.locator('a[data-dufynd-catalog-rc1-offer]').click();
      await page.waitForURL(url=>url.pathname==='/duft/rabanne-1-million'&&url.hash==='#angebote');
      assert.ok(await page.locator('#angebote').evaluate(el=>{const r=el.getBoundingClientRect();return r.top<innerHeight&&r.bottom>0;}));
      assert.equal(await page.locator('a[href*="/api/clickout/"]').count(),0,'empty fixture cannot invent an offer');
      if(outputDir) await page.screenshot({path:`${outputDir}/alias44-${width}-offers.png`,fullPage:true});
      if(width===390) for(const query of ['One Million EDT 50ml','One Million EDP 100ml','One Million Lucky','One Million Elixir']) {
        await page.goto(`${baseUrl}/duft?q=${encodeURIComponent(query)}&${attribution}`,{waitUntil:'load'});
        await page.getByRole('heading',{name:'Keine passenden Düfte gefunden',exact:true}).waitFor();
        assert.equal(await page.locator('a[data-dufynd-catalog-rc1-offer]').count(),0);
      }
      if(consent==='denied') assert.deepEqual(events,[],'alias discovery works without optional analytics');
      else assert.ok(events.some(e=>e.event==='product_open'&&e.product_id==='SC-RABANNE-1-MILLION-EDT-100'));
      assert.deepEqual(clickouts,[]);
      assert.deepEqual(errors,[]);
      cases.push({suite:'rc1-name-alias',width,consent,social_queries:4,catalog_queries:3,
        touch:width<1024,keyboard:width===1440,reduced_motion:consent==='denied',exact_offer_anchor:true,
        wrong_variants_excluded:width===390,analytics_requests:events.length,merchant_clickouts:0});
    } finally {await context.close();}
  }
  return cases;
}
