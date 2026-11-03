import assert from 'node:assert/strict';
import {readFileSync,writeFileSync,mkdirSync} from 'node:fs';
import {createHash} from 'node:crypto';

export async function photoIntegrationQa(browser,{base,out}) {
  const {items,holds}=JSON.parse(readFileSync(new URL('../../data/dufynd_photo_integration_review.json',import.meta.url),'utf8'));
  const originals=JSON.parse(readFileSync(new URL('../lib/generated/original-photos.json',import.meta.url),'utf8'));
  assert.equal(items.length,6);
  assert.equal(originals.length,10,'Explicitly prepared public image set; private review remains separate');
  assert.equal(holds.length,0,'All six exact source photographs visually accepted on 26 October');
  mkdirSync(`${out}/photo-integration`,{recursive:true});
  const report=[];
  for(const width of [390,1440]) {
    const page=await browser.newPage({viewport:{width,height:900},deviceScaleFactor:2,reducedMotion:'reduce'});
    const errors=[];page.on('pageerror',e=>errors.push(e.message));
    // No analytics, merchant requests or synthetic clickouts during visual QA.
    await page.route('**/*',r=>new URL(r.request().url()).origin===new URL(base).origin || originals.some(p=>p.url===r.request().url()) ? r.continue() : r.abort());
    await page.route('**/analytics/**',r=>r.fulfill({status:204}));
    await page.goto(`${base}/duft`);
    await page.locator('.dufynd-catalog-card').first().waitFor();
    for(const img of await page.locator('.dufynd-catalog-card img').all()) {
      await img.scrollIntoViewIfNeeded();
      await img.evaluate(x=>x.decode());
    }
    await page.evaluate(()=>scrollTo(0,0));
    await page.screenshot({path:`${out}/photo-integration/catalog-public-before-${width}.png`,fullPage:true});
    await page.goto(`${base}/review/photos`);
    assert.equal(await page.locator('[data-photo-review-card]').count(),6);
    assert.ok((await page.locator('meta[name=robots]').getAttribute('content')).includes('noindex'));
    assert.equal(await page.locator('a[href*=clickout],a[href*=awin]').count(),0);
    const links=await page.locator('[data-photo-review-card] a').evaluateAll(xs=>xs.map(x=>x.getAttribute('href')));
    await page.locator('[data-dufynd-original-review-photo] img').evaluateAll(xs=>Promise.all(xs.map(x=>x.decode())));
    await page.screenshot({path:`${out}/photo-integration/catalog-merchant-review-after-${width}.png`,fullPage:true});
    for(const [i,item] of items.entries()) {
      const slug=links[i].split('/').at(-1);
      await page.goto(`${base}/duft/${slug}`);
      await page.locator('h1').waitFor();
      assert.equal(await page.locator('[data-dufynd-original-review-photo]').count(),0,'Public page must not inherit merchant preview approval');
      const notes=await page.locator('.dufynd-notes-overview').innerText();
      await page.screenshot({path:`${out}/photo-integration/${item.merchant_product_id}-before-${width}.png`});
      const response=await page.goto(`${base}${links[i]}`);assert.equal(response.status(),200);
      assert.equal(await page.locator('[data-photo-review-boundary]').count(),1);
      assert.equal(await page.locator('#angebote,#dufynd-hero-offer-cta').count(),0);
      assert.equal(await page.locator('a[href*=clickout],a[href*=awin]').count(),0);
      assert.equal(await page.locator('link[rel=canonical]').count(),0);
      assert.ok((await page.locator('meta[name=robots]').getAttribute('content')).includes('noindex'));
      assert.equal(await page.locator('.dufynd-notes-overview').innerText(),notes,'Same documented notes as public page');
      const img=page.locator('[data-dufynd-original-review-photo] img');
      await img.evaluate(x=>x.decode());
      const actual=await img.evaluate(x=>({width:x.naturalWidth,height:x.naturalHeight,filter:getComputedStyle(x).filter,transform:getComputedStyle(x).transform,fit:getComputedStyle(x).objectFit,displayHeight:x.getBoundingClientRect().height,src:x.src}));
      assert.equal(actual.width,item.width);assert.equal(actual.height,item.height);
      assert.equal(actual.filter,'none');assert.equal(actual.transform,'none');assert.equal(actual.fit,'contain');
      assert.ok(actual.displayHeight<=260.1&&actual.displayHeight*2<=item.height,'Source supports display at 2x without upscaling');
      const frame=await img.evaluate(x=>{
        const image=x.getBoundingClientRect();
        const stage=x.closest('.dufynd-fragrance-stage-shell').getBoundingClientRect();
        return {top:image.top-stage.top,bottom:stage.bottom-image.bottom,left:image.left-stage.left,right:stage.right-image.right};
      });
      assert.ok(Object.values(frame).every(gap=>gap>=8),'Entire original bottle must fit inside the stage with breathing room');
      const bytes=await (await page.request.get(actual.src)).body();
      assert.equal(createHash('sha256').update(bytes).digest('hex'),item.image_sha256,'Exact owner-reviewed image bytes');
      assert.ok(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth),'No horizontal overflow');
      await page.screenshot({path:`${out}/photo-integration/${item.merchant_product_id}-after-${width}.png`});
      await page.screenshot({path:`${out}/photo-integration/${item.merchant_product_id}-after-full-${width}.png`,fullPage:true});
      report.push({product_id:item.product_id,width,image_sha256:item.image_sha256,display_height:actual.displayHeight,stage_gaps:frame,status:'passed',public_registry_unchanged:true,merchant:'top-parfuemerie',public_release:false});
    }
    assert.deepEqual(errors,[]);await page.close();
  }
  writeFileSync(`${out}/photo-integration/report.json`,JSON.stringify(report,null,2)+'\n');
  console.log(`Merchant photo integration: ${report.length} exact-image responsive checks passed; public gates unchanged.`);
}
