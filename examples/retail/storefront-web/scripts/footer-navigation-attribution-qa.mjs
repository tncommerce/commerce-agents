import assert from 'node:assert/strict';

export async function verifyFooterNavigationAttribution(browser, baseUrl) {
  let cases = 0;
  const targets = ['impressum','datenschutz','transparenz','bildnachweise','duftfinder','parfum-alternativen','sammlung','merkliste'];
  for(const width of [390,1440]) {
    for(const denied of [false,true]) {
      for(const target of targets) {
        const context=await browser.newContext({viewport:{width,height:900},reducedMotion:'reduce'});
        const page=await context.newPage(),events=[];
        try {
          if(denied)await context.addInitScript(()=>{
            const get=Storage.prototype.getItem,set=Storage.prototype.setItem;
            Storage.prototype.getItem=function(k){if(k==='dufynd_acquisition_attribution_v1')throw new DOMException('Denied','SecurityError');return get.call(this,k)};
            Storage.prototype.setItem=function(k,v){if(k==='dufynd_acquisition_attribution_v1')throw new DOMException('Denied','SecurityError');return set.call(this,k,v)};
          });
          await page.route('**/api/session',r=>r.fulfill({json:{session_id:'qa-footer-navigation',name:'QA'}}));
          await page.route('**/api/products?**',r=>r.fulfill({json:{products:[]}}));
          await page.route('**/api/merchant-partners',r=>r.fulfill({json:{partners:[]}}));
          await page.route('**/api/analytics/events',r=>{events.push(r.request().postDataJSON());return r.fulfill({json:{ok:true}})});
          await page.goto(`${baseUrl}/merkliste?src=newsletter&cmp=footer_qa&content=cta_1`);
          for(let n=0;n<100&&!events.some(e=>e.event==='page_view');n++)await page.waitForTimeout(50);
          await page.locator(`footer a[href*='/${target}']`).click();
          await page.waitForURL(u=>u.pathname===`/${target}`);
          const assertAttribution=()=>{
            const url=new URL(page.url());
            assert.equal(url.searchParams.get('src'),'newsletter',`${target}/${width}/${denied}: source must survive`);
            assert.equal(url.searchParams.get('cmp'),'footer_qa');
            assert.equal(url.searchParams.get('content'),'cta_1');
          };
          assertAttribution();
          if(targets.indexOf(target)<4) {
            assert.equal(events.filter(e=>e.event==='page_view').length,1,'informational pages must not gain a page view');
            const back=page.getByRole('link',{name:'← Zurück zu DUFYND',exact:true});
            await back.waitFor();
            await page.waitForFunction(()=>[...document.querySelectorAll('a')].some(a=>a.textContent?.trim()==='← Zurück zu DUFYND'&&new URL(a.href).searchParams.get('cmp')==='footer_qa'));
            await back.click();await page.waitForURL(u=>u.pathname==='/');assertAttribution();
          }
          for(let n=0;n<100&&events.filter(e=>e.event==='page_view').length<2;n++)await page.waitForTimeout(50);
          const views=events.filter(e=>e.event==='page_view');
          assert.equal(views.length,2,'existing destination page-view count must be preserved');
          for(const event of views){assert.equal(event.acquisition_source,'newsletter');assert.equal(event.campaign_id,'footer_qa');assert.equal(event.content_id,'cta_1')}
          cases++;
        } finally {await context.close()}
      }
    }
  }
  for(const width of [390,1440]) {
    for(const query of ['src=unsupported&cmp=untrusted','src=newsletter&cmp=%3Cunsafe%3E']) {
      const context=await browser.newContext({viewport:{width,height:900}}),page=await context.newPage();
      try {
        await page.route('**/api/session',r=>r.fulfill({json:{session_id:'qa-footer-invalid',name:'QA'}}));
        await page.route('**/api/analytics/events',r=>r.fulfill({json:{ok:true}}));
        await page.goto(`${baseUrl}/merkliste?${query}`);
        await page.getByRole('link',{name:'← Zurück zu DUFYND',exact:true}).waitFor();
        await page.locator("footer a[href*='/duftfinder']").click();
        await page.waitForURL(u=>u.pathname==='/duftfinder');
        const url=new URL(page.url());
        assert.equal(url.searchParams.get('cmp'),null,'untrusted campaign must not propagate');
        assert.equal(url.searchParams.get('src'),query.startsWith('src=unsupported')?'unknown':'newsletter');
        cases++;
      } finally {await context.close()}
    }
  }
  return cases;
}
