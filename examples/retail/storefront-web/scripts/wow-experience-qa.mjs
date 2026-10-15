import { chooseMeasurement } from "./measurement-choice-qa.mjs";
import assert from 'node:assert/strict';
import { writeFile } from 'node:fs/promises';

// CI-only, localhost/static export. Every API response is a fixture: no live sessions,
// no merchant navigation, no analytics delivery, no advisor/model calls.
// Page load + explicit DOM, client interaction and offer-state assertions are our
// readiness gates. Playwright networkidle is not: background requests can keep a
// fully interactive page busy and cause a false 30-second navigation failure.
export async function verifyWowExperience(browser, baseUrl, outputDir) {
  const results = [];
  const routes = [['home','/'],['catalog','/duft'],['brands','/marken'],['rabanne','/duft/rabanne-1-million'],['lancome','/duft/lancome-la-vie-est-belle']];
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
        const response=await page.goto(baseUrl+route+'?src=instagram&cmp=wow22_fixture&content=isolated',{waitUntil:'load'});
        await chooseMeasurement(page, 'granted');
        assert.equal(response?.status(),200,`${name}/${width}: exact public route must return 200`);
        await page.locator('h1').first().waitFor({state:'visible'});
        if (name === 'home') {
          await page.locator('.wow-search input').waitFor({state:'visible'});
          await page.locator('[data-scent-atlas] select').waitFor({state:'visible'});
        }
        if(name==='lancome') {
          assert.match(await page.locator('h1').innerText(),/La Vie est Belle/);
          const original=page.locator('.dufynd-fragrance-stage-shell img');
          await original.first().waitFor();
          await original.first().evaluate(image=>image.decode());
          assert.ok(await original.first().evaluate(image=>image.naturalWidth>0),'exact Lancôme original must decode');
        }
        await page.screenshot({path:`${outputDir}/wow22-${name}-${width}-first.png`});
        const metrics = await page.evaluate(() => ({...window.__wowPerf,overflow:Math.max(document.documentElement.scrollWidth-innerWidth,...[...document.querySelectorAll('.panel-scroll')].map(el=>el.scrollWidth-el.clientWidth)),dom:performance.getEntriesByType('navigation')[0].domContentLoadedEventEnd,resources:performance.getEntriesByType('resource').reduce((n,r)=>n+(r.transferSize||0),0)}));
        assert.ok(metrics.overflow <= 1,`${name}/${width}: horizontal overflow ${metrics.overflow}`);
        assert.ok(metrics.cls < .1,`${name}/${width}: CLS ${metrics.cls}`);
        if(name==='home') {
          const search=await page.locator('.wow-search').boundingBox();
          assert.ok(search && search.y+search.height<740,`home/${width}: search above fold`);
          await page.locator('.wow-hero-art').click();
          const atlas=page.locator('[data-scent-atlas]');
          // Long source labels must remain readable after the note-label composition changed.
          await atlas.locator('select').selectOption('1');
          const labelChoices=atlas.locator('.wow-atlas-notes button');
          const labels=await labelChoices.allTextContents();
          const longest=labels.reduce((a,b)=>b.length>a.length?b:a,'');
          await labelChoices.filter({hasText:longest}).first().click();
          const noteBounds=await atlas.locator('.wow-atlas-core').boundingBox();
          assert.ok(noteBounds.x>=0&&noteBounds.x+noteBounds.width<=width,'long selected note stays inside the viewport');
          await atlas.screenshot({path:`${outputDir}/polish23-atlas-${width}-long-note.png`});
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
          assert.ok(await matches.count() > 0, 'leather must match released profiles despite source capitalisation');
          assert.ok(await matches.filter({hasText:'Explorer'}).count(), 'documented Explorer leather note must be discoverable');
          for(const link of await matches.all()) {
            await link.focus(); // Existing link contract refreshes attribution on native focus/pointerdown.
            assert.equal(new URL(await link.getAttribute('href'),baseUrl).searchParams.get('cmp'),'wow22_fixture');
          }
          const transition=await atlas.locator('svg').evaluate(el=>getComputedStyle(el).transitionDuration);
          assert.equal(transition,'0s','reduced motion removes atlas transitions');
          await atlas.scrollIntoViewIfNeeded();
          await page.screenshot({path:`${outputDir}/wow22-atlas-${width}-interaction.png`});
          await atlas.screenshot({path:`${outputDir}/polish23-atlas-${width}-complete.png`});
          const editorialCards=page.locator('a[data-dufynd-original-card]');
          assert.equal(await editorialCards.count(),2,'one curated original selection, without repeated product rows');
          if(width<=390){
            const firstCard=await editorialCards.nth(0).boundingBox();
            const secondCard=await editorialCards.nth(1).boundingBox();
            const firstPhoto=await editorialCards.nth(0).locator('.wow-selection-photo').boundingBox();
            assert.ok(firstCard&&secondCard&&firstPhoto&&secondCard.y>firstCard.y+firstCard.height,
              'licensed mobile editorial cards are individually readable in a vertical journey');
            assert.ok(firstPhoto.width>=105,'mobile source photo remains prominent, not a tiny thumbnail');
            assert.ok(firstCard.x>=0&&firstCard.x+firstCard.width<=width,
              'mobile original-photo entry fits the viewport');
          }
          assert.equal(await page.locator('.wow-advisor textarea').count(),1,'existing advisor composer is inline on the homepage');
          assert.equal(await page.locator('textarea').count(),1,'no second fixed composer overlaps homepage content');
          const advisor=page.locator('.wow-advisor textarea');await advisor.fill('Isolierte Eingabe ohne Versand');
          assert.equal(await advisor.inputValue(),'Isolierte Eingabe ohne Versand');await advisor.fill('');await advisor.blur();
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
          if(await scroll.count()) {
            await page.locator('.wow-home img').evaluateAll(images=>Promise.all(images.map(async image=>{image.loading='eager';await Promise.race([image.decode().catch(()=>{}),new Promise(r=>setTimeout(r,8000))]);})));
            const extent=await scroll.evaluate(el=>({height:el.scrollHeight,viewport:el.clientHeight}));
            let frame=0;
            const end=Math.max(0,extent.height-extent.viewport);
            for(let y=0;;y=Math.min(end,y+Math.max(250,Math.floor(extent.viewport*.8)))) {
              await scroll.evaluate((el,y)=>{el.scrollTop=y;},y);
              await page.waitForTimeout(80);
              await page.screenshot({path:`${outputDir}/wow22-home-${width}-scroll-${String(frame++).padStart(2,'0')}.png`});
              if(y===end) break;
            }
            metrics.scrollFrames=frame;metrics.scrollHeight=extent.height;
            if(width===390) {metrics.baselineScrollHeight=5841;metrics.scrollReduction=1-extent.height/5841;assert.ok(extent.height<=3800,'390px homepage must be substantially shorter than WOW22');}
            if(width===320) assert.ok(extent.height<=4200,'320px retains a compact complete scroll journey');
            await scroll.evaluate(el=>{el.scrollTop=0;});
          }
          metrics.searchBottom=search.y+search.height;
          metrics.keyboard=true;metrics.touch=width<1024;metrics.reducedMotion=true;
          const destination=new URL(await matches.first().getAttribute('href'),baseUrl).pathname;
          await matches.first().focus();await page.keyboard.press('Enter');
          await page.waitForURL(url=>url.pathname===destination);
          assert.equal(new URL(page.url()).searchParams.get('cmp'),'wow22_fixture','actual atlas keyboard navigation preserves campaign');
          assert.equal(new URL(page.url()).searchParams.get('src'),'instagram');
          metrics.atlasDestination=destination;
          // Exercise the relocated existing composer with an empty isolated SSE response.
          // No production session, model request, clickout or analytics delivery is made.
          const messages=[];
          await page.route('**/api/chat',r=>{messages.push(r.request().postDataJSON().message);return r.fulfill({status:200,contentType:'text/event-stream',body:''});});
          await page.goto(baseUrl+'/?src=instagram&cmp=wow22_fixture&content=isolated',{waitUntil:'load'});
          await chooseMeasurement(page, 'granted');
          const inline=page.locator('.wow-advisor textarea');
          await inline.fill('QA: Ein Duft für den Alltag');await inline.press('Enter');
          await page.getByText('QA: Ein Duft für den Alltag',{exact:true}).waitFor();
          await page.waitForFunction(()=>!document.querySelector('.wow-home')&&document.querySelectorAll('textarea').length===1);
          assert.deepEqual(messages,['QA: Ein Duft für den Alltag'],'inline composer sends exactly one mocked request');
          const dock=page.getByRole('textbox',{name:'Nachricht an DUFYND Advisor'});
          assert.equal(await dock.evaluate(el=>document.activeElement===el),true,'typing focus follows the inline field into the conversation dock');
          await dock.fill('QA: zweite Nachricht');
          await page.getByRole('button',{name:'Send',exact:true}).click();
          await page.getByText('QA: zweite Nachricht',{exact:true}).waitFor();
          assert.deepEqual(messages,['QA: Ein Duft für den Alltag','QA: zweite Nachricht'],'conversation keeps the existing dock usable');
          assert.equal(new URL(page.url()).searchParams.get('cmp'),'wow22_fixture');
          await page.screenshot({path:`${outputDir}/polish23-advisor-${width}-FIXTURE.png`});
          metrics.advisor={inlineToConversation:true,requests:messages.length,mocked:true};
        } else {
          await page.evaluate(async()=>{for(let y=0;y<document.documentElement.scrollHeight;y+=600){window.scrollTo(0,y);await new Promise(r=>setTimeout(r,25));}window.scrollTo(0,0);});
          await page.evaluate(()=>Promise.all([...document.images].map(i=>i.decode().catch(()=>{}))));
          await page.screenshot({path:`${outputDir}/wow22-${name}-${width}-full.png`,fullPage:true});
        }
        if(name==='rabanne') {
          const heldNotes=page.locator('[data-dufynd-source-honest-notes="rabanne-edt-100"]');
          assert.equal(await heldNotes.count(),1,'Rabanne EDT 100ml has a source-honest editorial note identity during photo hold');
          assert.equal(await heldNotes.locator('img').count(),0,'Rabanne source-hold identity is not fake original photography');
          assert.deepEqual(await heldNotes.locator('li').allTextContents(),
            ['Minze','Mandarine','Rose','Zimt','Amber','Leder'],
            'Rabanne editorial notes match exact documented variant, never invented bottle or concentration claims');
          assert.match(await heldNotes.innerText(),/Originalfoto in Prüfung/);
          const summary=heldNotes.locator('summary');
          const heldBounds=await heldNotes.boundingBox();
          assert.ok(heldBounds&&heldBounds.x>=0&&heldBounds.x+heldBounds.width<=width
            &&heldBounds.height>=44&&heldBounds.height<=64,
            'Collapsed honest Rabanne note teaser preserves compact first-money landing');
          assert.equal(await heldNotes.locator('li').first().isVisible(),false,
            'Additional editorial content does not displace the initial offers CTA');
          await summary.focus();await page.keyboard.press('Enter');
          await heldNotes.locator('li').first().waitFor({state:'visible'});
          const expandedBounds=await heldNotes.boundingBox();
          assert.ok(expandedBounds&&expandedBounds.height>=160,
            'Expanded note study stays genuinely readable on demand');
          await summary.click();
          assert.equal(await heldNotes.locator('li').first().isVisible(),false,
            'Closing note study restores compact purchase journey');
          const offer={offer_id:'wow22-mock-offer',product_id:'SC-RABANNE-1-MILLION-EDT-100',merchant_id:'qa-only',merchant_name:'QA-Testhändler',price:90,currency:'EUR',shipping_cost:5,total_price:95,shipping_label:'5,00 € Versand (QA)',in_stock:true,variant_label:'100 ml · Eau de Toilette',affiliate_link:true,clickout_path:'/api/clickout/wow22-mock-offer',last_updated_at:'2026-10-14T00:00:00Z'};
          let available=true;
          await page.route('**/api/merchant-offers/SC-RABANNE-1-MILLION-EDT-100',r=>r.fulfill({json:{product_id:offer.product_id,best_offer_id:available?offer.offer_id:null,offers:available?[offer]:[],affiliate_disclosure:'Isolated QA fixture'}}));
          await page.reload({waitUntil:'load'});
          const merchant=page.getByRole('link',{name:'Bei QA-Testhändler ansehen',exact:true});
          await merchant.waitFor();
          assert.match(await page.locator('[data-merchant-offers]').innerText(),/Gesamtpreis inkl. Versand/);
          assert.equal(new URL(await merchant.getAttribute('href'),baseUrl).searchParams.get('cmp'),'wow22_fixture');
          assert.ok((await merchant.boundingBox()).height>=44);
          assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth),false,'available offer fits viewport');
          await page.screenshot({path:`${outputDir}/wow22-rabanne-${width}-available-FIXTURE.png`,fullPage:true});
          available=false;await page.reload({waitUntil:'load'});
          await page.locator('[data-offer-state="empty"]').waitFor({state:'visible'});
          assert.equal(await page.locator('a[href*="/api/clickout/"]').count(),0,'empty state has no purchase clickout');
          assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth),false,'empty offer fits viewport');
          await page.screenshot({path:`${outputDir}/wow22-rabanne-${width}-empty-FIXTURE.png`,fullPage:true});
          metrics.offerStates=['error','available','empty'];
        }
        results.push({name,width,...metrics});
      }
      assert.deepEqual(errors,[],'no browser runtime errors');
    } finally {await context.close();await writeFile(`${outputDir}/wow22-metrics.json`,JSON.stringify(results,null,2));}
  }
  const context=await browser.newContext({viewport:{width:390,height:844},reducedMotion:'no-preference'});
  try {
    await context.route('**/api/**',r=>r.fulfill({json:{session_id:'wow22-motion-fixture',products:[],partners:[],ok:true}}));
    const p=await context.newPage();await p.goto(baseUrl,{waitUntil:'load'});await chooseMeasurement(p,'denied');
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
