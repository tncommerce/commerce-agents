import assert from 'node:assert/strict';
import {photoIntegrationQa} from './photo-integration-qa.mjs';
import {publicCount} from './public-catalog-summary.mjs';
import {rendererDigest,renderDigest} from './release-gate.mjs';
import {chromium} from 'playwright';
import {readFileSync,mkdirSync,writeFileSync,existsSync} from 'node:fs';
const base=process.env.QA_BASE_URL || 'http://127.0.0.1:3013';
const out=process.env.QA_OUTPUT || '/tmp/dufynd-release-qa';
mkdirSync(out,{recursive:true});
const pilots=JSON.parse(readFileSync(new URL('../../data/dufynd_release_pilots.json',import.meta.url),'utf8')).pilots;
const facts=JSON.parse(readFileSync(new URL('../../data/dufynd_discovery_qualification.json',import.meta.url),'utf8')).products;
const photos=JSON.parse(readFileSync(new URL('../lib/generated/original-photos.json',import.meta.url),'utf8'));
const report=[];
const builtRenderer=JSON.parse(readFileSync(new URL('../lib/generated/review-build-fingerprint.json',import.meta.url),'utf8')).renderer_sha256;
assert.equal(rendererDigest(),builtRenderer,'Source changed after build: rebuild before certifying screenshots');
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
   const approved = (await card.getAttribute("data-original-photo")) === "true";
   const studioHold = card.locator(".dufynd-catalog-photo-pending");
   const approvedImageStage = card.locator("[data-dufynd-photo-state], [data-dufynd-visual-state='unavailable']");
   if (approved) {
     assert.equal(await studioHold.count(),0,"Approved photo cards must not pretend to need a license");
     assert.ok(await approvedImageStage.count() >= 1,"Registered source needs a real image stage or explicit failure");
   } else {
     assert.equal(imgs.length,0,"Unapproved rows must not render any product image");
     assert.equal(await studioHold.count(),1,"Every unapproved row needs an honest neutral studio visual");
     const caption = studioHold.locator(".dufynd-catalog-photo-pending-caption");
     assert.equal((await caption.textContent())?.trim(),"Originalfoto in Prüfung");
   }
 }
 assert.ok(!/\d[,.]\d\/10|\d+ Bewertungen/.test(await page.locator('main').innerText()));
 await page.locator('.dufynd-brand-directory summary').click();
 const buttons=page.locator('.dufynd-brand-directory button');let sum=0;const names=[];
 for(const button of await buttons.all()) {
  const n=Number(await button.locator('span').innerText());sum+=n;names.push((await button.innerText()).replace(/\s*\d+$/,''));
  if(width===1440){await button.click();await page.waitForTimeout(40);assert.equal(await cards.count(),Math.min(n,12));await button.click();}
 }
 assert.equal(sum,publicCount);assert.equal(new Set(names.map(x=>x.toLowerCase())).size,names.length);
 await page.goto(base);await page.locator('#dufynd-home-search').waitFor();
 const searchBounds=await page.locator('#dufynd-home-search').boundingBox();assert.ok(searchBounds.y<400,'Mobile search visible early');
 if(width<768){await page.getByRole('button',{name:'Weitere Düfte',exact:true}).click();await page.waitForTimeout(400);assert.ok(await page.locator('#dufynd-original-strip').evaluate(x=>x.scrollLeft>0),'Swipe navigation works');}
 for(const p of pilots){
  const response=await page.goto(`${base}/review/duft/${p.slug}`);assert.equal(response.status(),200);
  assert.ok((await page.locator('meta[name=robots]').getAttribute('content')).includes('noindex'));
  assert.ok((await page.locator('h1').innerText()).toLowerCase().includes(p.expected_variant.name.replace('REPLICA ','').toLowerCase()));
  assert.ok(await page.locator('h1').evaluate(el=>{
    const node=el.firstChild;const text=node.textContent;
    return [...text.matchAll(/\S+/g)].every(m=>{const r=document.createRange();r.setStart(node,m.index);r.setEnd(node,m.index+m[0].length);return r.getClientRects().length===1;});
  }),'Product name wraps between words, never isolated trailing letters');
  const studio = page.locator("[data-dufynd-studio-source-hold]");
  assert.equal(await studio.count(),1,"Every private review card needs its honest studio source hold");
  assert.equal(await page.locator("[data-scent-artwork]").count(),0,"Review cards must not reintroduce fake product photography");
  assert.equal(
    (await studio.locator("[data-dufynd-studio-source-label]").textContent())?.trim(),
    "Originalfoto in Prüfung",
  );
  assert.equal(await page.locator("#duftverlauf .dufynd-notes-overview").count(),1,"Private profiles share the public note layout");
  const contrast=await studio.locator("[data-dufynd-studio-source-label]").evaluate(el=>{
    const bg=getComputedStyle(el.closest("[data-dufynd-studio-source-hold]")).backgroundColor;
    const fg=getComputedStyle(el).color;
    const luminance=value=>value.match(/[\d.]+/g).slice(0,3).map(Number).map(c=>c/255).map(c=>c<=.04045?c/12.92:((c+.055)/1.055)**2.4).reduce((sum,c,i)=>sum+c*[.2126,.7152,.0722][i],0);
    const a=luminance(fg),b=luminance(bg);return (Math.max(a,b)+.05)/(Math.min(a,b)+.05);
  });assert.ok(contrast>=4.5,'Private studio source label needs accessible text contrast');
  assert.equal(await page.evaluate(()=>document.getAnimations().length),0,'Reduced-motion page has no running animation');
  assert.equal(await page.locator('img').count(),0,'No invented bottle');
  assert.equal(await page.locator('a[href*="awin"],a[href*="clickout"]').count(),0);
  const schemas=await page.locator('script[type="application/ld+json"]').allTextContents();
  assert.ok(schemas.every(s=>!s.includes('aggregateRating')&&!s.includes('"offers"')),'No invented structured offers or ratings');
  const art=await studio.boundingBox();
  assert.ok(art,"A private studio identity panel must be visible");
  if(width<768) assert.ok(art.y<470,'Honest studio panel appears before description on mobile');
  assert.equal(await page.locator('link[rel=canonical]').count(),0,'Private pages have no public canonical');
  assert.ok((await page.title()).includes(p.expected_variant.name));
  assert.equal(await page.locator('meta[name=description]').getAttribute('content'),p.seo.description);
  {
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
await photoIntegrationQa(browser,{base,out});
}finally{await browser.close();}
assert.equal(rendererDigest(),builtRenderer,'Source changed during browser QA: do not certify mixed revisions');
writeFileSync(`${out}/report.json`,JSON.stringify(report,null,2));
writeFileSync(`${out}/release-qa.json`,JSON.stringify({schema_version:1,profiles:pilots.map(p=>({product_id:p.product_id,passed:true,evidence_sha256:p.evidence_sha256,render_sha256:renderDigest(p,builtRenderer),widths:report.map(r=>r.width)}))},null,2)+'\n');
console.log(JSON.stringify(report));
