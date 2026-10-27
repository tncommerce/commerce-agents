import assert from 'node:assert/strict';
import { mkdir, readFile, writeFile } from 'node:fs/promises';
import { createHash } from 'node:crypto';
import path from 'node:path';
import { chooseMeasurement } from './measurement-choice-qa.mjs';
import { emptyOfferFixture } from './merchant-offer-fixture-qa.mjs';

// Existing public profiles only. All external requests are blocked; API offer
// replies are explicitly synthetic empty QA fixtures, never real buy options.
const products = [
  {id:'SC-YSL-BLACK-OPIUM-EDP-90',name:'Black Opium',slug:'yves-saint-laurent-black-opium',query:'BlackOpium EDP 90 ml',normal:'Black Opium EDP 90 ml',volume:90},
  {id:'SC-ESSENTIAL-PARFUMS-BOIS-IMPERIAL-100',name:'Bois Impérial',slug:'essential-parfums-bois-imperial',query:'BoisImperial EDP 100 ml',normal:'Bois Impérial EDP 100 ml',volume:100},
  {id:'SC-LANCOME-LA-VIE-EST-BELLE-EDP-100',name:'La Vie est Belle',slug:'lancome-la-vie-est-belle',query:'LaVieEstBelle EDP 100 ml',normal:'La Vie Est Belle EDP 100 ml',volume:100},
];

