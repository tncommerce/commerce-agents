import assert from 'node:assert/strict';
import {chromium} from 'playwright';
import {readFileSync,mkdirSync,writeFileSync,existsSync} from 'node:fs';
const base=process.env.QA_BASE_URL || 'http://127.0.0.1:3013';
const out=process.env.QA_OUTPUT || '/tmp/dufynd-release-qa';
mkdirSync(out,{recursive:true});
const pilots=JSON.parse(readFileSync(new URL('../../data/dufynd_release_pilots.json',import.meta.url),'utf8')).pilots;
const facts=JSON.parse(readFileSync(new URL('../../data/dufynd_discovery_qualification.json',import.meta.url),'utf8')).products;
const photos=JSON.parse(readFileSync(new URL('../lib/generated/original-photos.json',import.meta.url),'utf8'));
const report=[];
const browser=await chromium.launch({headless:true});
try {
for(const width of [320,390,768,1440]) {
 const page=await browser.newPage({viewport:{width,height:900},reducedMotion:'reduce'});
 const errors=[];page.on('pageerror',e=>errors.push(e.message));
 if(process.env.QA_IMAGE_MANIFEST&&existsSync(process.env.QA_IMAGE_MANIFEST)) for(const asset of JSON.parse(readFileSync(process.env.QA_IMAGE_MANIFEST,'utf8'))) await page.route(asset.url,r=>r.fulfill({path:asset.path}));
 await page.route('**/analytics/**',r=>r.fulfill({status:204}));
 await page.goto(`${base}/duft?bewertung=8&sort=rating`);await page.locator('.dufynd-catalog-card').first().waitFor();
 await page.waitForFunction(()=>!new URL(location.href).searchParams.has("bewertung"));
 assert.equal(await page.getByRole('combobox',{name:'Bewertung'}).count(),0);
 assert.ok(!new URL(page.url()).searchParams.has('bewertung'),'Old blocked rating filter removed');
 const cards=page.locator('.dufynd-catalog-card');assert.equal(await cards.count(),12);
 for(const card of await cards.all()) {
   const imgs=await card.locator('[data-dufynd-catalog-card-stage] img').evaluateAll(xs=>xs.map(x=>x.getAttribute('src')));
   assert.ok(imgs.every(src=>photos.some(p=>p.url===src)),'Only approved original product photos');
   assert.equal(await card.locator('[data-scent-artwork]').count()+Number(imgs.length>0),1,'Every card has a filled, honest visual');
 }
 assert.ok(!/\d[,.]\d\/10|\d+ Bewertungen/.test(await page.locator('main').innerText()));
 await page.locator('.dufynd-brand-directory summary').click();
 const buttons=page.locator('.dufynd-brand-directory button');let sum=0;const names=[];
 for(const button of await buttons.all()) {
  const n=Number(await button.locator('span').innerText());sum+=n;names.push((await button.innerText()).replace(/\s*\d+$/,''));
  if(width===1440){await button.click();await page.waitForTimeout(40);assert.equal(await cards.count(),Math.min(n,12));await button.click();}
 }
 assert.equal(sum,37);assert.equal(new Set(names.map(x=>x.toLowerCase())).size,names.length);
 await page.goto(base);await page.locator('#dufynd-home-search').waitFor();
 const searchBounds=await page.locator('#dufynd-home-search').boundingBox();assert.ok(searchBounds.y<400,'Mobile search visible early');
 if(width<768){await page.getByRole('button',{name:'Weitere Düfte',exact:true}).click();await page.waitForTimeout(400);assert.ok(await page.locator('#dufynd-original-strip').evaluate(x=>x.scrollLeft>0),'Swipe navigation works');}
 for(const p of pilots){
  const response=await page.goto(`${base}/review/duft/${p.slug}`);assert.equal(response.status(),200);
  assert.ok((await page.locator('meta[name=robots]').getAttribute('content')).includes('noindex'));
  assert.ok((await page.locator('h1').innerText()).includes(p.expected_variant.name.replace('REPLICA ','')));
  assert.equal(await page.locator('[data-scent-artwork]').count(),1);
  assert.equal(await page.locator('img').count(),0,'No invented bottle');
  assert.equal(await page.locator('a[href*="awin"],a[href*="clickout"]').count(),0);
  const schemas=await page.locator('script[type="application/ld+json"]').allTextContents();
  assert.ok(schemas.every(s=>!s.includes('aggregateRating')&&!s.includes('"offers"')),'No invented structured offers or ratings');
  const art=await page.locator('[data-scent-artwork]').boundingBox();
  if(width<768) assert.ok(art.y<470,'Scent visual appears before description on mobile');
  assert.equal(await page.locator('link[rel=canonical]').count(),0,'Private pages have no public canonical');
  assert.ok((await page.title()).includes(p.expected_variant.name));
  assert.equal(await page.locator('meta[name=description]').getAttribute('content'),p.seo.description);
  if([390,1440].includes(width)) {
    await page.screenshot({path:`${out}/${p.slug}-${width}-viewport.png`});
    await page.screenshot({path:`${out}/${p.slug}-${width}.png`,fullPage:true});
  }
  await page.getByRole('link',{name:'Die Komposition entdecken'}).click();
  assert.equal(new URL(page.url()).hash,'#duftverlauf');
  await page.locator('#quellen summary').click();
  assert.ok((await page.locator('#quellen').innerText()).includes(facts.find(f=>f.product_id===p.product_id).identity.kind==='gtin'?'Geprüfte GTIN':'Herstellerreferenz (keine GTIN)'));
  assert.equal(await page.locator('nav[aria-label="Review-Produktnavigation"] a').count(),2);
  const links=await page.locator('nav[aria-label="Review-Produktnavigation"] a').evaluateAll(xs=>xs.map(x=>x.getAttribute('href')));
  assert.ok(links.every(h=>pilots.some(p=>h===`/review/duft/${p.slug}`)),'Previous/next links are real wave routes');
  assert.ok(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth),'No horizontal overflow');
 }
 assert.deepEqual(errors,[]);report.push({width,status:'passed',review_pages:pilots.length,checks:['public_metrics','honest_catalog_visuals','brand_counts','mobile_search','swipe_controls','exact_review_pages','early_art','metadata','review_navigation','no_offers','noindex','no_overflow','no_page_errors']});await page.close();
}
}finally{await browser.close();}
writeFileSync(`${out}/report.json`,JSON.stringify(report,null,2));console.log(JSON.stringify(report));
