import { emptyOfferFixture } from "./merchant-offer-fixture-qa.mjs";
import { chooseMeasurement } from "./measurement-choice-qa.mjs";
import { verifyCompactFragranceSearch } from "./compact-fragrance-search-qa.mjs";
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
    await context.route('**/api/merchant-offers/**',r=>r.fulfill({json:emptyOfferFixture(r)}));
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
      // Only the Rabanne RC1 card has a separate catalog offer shortcut.
      // Other released offers are accessible through the respective product profile.
      // The catalog may show other matched cards (including Rabanne).
      // Assert the Libre card itself cannot inherit a Rabanne-only shortcut.
      const libreCard = page.locator('article.dufynd-catalog-card').filter({
        has: page.getByRole('heading', {name: 'Libre', exact: true}),
      }).first();
      await libreCard.waitFor({state: 'visible'});
      assert.equal(await libreCard.locator('a[data-dufynd-catalog-rc1-offer]').count(),0);
      assert.equal(
        (await libreCard.locator('.dufynd-catalog-card-cta').innerText()).trim(),
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
      // Catalog hydration may reserialize an identical search from %20 to +.
      // Compare the complete URL after standard query encoding; do not drop
      // origin, path, fragment, query values, duplicate params or their order.
      const normalizedUrl=href=>{
        const url=new URL(href);
        url.search=url.searchParams.toString();
        return url.href;
      };
      const catalogUrl=normalizedUrl(page.url());
      await page.evaluate(() => { window.qaCatalogDocument = "synthetic-catalog-action"; });
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
      const selectedCatalogUrl=new URL(catalogUrl);
      selectedCatalogUrl.searchParams.set('compare','SC-RABANNE-1-MILLION-EDT-100');
      assert.equal(normalizedUrl(page.url()),normalizedUrl(selectedCatalogUrl.href),'Save/compare only updates the functional selection parameter');
      assert.equal(await page.evaluate(() => window.qaCatalogDocument),'synthetic-catalog-action','Save/compare must not navigate to the profile or merchant');
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
      assert.equal(normalizedUrl(page.url()),catalogUrl,'Removing save/compare state must not navigate');
      if(outputDir) await rc1Card.screenshot({path:`${outputDir}/conversion-search-${width}-rc1-catalog.png`});
      await verifiedRc1Entry.click();
      await page.waitForURL(url=>url.pathname==='/duft/rabanne-1-million'&&url.hash==='#angebote');
      assert.equal(new URL(page.url()).searchParams.get('src'),'instagram','Catalog RC1 offer link preserves campaign source');
      assert.equal(new URL(page.url()).searchParams.get('cmp'),'qa_conversion','Catalog RC1 offer link preserves campaign ID');
      await page.locator('#angebote').waitFor({state:'visible'});
      // The independently rejected editorial creative is excluded. Product
      // metadata stays truthful and uses a compact text-only social summary.
      assert.equal(await page.locator('meta[property="og:image"]').count(),0);
      assert.equal(await page.locator('meta[name="twitter:image"]').count(),0);
      assert.equal(await page.locator('meta[name="twitter:card"]').getAttribute('content'),'summary');
      assert.match(await page.locator('meta[property="og:title"]').getAttribute('content'),/Rabanne 1 Million.*100 ml/);

      await page.goto(`${baseUrl}/duft?q=YSL%20Libre%2050ml&qa=1`,{waitUntil:'domcontentloaded'});
      await page.getByRole('heading',{name:'Keine passenden Düfte gefunden',exact:true}).waitFor();
      await page.goto(`${baseUrl}/start?qa=1&src=instagram&cmp=qa_conversion&content=qa_search`,{waitUntil:'load'});
      const input=page.getByLabel('Duft oder Marke suchen',{exact:true});
      await input.waitFor({state:'visible'});
      // Wait for React hydration; SSR alone does not attach live-search handlers.
      await page.waitForFunction(() => {
        const element=document.getElementById('dufynd-social-search');
        return !!element&&Object.keys(element).some(key=>key.startsWith('__reactProps$'));
      },null,{timeout:12_000});
      await input.fill('Libre YSL EDP 90ml');
      const results=page.locator('[data-dufynd-social-live-results]');
      await results.getByRole('link').first().waitFor({state:'visible',timeout:12_000});
      assert.match(await results.innerText(),/Eau de Parfum · 90 ml/);
      if(outputDir) await page.screenshot({path:`${outputDir}/conversion-search-${width}-start.png`,fullPage:true});
      if(width===390) await input.press('Enter');
      else await results.getByRole('link').first().click();
      await page.waitForURL('**/duft/yves-saint-laurent-libre**');
      assert.equal(new URL(page.url()).searchParams.get('src'),'instagram');
      // SEO buyer-guide visual proof on the REAL static export, not a mocked
      // component. This is isolated to Libre EDP 90ml and must not click
      // merchant links or write real analytics.
      const guide=page.locator('[data-dufynd-libre-refill-guide]');
      assert.equal(await guide.count(),1,'only one Libre buying guide may be rendered');
      assert.equal(await guide.getByRole('heading',{name:'YSL Libre EDP 90 ml: nachfüllbarer Flakon oder Refill?'}).count(),1);
      assert.match(await guide.innerText(),/VZR11010/);
      assert.match(await guide.innerText(),/nachfüllbarer Flakon/);
      assert.match(await guide.innerText(),/Werbung · DUFYND enthält Affiliate-Links/);
      assert.equal(await guide.locator('a[href="#angebote"]').count(),2,'both editorial CTAs must remain internal');
      assert.equal(await guide.locator('a[href*="/api/clickout/"]').count(),0);
      await guide.scrollIntoViewIfNeeded();
      const bounds=await guide.boundingBox();
      assert.ok(bounds&&bounds.x>=-1&&bounds.x+bounds.width<=width+1,`${width}: Libre guide is outside viewport`);
      assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth+1),false,`${width}: Libre guide causes horizontal overflow`);
      if(outputDir) await guide.screenshot({path:`${outputDir}/libre-refill-guide-${width}.png`,animations:'disabled'});
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
      cases.push({width,home_search:true,social_search:true,wrong_variant_excluded:true,attribution:true,catalog_rc1_offer_route:true,rc1_save_compare_actions:true,rc1_unapproved_creative_excluded:true,non_rc1_offer_claim_suppressed:true,empty_offer_fallback:true,clickouts:0});
    } finally {await context.close();}
  }
  cases.push(...await verifyProductNameAliases(browser, baseUrl, outputDir));
  cases.push(...await verifyCompactFragranceSearch(browser, baseUrl, outputDir));
  return cases;
}