export async function verifyCompactFragranceSearch(browser, baseUrl, outputDir) {
  assert.ok(['127.0.0.1','localhost','[::1]'].includes(new URL(baseUrl).hostname));
  const cases = [], observations = [], screenshots = [];
  if(outputDir) await mkdir(outputDir,{recursive:true});
  for(const width of [320,390,768,1440]) {
    const context=await browser.newContext({viewport:{width,height:900},hasTouch:width<768,reducedMotion:'reduce',serviceWorkers:'block'});
    const forbidden=[], functionalSessions=[], errors=[];
    await context.route('**/*',route=>{
      const url=new URL(route.request().url());
      if(/\/api\/(analytics|clickout)/.test(url.pathname)) forbidden.push(url.pathname);
      // The home advisor initializes its functional session independently of
      // analytics consent. Keep that existing request isolated as well.
      if(url.pathname==='/api/session') {
        functionalSessions.push(url.pathname);
        return route.fulfill({json:{session_id:'synthetic-compact-search-session'}});
      }
      if(url.pathname.startsWith('/api/merchant-offers/')) return route.fulfill({json:emptyOfferFixture(route)});
      if(url.origin===new URL(baseUrl).origin) return route.continue();
      return route.abort();
    });
    const page=await context.newPage();
    page.on('pageerror',e=>errors.push(String(e)));
    const search=page.getByRole('searchbox',{name:'Duft, Marke oder Profil'});
    const cards=page.locator('.dufynd-catalog-card');
    const capture=async name=>{
      if(!outputDir) return;
      const file=`compact-search-${width}-${name}.png`;
      await page.screenshot({path:path.join(outputDir,file)});
      screenshots.push({file,width,sha256:createHash('sha256').update(await readFile(path.join(outputDir,file))).digest('hex')});
    };
    const checkCard=async(product,query)=>{
      await page.waitForFunction(q=>document.querySelector('input[type="search"]')?.value===q,query);
      await cards.getByRole('heading',{name:product.name,exact:true}).waitFor();
      assert.equal(await cards.count(),1,query);
      assert.equal(await cards.getByLabel('Exakte Duftvariante',{exact:true}).getByText('Eau de Parfum',{exact:true}).count(),1);
      assert.equal(await cards.getByLabel('Exakte Duftvariante',{exact:true}).getByText(`${product.volume} ml`,{exact:true}).count(),1);
      assert.equal(new URL(await cards.locator('a.group').getAttribute('href'),baseUrl).pathname,`/duft/${product.slug}`);
      assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth),false);
      observations.push({width,route:'/duft',query,product_id:product.id,results:1});
    };
    try {
      await page.goto(`${baseUrl}/?qa=1`);
      await chooseMeasurement(page,'denied');
      await page.locator('#dufynd-home-search').fill(products[0].query);
      await page.getByRole('search',{name:'DUFYND Duftkatalog durchsuchen'}).getByRole('button',{name:'Suchen',exact:true}).click();
      await checkCard(products[0],products[0].query);
      for(const product of products) {
        await search.fill(product.normal);
        await checkCard(product,product.normal);
        await search.fill(product.query);
        await checkCard(product,product.query);
        if(product===products[0]) {
          await page.evaluate(()=>scrollTo(0,0));
          await capture('catalog');
        }
        await search.press('Enter');
        await page.waitForFunction(()=>document.activeElement?.id==='catalog-results');
        await capture(product.slug);
        await cards.locator('a.group').click();
        await page.getByRole('heading',{name:product.name,exact:true,level:1}).waitFor();
        const identity=page.getByLabel('Exakte Duftvariante',{exact:true});
        assert.match(await identity.innerText(),new RegExp(`Eau de Parfum[\\s\\S]*${product.volume} ml`));
        await page.locator('[data-offer-state="empty"]').waitFor();
        assert.equal(await page.locator('a[href*="/api/clickout/"]').count(),0);
        await page.getByRole('link',{name:'← Zurück zu deiner Auswahl',exact:true}).first().click();
        await page.waitForFunction(q=>document.querySelector('input[type="search"]')?.value===q,product.query);
        await checkCard(product,product.query);
      }

      // Keep a real filter and both exact selected variants across search,
      // comparison, its explicit return link, product navigation and native back.
      await search.fill(products[0].query);
      const filterToggle=page.locator('button[aria-controls="catalog-filter-panel"]');
      if(await filterToggle.isVisible() && await filterToggle.getAttribute('aria-expanded')==='false') {
        await filterToggle.click();
      }
      await page.getByRole('region',{name:'Duftkatalog filtern'}).getByRole('button',{name:'Damen',exact:true}).click();
      await checkCard(products[0],products[0].query);
      await cards.getByRole('button',{name:/für Vergleich auswählen/}).click();
      await search.fill(products[2].query);
      await checkCard(products[2],products[2].query);
      await cards.getByRole('button',{name:/für Vergleich auswählen/}).click();
      const tray=page.getByRole('complementary',{name:'Duftvergleich vorbereiten'});
      await tray.getByRole('link',{name:'Jetzt vergleichen →',exact:true}).click();
      await page.locator('.dufynd-comparison-live-stage').waitFor();
      assert.equal(await page.getByRole('combobox',{name:'Duft 1',exact:true}).inputValue(),products[0].id);
      assert.equal(await page.getByRole('combobox',{name:'Duft 2',exact:true}).inputValue(),products[2].id);
      await page.locator('.dufynd-comparison-picker').scrollIntoViewIfNeeded();
      await capture('comparison');
      await page.locator('header').getByRole('link',{name:'← Zurück zu deiner Auswahl',exact:true}).click();
      await page.waitForFunction(q=>document.querySelector('input[type="search"]')?.value===q,products[2].query);
      assert.equal(new URL(page.url()).searchParams.get('zielgruppe'),'women');
      assert.deepEqual(new URL(page.url()).searchParams.get('compare').split(','),[products[0].id,products[2].id]);
      await cards.locator('a.group').click();
      await page.getByRole('heading',{name:products[2].name,exact:true,level:1}).waitFor();
      await page.goBack();
      await search.waitFor();
      await page.waitForFunction(q=>document.querySelector('input[type="search"]')?.value===q,products[2].query);
      assert.equal(new URL(page.url()).searchParams.get('zielgruppe'),'women');
      assert.deepEqual(new URL(page.url()).searchParams.get('compare').split(','),[products[0].id,products[2].id]);

      await page.goto(`${baseUrl}/start?qa=1`);
      const social=page.getByLabel('Duft oder Marke suchen',{exact:true});
      const results=page.locator('[data-dufynd-social-live-results]');
      for(const product of products) {
        for(const query of [product.normal,product.query,product.query.toUpperCase()]) {
          await social.fill(query);
          await results.getByRole('link').filter({hasText:product.name}).waitFor();
          assert.equal(await results.getByRole('link').count(),1);
          assert.equal(new URL(await results.getByRole('link').getAttribute('href'),baseUrl).pathname,`/duft/${product.slug}`);
          observations.push({width,route:'/start',query,product_id:product.id,results:1});
        }
        await social.fill(product.query);
        if(product===products[0]) {await social.scrollIntoViewIfNeeded();await capture('social');}
        await social.press('Enter');
        await page.getByRole('heading',{name:product.name,exact:true,level:1}).waitFor();
        await page.goBack();
        await social.waitFor();
      }
      if(width===390) {
        const negatives=[...products.flatMap(p=>[p.query.replace(/\d+ ml/,'50 ml'),p.query.replace('EDP','EDT'),`${p.query} Intense`,`${p.query} Elixir`,`${p.query} Le Parfum`,`${p.query} Refill`,p.query.replace(' EDP','Intense EDP'),p.query.replaceAll(' ','')]),'BlackOpiumEDP50ml','UnknownFragranceXYZ','BurberryGoddess','PradaParadoxe','GoodGirl','CocoMademoiselle','MonGuerlain','Widian London'];
        for(const query of negatives) {
          await page.goto(`${baseUrl}/duft?q=${encodeURIComponent(query)}`);
          await page.getByRole('heading',{name:'Keine passenden Düfte gefunden',exact:true}).waitFor();
          assert.equal(await cards.count(),0,query);
          await page.goto(`${baseUrl}/start`);
          await social.fill(query);
          await page.getByRole('button',{name:'Direkt suchen',exact:true}).waitFor();
          assert.equal(await results.getByRole('link').count(),0,query);
        }
        observations.push({width,negative_queries:negatives.length,surfaces:2,results:0});
      }
      assert.deepEqual(forbidden,[],'No analytics or merchant clickout requests');
      assert.deepEqual(errors,[]);
      cases.push({suite:'compact-public-name',width,public_products:products.map(p=>p.id),home:true,catalog:true,social:true,comparison:true,filter_and_selection_restored:true,empty_offers:true,synthetic_functional_sessions:functionalSessions.length,analytics_requests:0,merchant_clickouts:0});
    } finally {await context.close();}
  }
  if(outputDir) {
    const event=process.env.GITHUB_EVENT_PATH?JSON.parse(await readFile(process.env.GITHUB_EVENT_PATH,'utf8')):null;
    const sources=[];
    for(const file of ['../lib/fragranceSearchIdentity.ts','../components/FragranceCatalogBrowser.tsx','../components/SocialFragranceSearch.tsx','compact-fragrance-search-qa.mjs','../lib/generated/public-fragrances.json','../lib/generated/public-catalog.json']) {
      sources.push({file,sha256:createHash('sha256').update(await readFile(new URL(file,import.meta.url))).digest('hex')});
    }
    await writeFile(path.join(outputDir,'compact-search-evidence.json'),JSON.stringify({feature_sha:event?.pull_request?.head?.sha||process.env.QA_SOURCE_SHA||null,checkout_sha:process.env.GITHUB_SHA||process.env.QA_SOURCE_SHA||null,run_id:process.env.GITHUB_RUN_ID||null,data:'Unchanged public catalog; external requests blocked; synthetic empty offers only',sources,observations,screenshots,cases},null,2)+'\n');
  }
  return cases;
}
