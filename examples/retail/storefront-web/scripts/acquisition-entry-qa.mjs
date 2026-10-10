import assert from 'node:assert/strict';

export async function verifyAcquisitionEntry(browser, baseUrl) {
  const results=[];
  for (const width of [390,1440]) {
    for (const sample of [
      {query:'utm_source=youtube&utm_campaign=release_week&utm_content=profile',source:'youtube',campaign:'release_week',content:'profile'},
      {query:'src=instagram&cmp=launch01_high_end&content=profile&utm_source=youtube',source:'instagram',campaign:'launch01_high_end',content:'profile'},
      {query:'',referrer:'https://l.instagram.com/',source:'instagram'},
      {query:'',referrer:'https://www.google.de/search?q=private',source:'organic'},
      {query:'',source:'unknown'},
      {query:'utm_source=google&utm_medium=cpc&utm_campaign=paid_search',source:'google',campaign:'paid_search'},
    ]) {
      const context=await browser.newContext({viewport:{width,height:900}});
      const events=[];
      await context.route('**/*',r=>new URL(r.request().url()).hostname===new URL(baseUrl).hostname ? r.continue() : r.abort());
      await context.route('**/api/session',r=>r.fulfill({json:{session_id:'qa_acquisition_entry_session'}}));
      await context.route('**/api/analytics/events',r=>{events.push(r.request().postDataJSON());return r.fulfill({json:{ok:true}});});
      await context.route('**/api/merchant-offers/**',r=>r.fulfill({json:{offers:[],best_offer_id:null}}));
      await context.route('**/api/clickout/**',()=>{throw new Error('No affiliate requests allowed');});
      const page=await context.newPage();
      try {
        await page.goto(`${baseUrl}/start?qa=1&${sample.query}`,{waitUntil:'networkidle',referer:sample.referrer});
        const link=page.locator('a').filter({hasText:'Yves Saint Laurent Libre'}).first();
        await link.waitFor();
        const href=new URL(await link.getAttribute('href'),baseUrl);
        assert.equal(href.searchParams.get('src'),sample.source);
        assert.equal(href.searchParams.get('cmp'),sample.campaign||null);
        assert.equal(href.searchParams.get('content'),sample.content||null);
        // Attribution must survive document navigation even without browser storage.
        await context.addInitScript(()=>{Object.defineProperty(window,'sessionStorage',{get(){throw new Error('blocked')}});});
        await link.click();
        await page.waitForURL('**/duft/yves-saint-laurent-libre**');
        await page.waitForLoadState('networkidle');
        const captured=events.filter(e=>e.event==='page_view');
        assert.ok(captured.length>=2);
        for(const e of captured){assert.equal(e.acquisition_source,sample.source);assert.equal(e.campaign_id,sample.campaign);assert.equal(e.content_id,sample.content);assert.equal(e.internal_qa,true);}
        assert.ok(!JSON.stringify(events).includes('q=private'),'raw referrer must not enter analytics');
        assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth),false);
        results.push({width,source:sample.source,campaign:sample.campaign||null,qa_only:true});
      } finally {await context.close();}
    }
  }
  return results;
}
