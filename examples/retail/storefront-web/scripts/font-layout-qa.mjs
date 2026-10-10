import assert from 'node:assert/strict';

export async function verifyFontLayout(browser, baseUrl) {
  const results=[];
  for (const width of [390,1440]) {
    const context=await browser.newContext({viewport:{width,height:900}});
    let fontRequests=0;
    await context.route('**/*',r=>new URL(r.request().url()).hostname===new URL(baseUrl).hostname ? r.continue() : r.abort());
    await context.route('**/api/session',r=>r.fulfill({json:{session_id:'qa_font_layout_session'}}));
    await context.route('**/api/analytics/events',r=>r.fulfill({json:{ok:true}}));
    await context.route('**/*.woff2',async r=>{fontRequests++;await new Promise(resolve=>setTimeout(resolve,1500));return r.continue();});
    await context.addInitScript(()=>{
      window.__dufyndLayoutShifts=[];
      new PerformanceObserver(list=>{for(const entry of list.getEntries())if(!entry.hadRecentInput)window.__dufyndLayoutShifts.push(entry.value);}).observe({type:'layout-shift',buffered:true});
    });
    const page=await context.newPage();
    try {
      await page.goto(`${baseUrl}/start?qa=1`,{waitUntil:'networkidle'});
      assert.ok(fontRequests>0,'cold font request must be delayed');
      const cls=await page.evaluate(()=>window.__dufyndLayoutShifts.reduce((sum,value)=>sum+value,0));
      assert.ok(cls<0.01,`late font must not move the entry controls: CLS ${cls}`);
      assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth),false);
      await page.getByLabel('Duft oder Marke suchen',{exact:true}).fill('YSL Libre');
      await page.locator('[data-dufynd-social-live-results]').getByRole('link').first().waitFor();
      results.push({width,cls,fontRequests,search_operable:true});
    } finally {await context.close();}
  }
  return results;
}
