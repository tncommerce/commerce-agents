import assert from 'node:assert/strict';
import { chromium } from 'playwright';

const BASE = 'https://dufynd.de';
const PROD = '36cc84c34791284e4245ab4504ae020434dca89e';
const ROWS = [
  ['SC-PDM-DELINA-EDP-75','parfums-de-marly-delina','825869_3700578501998_051.png','75 ml'],
  ['SC-YSL-BLACK-OPIUM-EDP-90','yves-saint-laurent-black-opium','787670_3365440787971_051.png','90 ml'],
  ['SC-YSL-LIBRE-EDP-90','yves-saint-laurent-libre','856448_3614272648425_051.png','90 ml'],
  ['SC-ESSENTIAL-PARFUMS-BOIS-IMPERIAL-100','essential-parfums-bois-imperial','924719_3770010614630_051.png','100 ml'],
  ['SC-ARMANI-SWY-INTENSELY-100','giorgio-armani-stronger-with-you-intensely','849484_3614272225718_051.png','100 ml'],
  ['SC-PDM-LAYTON-125','parfums-de-marly-layton','812773_3700578502322_051.png','125 ml'],
  ['SC-VALENTINO-BORN-IN-ROMA-INTENSE-100','valentino-uomo-born-in-roma-intense','897029_3614273790826_051.png','100 ml'],
  ['SC-PDM-ALTHAIR-125','parfums-de-marly-althair','904707_904707_061.png','125 ml'],
  ['SC-RABANNE-1-MILLION-EDT-100','rabanne-1-million','707368_3349666007921_051.png','100 ml'],
  ['SC-LANCOME-LA-VIE-EST-BELLE-EDP-100','lancome-la-vie-est-belle','3605533286555.webp','100 ml']
];
assert.equal(ROWS.length, 10);
assert.equal(new Set(ROWS.map(r=>r[0])).size, 10);

function forbidden(req) {
  const u = new URL(req.url());
  return req.method() !== 'GET'
    || /\/api\/clickout\/|\/api\/analytics|\/analytics\/|\/session(?:\/|$)/.test(u.pathname)
    || /(^|\.)awin1\.com$|jdoqocy\.com$|commissionjunction\.com$/.test(u.hostname);
}
const browser = await chromium.launch({headless:true});
const context = await browser.newContext({
  viewport:{width:390,height:844}, locale:'de-DE',
  reducedMotion:'reduce',serviceWorkers:'block'
});
const blocked = [];
await context.route('**/*', async route => {
  const req = route.request();
  if (forbidden(req)) {
    blocked.push({method:req.method(),path:new URL(req.url()).pathname});
    return route.abort();
  }
  return route.continue();
});
const result = [];
try {
  for (const [pid, slug, file, ml] of ROWS) {
    const page = await context.newPage();
    const errors = [];
    page.on('pageerror',e=>errors.push(e.message.slice(0,250)));
    try {
      const response = await page.goto(BASE+'/duft/'+slug, {waitUntil:'domcontentloaded',timeout:25000});
      assert.equal(response?.status(),200,'Page HTTP 200 '+slug);
      const img = page.locator('img[src*="'+file+'"]').first();
      assert.equal(await img.count(),1,'Registered original image in HTML '+slug);
      await img.scrollIntoViewIfNeeded({timeout:12000});
      await img.waitFor({state:'visible',timeout:12000});
      const image = await img.evaluate(async el=>{
        try {
          await Promise.race([
            el.decode(),
            new Promise((_, reject)=>setTimeout(()=>reject(Error('photo_timeout')),9000))
          ]);
        } catch {}
        return {naturalWidth:el.naturalWidth,naturalHeight:el.naturalHeight,
          complete:el.complete,visibleHeight:el.getBoundingClientRect().height,alt:el.alt};
      });
      assert.ok(image.naturalWidth>0&&image.naturalHeight>0&&image.complete,
        'Original pixels could not decode '+slug+' '+JSON.stringify(image));
      assert.ok(image.visibleHeight>30&&image.alt?.trim(),'Original image hidden or unlabelled '+slug);
      const offers = page.locator('[data-merchant-offers][data-offer-state="available"]');
      await offers.waitFor({state:'visible',timeout:20000});
      const shown = await offers.innerText();
      assert.ok(/top parfümerie/i.test(shown),'Top offer invisible '+slug);
      assert.ok(shown.includes(ml),'Exact variant not visible '+slug);
      assert.ok(shown.includes('Gesamtpreis inkl. Versand'),'Total price not labelled '+slug);
      const links = await offers.locator('a[href*="/api/clickout/"]').evaluateAll(nodes=>
        nodes.map(n=>({href:n.getAttribute('href'),rel:n.getAttribute('rel')}))
      );
      assert.ok(links.length>=1&&links.every(x=>x.rel?.includes('noopener')&&x.rel?.includes('noreferrer')),
        'Unqualified merchant CTA '+slug);
      if(pid==='SC-RABANNE-1-MILLION-EDT-100'){
        assert.ok(shown.includes('Perfumetrader'),'Cheaper Perfumetrader omitted');
        assert.ok(shown.indexOf('Perfumetrader')<shown.indexOf('top Parfümerie'),
          'Rabanne Perfumetrader no longer best');
      }
      const bounds = await page.evaluate(()=>({scroll:document.documentElement.scrollWidth,width:innerWidth}));
      assert.ok(bounds.scroll<=bounds.width+1,'Mobile horizontal overflow '+slug);
      assert.deepEqual(errors,[],'Browser JavaScript errors '+slug);
      result.push({product_id:pid,slug,photo_pixels_loaded:true,
        natural_width:image.naturalWidth,natural_height:image.naturalHeight,
        offer_ctas_present:links.length,offer_state:'available',exact_ml:ml,
        mobile_width:390,overflow:false});
    } catch (error) {
      const state = await page.locator('[data-offer-state]').evaluateAll(
        nodes=>nodes.map(n=>n.getAttribute('data-offer-state'))
      ).catch(()=>[]);
      console.log('DUFYND_BROWSER_QA_FAIL='+JSON.stringify({product_id:pid,slug,
        error:String(error.message).slice(0,450),offer_states:state,errors,
        blocked_requests:blocked.length}));
      process.exitCode=2;
      break;
    } finally {await page.close();}
  }
  if(!process.exitCode) console.log('DUFYND_BROWSER_QA_SUCCESS='+JSON.stringify({
    status:'10_ORIGINALS_DECODED_AND_10_BUYER_OFFERS_RENDERED',
    source_live_commit:PROD,profiles:result,clickouts:0,production_mutations:0,
    blocked_analytics_write_requests:blocked.filter(x=>x.method!=='GET').length
  }));
} finally {await context.close();await browser.close();}
