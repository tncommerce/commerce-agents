import assert from 'node:assert/strict';
import { writeFile } from 'node:fs/promises';

// CI-only, localhost/static export. Every API response is a fixture: no live sessions,
// no merchant navigation, no analytics delivery, no advisor/model calls.
export async function verifyWowExperience(browser, baseUrl, outputDir) {
  const results = [];
  const routes = [['home','/'],['catalog','/duft'],['brands','/marken'],['rabanne','/duft/rabanne-1-million'],['lancome','/duft/la-vie-est-belle']];
  for (const width of [320,390,768,1024,1440]) {
    const context = await browser.newContext({viewport:{width,height:width < 640 ? 844 : 1000},hasTouch:width<1024,reducedMotion:'reduce'});
    await context.route('**/api/**', r => {
      const path = new URL(r.request().url()).pathname;
      if(path.endsWith('/session')) return r.fulfill({json:{session_id:'wow22-isolated-session',name:'QA'}});
      if(path.endsWith('/products')) return r.fulfill({json:{products:[]}});
      if(path.endsWith('/merchant-partners')) return r.fulfill({json:{partners:[]}});
      if(path.endsWith('/analytics/events')) return r.fulfill({json:{ok:true}});
      return r.fulfill({status:503,json:{detail:'Isolated offer-unavailable fixture'}});
    });
    await context.addInitScript(() => {
      window.__wowPerf={cls:0,lcp:0};
      new PerformanceObserver(list=>{for(const e of list.getEntries()) if(!e.hadRecentInput) window.__wowPerf.cls+=e.value;}).observe({type:'layout-shift',buffered:true});
      new PerformanceObserver(list=>{for(const e of list.getEntries()) window.__wowPerf.lcp=e.startTime;}).observe({type:'largest-contentful-paint',buffered:true});
    });
    const page = await context.newPage();
    const errors=[];page.on('pageerror',e=>errors.push(e.message));
    try {
      for (const [name,route] of routes) {
        await page.goto(baseUrl+route+'?src=instagram&cmp=wow22_fixture&content=isolated',{waitUntil:'networkidle'});
        await page.locator('h1').first().waitFor();
        await page.screenshot({path:`${outputDir}/wow22-${name}-${width}-first.png`});
        const metrics = await page.evaluate(() => ({...window.__wowPerf,overflow:Math.max(document.documentElement.scrollWidth-innerWidth,...[...document.querySelectorAll('.panel-scroll')].map(el=>el.scrollWidth-el.clientWidth)),dom:performance.getEntriesByType('navigation')[0].domContentLoadedEventEnd,resources:performance.getEntriesByType('resource').reduce((n,r)=>n+(r.transferSize||0),0)}));
        assert.ok(metrics.overflow <= 1,`${name}/${width}: horizontal overflow ${metrics.overflow}`);
        assert.ok(metrics.cls < .1,`${name}/${width}: CLS ${metrics.cls}`);
        if(name==='home') {
          const search=await page.locator('.wow-search').boundingBox();
          assert.ok(search && search.y+search.height<740,`home/${width}: search above fold`);
          await page.locator('.wow-hero-art').click();
          const atlas=page.locator('[data-scent-atlas]');
          await atlas.locator('select').selectOption('2');
          await atlas.getByText('Eau de Toilette · 100 ml',{exact:true}).waitFor();
          const notes=atlas.locator('.wow-atlas-notes button');
          assert.deepEqual(await notes.allTextContents(), ['Minze','Mandarine','Rose','Zimt','Amber','Leder'], 'Rabanne uses documented key notes, never an invented pyramid');
          await notes.first().focus();await page.keyboard.press('Enter');
          assert.equal(await notes.first().getAttribute('aria-pressed'),'true');
          await atlas.locator('[data-atlas-matches] small').waitFor();
          if(width<1024) await notes.last().tap();else await notes.last().click();
          assert.equal(await notes.last().getAttribute('aria-pressed'),'true');
          const matches=atlas.locator('[data-atlas-matches] a');
          for(const link of await matches.all()) assert.equal(new URL(await link.getAttribute('href'),baseUrl).searchParams.get('cmp'),'wow22_fixture');
          const transition=await atlas.locator('svg').evaluate(el=>getComputedStyle(el).transitionDuration);
          assert.equal(transition,'0s','reduced motion removes atlas transitions');
          await atlas.scrollIntoViewIfNeeded();
          await page.screenshot({path:`${outputDir}/wow22-atlas-${width}-interaction.png`});
          for(const [part,selector] of [['selection','.wow-selection'],['audiences','.wow-audiences'],['footer','.wow-home footer']]) {
            const el=page.locator(selector).first();if(await el.count()){
              await el.scrollIntoViewIfNeeded();
              await el.locator('img').evaluateAll(images=>Promise.all(images.map(async image=>{image.loading='eager';await Promise.race([image.decode().catch(()=>{}),new Promise(r=>setTimeout(r,8000))]);})));
              const broken=await el.locator('img').evaluateAll(images=>images.filter(i=>!i.complete||i.naturalWidth===0).map(i=>i.src));
              assert.deepEqual(broken,[],`${part}/${width}: selected originals must decode`);
              await page.screenshot({path:`${outputDir}/wow22-home-${width}-${part}.png`});
            }
          }
          const scroll=page.locator('.panel-scroll').filter({has:page.locator('.wow-home')});
          if(await scroll.count()) await scroll.evaluate(el=>{el.scrollTop=0;});
          metrics.searchBottom=search.y+search.height;
          metrics.keyboard=true;metrics.touch=width<1024;metrics.reducedMotion=true;
        } else {
          await page.evaluate(async()=>{for(let y=0;y<document.documentElement.scrollHeight;y+=600){window.scrollTo(0,y);await new Promise(r=>setTimeout(r,25));}window.scrollTo(0,0);});
          await page.evaluate(()=>Promise.all([...document.images].map(i=>i.decode().catch(()=>{}))));
          await page.screenshot({path:`${outputDir}/wow22-${name}-${width}-full.png`,fullPage:true});
        }
        results.push({name,width,...metrics});
      }
      assert.deepEqual(errors,[],'no browser runtime errors');
    } finally {await context.close();await writeFile(`${outputDir}/wow22-metrics.json`,JSON.stringify(results,null,2));}
  }
  const context=await browser.newContext({viewport:{width:390,height:844},reducedMotion:'no-preference'});
  try {
    await context.route('**/api/**',r=>r.fulfill({json:{session_id:'wow22-motion-fixture',products:[],partners:[],ok:true}}));
    const p=await context.newPage();await p.goto(baseUrl,{waitUntil:'networkidle'});
    const atlas=p.locator('[data-scent-atlas]');
    assert.notEqual(await atlas.locator('svg').evaluate(el=>getComputedStyle(el).transitionDuration),'0s');
    await atlas.locator('select').selectOption('1');
    await atlas.locator('.wow-atlas-notes button').first().click();
    await p.screenshot({path:`${outputDir}/wow22-atlas-390-motion.png`});
    results.push({normalMotion:true});
  } finally {await context.close();}
  await writeFile(`${outputDir}/wow22-metrics.json`,JSON.stringify(results,null,2));
  return results;
}
