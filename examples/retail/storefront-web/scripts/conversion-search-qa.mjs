import assert from 'node:assert/strict';

export async function verifyConversionSearch(browser, baseUrl, outputDir) {
  const cases=[];
  for (const width of [390,1440]) {
    const context=await browser.newContext({viewport:{width,height:900}});
    const events=[];
    await context.route('**/api/session',r=>r.fulfill({json:{session_id:'qa-conversion-search-session'}}));
    await context.route('**/api/analytics/events',async r=>{const event=r.request().postDataJSON();events.push(event);if(event.event==='catalog_search') await new Promise(resolve=>setTimeout(resolve,150));return r.fulfill({json:{ok:true}}).catch(()=>{});});
    await context.route('**/api/clickout/**',r=>{throw new Error('Conversion QA must never trigger a clickout');});
    await context.route('**/api/merchant-offers/**',r=>r.fulfill({json:{offers:[],best_offer_id:null}}));
    const page=await context.newPage();
    try {
      await page.goto(`${baseUrl}/?qa=1&src=instagram&cmp=qa_conversion&content=qa_search`,{waitUntil:'networkidle'});
      await page.locator('#dufynd-home-search').fill('YSL Libre EDP 90ml');
      await page.getByRole('search',{name:'DUFYND Duftkatalog durchsuchen'}).getByRole('button',{name:'Suchen',exact:true}).click();
      await page.getByRole('heading',{name:'Libre',exact:true}).waitFor();
      assert.equal(new URL(page.url()).searchParams.get('src'),'instagram');
      assert.equal(new URL(page.url()).searchParams.get('cmp'),'qa_conversion');
      if(outputDir) await page.screenshot({path:`${outputDir}/conversion-search-${width}-catalog.png`,fullPage:true});
      await page.goto(`${baseUrl}/duft?q=YSL%20Libre%2050ml&qa=1`,{waitUntil:'networkidle'});
      await page.getByRole('heading',{name:'Keine passenden Düfte gefunden',exact:true}).waitFor();
      await page.goto(`${baseUrl}/start?qa=1&src=instagram&cmp=qa_conversion&content=qa_search`,{waitUntil:'networkidle'});
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
        await page.goto(`${baseUrl}/start?qa=1`,{waitUntil:'networkidle'});
        await context.route('**/api/analytics/events',()=>{});
        await page.getByLabel('Duft oder Marke suchen',{exact:true}).fill('PDM Delina 75ml');
        const started=Date.now();
        await page.getByLabel('Duft oder Marke suchen',{exact:true}).press('Enter');
        await page.waitForURL('**/duft/parfums-de-marly-delina**',{waitUntil:'domcontentloaded',timeout:5000});
        assert.ok(Date.now()-started<4000,'stalled analytics must not block navigation');
      }
      cases.push({width,home_search:true,social_search:true,wrong_variant_excluded:true,attribution:true,empty_offer_fallback:true,clickouts:0});
    } finally {await context.close();}
  }
  return cases;
}