// Port of the tested #799 aliases; the release additionally follows real
// /start -> /duft -> RC1#angebote navigation for both social sources.
export async function verifyProductNameAliases(browser, baseUrl, outputDir) {
  assert.ok(['127.0.0.1','localhost','[::1]'].includes(new URL(baseUrl).hostname));
  const cases=[];
  for(const width of [320,390,768,1440]) for(const source of ['instagram','tiktok']) {
    const consent=([390,1440].includes(width)===(source==='instagram'))?'granted':'denied';
    const context=await browser.newContext({viewport:{width,height:900},hasTouch:width<1024,
      reducedMotion:consent==='denied'?'reduce':'no-preference'});
    const events=[],clickouts=[],errors=[];
    const campaign='qa_rc1_alias',content='qa_one_million';
    await context.route('**/api/**',route=>{
      const request=route.request(),url=new URL(request.url());
      if(/\/clickout(?:\/|$)/.test(url.pathname)) {clickouts.push(url.pathname);return route.abort();}
      if(url.pathname==='/api/session') return route.fulfill({json:{session_id:'qa-rc1-alias-session'}});
      if(url.pathname==='/api/analytics/events') {events.push(request.postDataJSON());return route.fulfill({json:{ok:true}});}
      if(url.pathname==='/api/products') return route.fulfill({json:{products:[]}});
      if(url.pathname.startsWith('/api/merchant-offers/')) return route.fulfill({json:emptyOfferFixture(route)});
      return route.fulfill({status:503,json:{detail:'Isolated alias QA fixture'}});
    });
    const page=await context.newPage();
    page.on('pageerror',error=>errors.push(error.message));
    const activate=async locator=>{
      if(width<1024) await locator.tap();
      else {await locator.focus();await locator.press('Enter');}
    };
    let measurementSession;
    const assertAttribution=()=>{
      const url=new URL(page.url());
      if(consent==='granted') {
        for(const [key,value] of [['src',source],['cmp',campaign],['content',content],['sid',measurementSession],['qa','1']]) {
          assert.equal(url.searchParams.get(key),value,`${width}/${source}: ${key} survives actual navigation`);
        }
        assert.equal(url.searchParams.get('measurement'),null);
      } else for(const key of ['src','cmp','content','sid','measurement','utm_source','utm_medium','utm_campaign','utm_content','utm_term']) {
        assert.equal(url.searchParams.get(key),null,`${width}/${source}: denied ${key} must not propagate`);
      }
    };
    try {
      await page.goto(`${baseUrl}/start?qa=1&src=${source}&cmp=${campaign}&content=${content}`,{waitUntil:'load'});
      assert.deepEqual(events,[],'entry is not permission for optional analytics');
      await chooseMeasurement(page,consent);
      if(consent==='granted') {
        for(let attempt=0;attempt<100&&!events.some(e=>e.event==='page_view');attempt++) await page.waitForTimeout(25);
        measurementSession=events.find(e=>e.event==='page_view')?.analytics_session_id;
        assert.match(measurementSession,/^[a-f0-9-]{36}$/);
        assert.notEqual(measurementSession,'qa-rc1-alias-session');
      }
      const input=page.getByLabel('Duft oder Marke suchen',{exact:true});
      const results=page.locator('[data-dufynd-social-live-results]');
      for(const query of ['One Million','onemillion','1million','Paco Rabanne One Million EDT 100ml']) {
        await input.fill(query);
        const link=results.getByRole('link');
        await link.first().waitFor({state:'visible'});
        assert.equal(await link.count(),1,`${width}/${source}: ${query} resolves only the published RC1`);
        assert.match(await link.innerText(),/Eau de Toilette · 100 ml/);
        assert.equal(new URL(await link.getAttribute('href'),baseUrl).pathname,'/duft/rabanne-1-million');
      }
      await input.fill('onemillion');
      const result=results.getByRole('link').first();
      await result.waitFor({state:'visible'});
      const bounds=await result.boundingBox();
      assert.ok(bounds && bounds.height>=44 && bounds.x>=0 && bounds.x+bounds.width<=width+1);
      assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth+1),false);
      if(outputDir) await page.screenshot({path:`${outputDir}/alias45-${width}-${source}-social.png`,fullPage:true});
      await activate(result);
      await page.waitForURL(url=>url.pathname==='/duft/rabanne-1-million');
      assertAttribution();
      await activate(page.locator('#dufynd-hero-offer-cta'));
      assert.ok(await page.locator('#angebote').evaluate(el=>{const r=el.getBoundingClientRect();return r.top<innerHeight&&r.bottom>0;}));

      // Return to the existing entry without injecting campaign/session fields;
      // every following hop must carry (or strip) them through the actual UI.
      await page.goto(`${baseUrl}/start`,{waitUntil:'load'});
      await activate(page.getByRole('link',{name:'Katalog entdecken',exact:true}));
      await page.waitForURL(url=>url.pathname==='/duft');
      assertAttribution();
      const catalogSearch=page.getByRole('searchbox',{name:'Duft, Marke oder Profil',exact:true});
      for(const query of ['One Million EDT 100ml','onemillion','1million']) {
        await catalogSearch.fill(query);
        await page.waitForURL(url=>url.pathname==='/duft'&&url.searchParams.get('q')===query);
        const offer=page.locator('a[data-dufynd-catalog-rc1-offer]');
        await offer.waitFor({state:'visible'});
        assert.equal(await offer.count(),1);
        assert.equal(await page.locator('.dufynd-catalog-card').count(),1);
        assert.equal(new URL(await offer.getAttribute('href'),baseUrl).pathname,'/duft/rabanne-1-million');
        assert.equal(new URL(await offer.getAttribute('href'),baseUrl).hash,'#angebote');
        assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth+1),false);
        assertAttribution();
      }
      if(outputDir) await page.screenshot({path:`${outputDir}/alias45-${width}-${source}-catalog.png`,fullPage:true});
      const offer=page.locator('a[data-dufynd-catalog-rc1-offer]');
      const offerBounds=await offer.boundingBox();
      assert.ok(offerBounds&&offerBounds.height>=44&&offerBounds.x>=0&&offerBounds.x+offerBounds.width<=width+1);
      const beforeCatalogOffer=events.length;
      await activate(offer);
      await page.waitForURL(url=>url.pathname==='/duft/rabanne-1-million'&&url.hash==='#angebote');
      assertAttribution();
      assert.ok(await page.locator('#angebote').evaluate(el=>{const r=el.getBoundingClientRect();return r.top<innerHeight&&r.bottom>0;}));
      await page.locator('[data-offer-state="empty"]').waitFor({state:'visible'});
      assert.equal(await page.locator('a[href*="/api/clickout/"]').count(),0,'empty fixture cannot invent an offer');
      assert.match(await page.locator('.dufynd-journey-offers').innerText(),/kein ausreichend aktuelles/);
      if(outputDir) await page.screenshot({path:`${outputDir}/alias45-${width}-${source}-offers.png`,fullPage:true});
      if(consent==='granted') {
        const arrivedFromCatalog=()=>events.slice(beforeCatalogOffer).some(e=>e.event==='fragrance_detail_view'&&e.product_id==='SC-RABANNE-1-MILLION-EDT-100');
        for(let attempt=0;attempt<100&&!arrivedFromCatalog();attempt++) await page.waitForTimeout(25);
        assert.ok(arrivedFromCatalog(),'the final catalog-to-offer hop records its own exact detail arrival');
        for(const event of ['product_open','fragrance_detail_view']) assert.ok(events.some(e=>e.event===event&&e.product_id==='SC-RABANNE-1-MILLION-EDT-100'));
        for(const event of events) {
          assert.equal(event.analytics_session_id,measurementSession);
          assert.equal(event.acquisition_source,source);
          assert.equal(event.campaign_id,campaign);
          assert.equal(event.content_id,content);
          assert.equal(event.internal_qa,true);
        }
      }
      if(width===390) for(const query of ['One Million EDT 50ml','One Million EDP 100ml','One Million Lucky','One Million Elixir']) {
        await page.goto(`${baseUrl}/duft?q=${encodeURIComponent(query)}`,{waitUntil:'load'});
        await page.getByRole('heading',{name:'Keine passenden Düfte gefunden',exact:true}).waitFor();
        assert.equal(await page.locator('a[data-dufynd-catalog-rc1-offer]').count(),0);
      }
      if(consent==='denied') assert.deepEqual(events,[],'alias discovery works without optional analytics');
      assert.deepEqual(clickouts,[]);
      assert.deepEqual(errors,[]);
      cases.push({suite:'rc1-name-alias',width,source,consent,social_queries:4,catalog_queries:3,
        touch:width<1024,keyboard:width===1440,reduced_motion:consent==='denied',actual_catalog_navigation:true,
        exact_offer_anchor:true,session_campaign_preserved:consent==='granted',optional_fields_stripped:consent==='denied',
        wrong_variants_excluded:width===390,analytics_requests:events.length,merchant_clickouts:0});
    } finally {await context.close();}
  }
  return cases;
}
