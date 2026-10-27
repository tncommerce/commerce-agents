import assert from 'node:assert/strict';
import { chromium } from 'playwright';

const BASE='https://dufynd.de', PROD='36cc84c34791284e4245ab4504ae020434dca89e';
const PHOTOS=[
 ['SC-PDM-DELINA-EDP-75','parfums-de-marly-delina','825869_3700578501998_051.png'],
 ['SC-YSL-BLACK-OPIUM-EDP-90','yves-saint-laurent-black-opium','787670_3365440787971_051.png'],
 ['SC-YSL-LIBRE-EDP-90','yves-saint-laurent-libre','856448_3614272648425_051.png'],
 ['SC-ESSENTIAL-PARFUMS-BOIS-IMPERIAL-100','essential-parfums-bois-imperial','924719_3770010614630_051.png'],
 ['SC-ARMANI-SWY-INTENSELY-100','giorgio-armani-stronger-with-you-intensely','849484_3614272225718_051.png'],
 ['SC-PDM-LAYTON-125','parfums-de-marly-layton','812773_3700578502322_051.png'],
 ['SC-VALENTINO-BORN-IN-ROMA-INTENSE-100','valentino-uomo-born-in-roma-intense','897029_3614273790826_051.png'],
 ['SC-PDM-ALTHAIR-125','parfums-de-marly-althair','904707_904707_061.png'],
 ['SC-RABANNE-1-MILLION-EDT-100','rabanne-1-million','707368_3349666007921_051.png'],
 ['SC-LANCOME-LA-VIE-EST-BELLE-EDP-100','lancome-la-vie-est-belle','3605533286555.webp']
];
const OFFERS=[
 ['SC-RABANNE-1-MILLION-EDT-100','rabanne-1-million','100 ml','707368'],
 ['SC-ESSENTIAL-PARFUMS-BOIS-IMPERIAL-100','essential-parfums-bois-imperial','100 ml','924719'],
 ['SC-ARMANI-SWY-INTENSELY-100','giorgio-armani-stronger-with-you-intensely','100 ml','849484'],
 ['SC-PDM-LAYTON-125','parfums-de-marly-layton','125 ml','812773'],
 ['SC-VALENTINO-BORN-IN-ROMA-INTENSE-100','valentino-uomo-born-in-roma-intense','100 ml','897029'],
 ['SC-PDM-ALTHAIR-125','parfums-de-marly-althair','125 ml','904707'],
 ['SC-MONTBLANC-EXPLORER-100','montblanc-explorer','100 ml','849457'],
 ['SC-CREED-AVENTUS-100','creed-aventus','100 ml','827407'],
 ['SC-PRADA-LHOMME-100','prada-lhomme','100 ml','815682'],
 ['SC-XERJOFF-NAXOS-100','xerjoff-naxos','100 ml','836129']
];
assert.equal(PHOTOS.length,10);
assert.equal(OFFERS.length,10);
assert.equal(new Set(PHOTOS.map(p=>p[0])).size,10);
assert.equal(new Set(OFFERS.map(p=>p[0])).size,10);
const browser=await chromium.launch({headless:true});
const ctx=await browser.newContext({viewport:{width:390,height:844},locale:'de-DE',reducedMotion:'reduce',serviceWorkers:'block'});
const blocked=[];
await ctx.route('**/*', async route=>{
 const req=route.request(),u=new URL(req.url());
 if(req.method()!=='GET'||/\/api\/clickout\/|\/api\/analytics|\/analytics\/|\/session(?:\/|$)/.test(u.pathname)||
  /(^|\.)awin1\.com$|jdoqocy\.com$|commissionjunction\.com$/.test(u.hostname)){
   blocked.push({method:req.method(),path:u.pathname});return route.abort();
 }
 return route.continue();
});
const photoChecks=[],offerChecks=[];
async function safePage(slug,operation,callback){
 const p=await ctx.newPage(),errors=[];
 p.on('pageerror',e=>errors.push(e.message.slice(0,240)));
 try{
   const res=await p.goto(BASE+'/duft/'+slug,{waitUntil:'domcontentloaded',timeout:25000});
   assert.equal(res?.status(),200,'Public HTML not 200 for '+slug);
   const result=await callback(p);
   const geo=await p.evaluate(()=>({scroll:document.documentElement.scrollWidth,viewport:innerWidth}));
   assert.ok(geo.scroll<=geo.viewport+1,'Mobile horizontal overflow '+slug);
   assert.deepEqual(errors,[],'Browser JavaScript errors '+slug);
   return result;
 }catch(e){
   const state=await p.locator('[data-offer-state]').evaluateAll(nodes=>nodes.map(n=>n.getAttribute('data-offer-state'))).catch(()=>[]);
   console.log('DUFYND_BROWSER_QA_FAIL='+JSON.stringify({phase:operation,slug,error:String(e.message).slice(0,450),
       offers_state:state,js_errors:errors,blocked_requests:blocked.length}));
   throw e;
 }finally{await p.close();}
}
try {
 for(const [pid,slug,filename,ml,sku] of OFFERS){
  const data=await safePage(slug,'offer',async page=>{
    const section=page.locator('[data-merchant-offers][data-offer-state="available"]');
    await section.waitFor({state:'visible',timeout:18000});
    const contents=await section.innerText();
    assert.ok(/top parfümerie/i.test(contents),'Top offer missing from rendered page '+slug);
    assert.ok(contents.includes(ml),'Wrong volume on live offer '+slug+'; public_rendered_text='+JSON.stringify(contents.slice(0,1400)));
    assert.ok(contents.includes('Gesamtpreis inkl. Versand'),'Total price disclosure missing '+slug);
    const links=await section.locator('a[href*="/api/clickout/"]').evaluateAll(nodes=>nodes.map(n=>({
      href:n.getAttribute('href'),rel:n.getAttribute('rel')
    })));
    assert.ok(links.length>=1,'No visible purchase CTA '+slug);
    assert.ok(links.every(x=>x.rel?.includes('noopener')&&x.rel?.includes('noreferrer')),
      'Unsafe merchant CTA '+slug);
    if(pid==='SC-RABANNE-1-MILLION-EDT-100'){
      assert.ok(contents.includes('Perfumetrader'),'Certified cheaper Perfumetrader missing');
      assert.ok(contents.indexOf('Perfumetrader')<contents.indexOf('top Parfümerie'),
        'Perfumetrader lost first-ranked buyer spot');
    }
    return {product_id:pid,slug,merchant_sku:sku,volume:ml,live_ui_available:true,
      link_ctas:links.length,total_including_shipping_label:true};
  });
  offerChecks.push(data);
 }
 for(const [pid,slug,filename] of PHOTOS){
  const data=await safePage(slug,'photo',async page=>{
    const img=page.locator('img[src*="'+filename+'"]').first();
    assert.equal(await img.count(),1,'Exact original image not on page '+slug);
    await img.scrollIntoViewIfNeeded({timeout:12000});
    await img.waitFor({state:'visible',timeout:12000});
    const res=await img.evaluate(async el=>{
      try{await Promise.race([el.decode(),new Promise((_,reject)=>setTimeout(()=>reject(Error('timeout')),10000))]);}catch{}
      return {natural_width:el.naturalWidth,natural_height:el.naturalHeight,complete:el.complete,
        display_height:el.getBoundingClientRect().height,alt:el.alt};
    });
    assert.ok(res.complete&&res.natural_width>0&&res.natural_height>0,
      'Remote packshot pixels failed to load '+slug+' '+JSON.stringify(res));
    assert.ok(res.display_height>35&&res.alt?.trim(),'Source image hidden or unlabelled '+slug);
    return {product_id:pid,slug,source_file:filename,loaded:true,
      natural_width:res.natural_width,natural_height:res.natural_height};
  });
  photoChecks.push(data);
 }
 console.log('DUFYND_BROWSER_QA_SUCCESS='+JSON.stringify({
  status:'ALL_10_LIVE_OFFERS_HYDRATED_AND_10_ORIGINAL_IMAGES_DECODED',
  expected_live_commit:PROD,offers:offerChecks,images:photoChecks,
  affiliate_clickouts:0,production_writes:0,analytics_post_requests_blocked:blocked.filter(x=>x.method!=='GET').length
 }));
} catch {process.exitCode=2;} finally{await ctx.close();await browser.close();}
