import { chooseMeasurement } from "./measurement-choice-qa.mjs";
import assert from 'node:assert/strict';

// Route readiness is verified by the semantic headings and controls below.
// Network-idle is not a valid readiness gate while analytics, image decoding or
// async search are active; it can deadlock on an otherwise functional page.
export async function verifyConversionSearch(browser, baseUrl, outputDir) {
  const cases=[];
  for (const width of [320,390,1440]) {
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
      const rc1Card=page.locator('.dufynd-catalog-card').filter({has:verifiedRc1Entry});
      const catalogUrl=page.url();
      // Exercise the exact card after adding its offer CTA: these actions must
      // remain independent, operable and in-bounds even at the 320px minimum.
      const save=rc1Card.getByRole('button',{name:'♡ Merken',exact:true});
      await save.click();
      const saved=rc1Card.getByRole('button',{name:'✓ Gemerkt',exact:true});
      await saved.waitFor({state:'visible'});
      assert.equal(await saved.getAttribute('aria-pressed'),'true');
      await rc1Card.getByRole('button',{name:'Rabanne 1 Million für Vergleich auswählen',exact:true}).click();
      const selected=rc1Card.getByRole('button',{name:'Rabanne 1 Million aus Vergleich entfernen',exact:true});
      await selected.waitFor({state:'visible'});
      assert.equal(await selected.getAttribute('aria-pressed'),'true');
      assert.equal(page.url(),catalogUrl,'Save/compare must not navigate to the profile or merchant');
      const actionLayout=await rc1Card.evaluate(card=>{
        const box=element=>{const b=element.getBoundingClientRect();return {left:b.left,right:b.right,top:b.top,bottom:b.bottom,width:b.width,height:b.height};};
        return {
          card:box(card),
          cta:box(card.querySelector('a[data-dufynd-catalog-rc1-offer]')),
          buttons:[...card.querySelectorAll('.dufynd-catalog-card-actions button')].map(box),
        };
      });
      assert.equal(actionLayout.buttons.length,3,'RC1 retains save, collection and compare actions');
      for(const button of actionLayout.buttons) {
        assert.ok(button.width>0 && button.height>0 &&
          button.left>=actionLayout.card.left-1 && button.right<=actionLayout.card.right+1,
          `${width}: every RC1 action remains visible inside its card`);
        assert.ok(button.bottom<=actionLayout.cta.top+1 || button.top>=actionLayout.cta.bottom-1 ||
          button.right<=actionLayout.cta.left+1 || button.left>=actionLayout.cta.right-1,
          `${width}: RC1 offer CTA must not overlap save/compare actions`);
      }
      assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth+1),false,
        'Selected RC1 actions must not add horizontal overflow');
      if(outputDir) await rc1Card.screenshot({path:`${outputDir}/conversion-search-${width}-rc1-selected.png`});
      await selected.click();
      await rc1Card.getByRole('button',{name:'Rabanne 1 Million für Vergleich auswählen',exact:true}).waitFor({state:'visible'});
      await saved.click();
      await save.waitFor({state:'visible'});
      assert.equal(await save.getAttribute('aria-pressed'),'false');
      assert.equal(page.url(),catalogUrl,'Removing save/compare state must not navigate');
      if(outputDir) await rc1Card.screenshot({path:`${outputDir}/conversion-search-${width}-rc1-catalog.png`});
      await verifiedRc1Entry.click();
      await page.waitForURL(url=>url.pathname==='/duft/rabanne-1-million'&&url.hash==='#angebote');
      assert.equal(new URL(page.url()).searchParams.get('src'),'instagram','Catalog RC1 offer link preserves campaign source');
      assert.equal(new URL(page.url()).searchParams.get('cmp'),'qa_conversion','Catalog RC1 offer link preserves campaign ID');
      await page.locator('#angebote').waitFor({state:'visible'});
      // Inspect the actual exported head and decoded asset, in addition to the
      // isolated metadata unit test: this RC1 currently has no licensed photo.
      const socialPath='/assets/social/dufynd-rabanne-1-million-og.png';
      const ogImage=await page.locator('meta[property="og:image"]').getAttribute('content');
      const twitterImage=await page.locator('meta[name="twitter:image"]').getAttribute('content');
      assert.equal(new URL(ogImage,baseUrl).pathname,socialPath);
      assert.equal(new URL(twitterImage,baseUrl).pathname,socialPath);
      assert.equal(await page.locator('meta[name="twitter:card"]').getAttribute('content'),'summary_large_image');
      assert.match(await page.locator('meta[property="og:image:alt"]').getAttribute('content'),/kein Produktfoto/);
      const decodedSocial=await page.evaluate(path=>new Promise((resolve,reject)=>{
        const image=new Image();
        const timer=setTimeout(()=>reject(new Error('RC1 social asset did not decode')),5000);
        image.onload=()=>{clearTimeout(timer);resolve({width:image.naturalWidth,height:image.naturalHeight});};
        image.onerror=()=>{clearTimeout(timer);reject(new Error('RC1 social asset could not load'));};
        image.src=path;
      }),socialPath);
      assert.deepEqual(decodedSocial,{width:1200,height:630});

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
      cases.push({width,home_search:true,social_search:true,wrong_variant_excluded:true,attribution:true,catalog_rc1_offer_route:true,rc1_save_compare_actions:true,rc1_exported_social_metadata:true,non_rc1_offer_claim_suppressed:true,empty_offer_fallback:true,clickouts:0});
    } finally {await context.close();}
  }
  return cases;
}
