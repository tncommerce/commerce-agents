'use strict';
const assert=require('node:assert/strict');
const fs=require('node:fs');
const path=require('node:path');
const crypto=require('node:crypto');
const {chromium}=require(path.resolve('candidate/examples/node_modules/playwright'));
const MODE=process.argv[2];
const ROOT=path.resolve('candidate');
const read=p=>JSON.parse(fs.readFileSync(path.join(ROOT,p),'utf8'));
const TARGET='833feefcd6e4c525ef83fcd0a3a3f9f9b72629f3';
const normalize=x=>String(x||'').normalize('NFKD').replace(/[\u0300-\u036f]/g,'').replace(/[’']/g,'').replace(/&/g,' und ').toLowerCase().replace(/[^a-z0-9]+/g,'-').replace(/^-+|-+$/g,'');
async function security(browser){
 const offers=read('examples/retail/data/merchant_offers.json').offers;
 const source=read('examples/retail/storefront-web/lib/generated/public-catalog.json').products;
 const photos=read('examples/retail/storefront-web/lib/generated/original-photos.json');
 const products=new Map(source.map(p=>[p.product_id,p]));
 const byProduct=new Map();
 for(const o of offers.filter(o=>o.merchant_id==='top-parfuemerie'||o.offer_id==='perfumetrader-rabanne-1-million-edt-100')){
   const list=byProduct.get(o.product_id)||[];list.push(o);byProduct.set(o.product_id,list);
 }
 assert.equal([...byProduct.values()].flat().filter(o=>o.merchant_id==='top-parfuemerie').length,10);
 const cases=[];
 for(const width of [320,390,768,1440]){
  const ctx=await browser.newContext({viewport:{width,height:900},locale:'de-DE',reducedMotion:'reduce',serviceWorkers:'block'});
  let blocked=0;
  await ctx.route('**/*',async route=>{
   const r=route.request(),u=new URL(r.url());
   if(u.pathname.startsWith('/api/merchant-offers/')){
    const pid=decodeURIComponent(u.pathname.split('/').pop());
    const rows=(byProduct.get(pid)||[]).map(o=>({...o,affiliate_url:undefined,product_url:undefined,affiliate_link:true,total_price:o.price+(o.shipping_cost||0),clickout_path:'/api/clickout/'+o.offer_id,last_updated_at:new Date().toISOString()})).sort((a,b)=>a.total_price-b.total_price);
    return route.fulfill({status:200,contentType:'application/json',body:JSON.stringify({product_id:pid,offers:rows,best_offer_id:rows[0]?.offer_id||null,affiliate_disclosure:'ISOLATED SECURITY TEST FIXTURE: NOT LIVE PRICE EVIDENCE'})});
   }
   if(r.resourceType()==='image'&&!['127.0.0.1','localhost'].includes(u.hostname)){
    const photo=photos.find(p=>p.url===r.url()),w=photo?.width||300,h=photo?.height||600;
    return route.fulfill({status:200,contentType:'image/svg+xml',body:'<svg xmlns="http://www.w3.org/2000/svg" width="'+w+'" height="'+h+'"><rect width="100%" height="100%" fill="#ccc"/></svg>'});
   }
   if(r.method()!=='GET'||u.pathname.includes('/api/clickout/')||!['127.0.0.1','localhost'].includes(u.hostname)){blocked++;return route.abort();}
   return route.continue();
  });
  for(const [pid,rows] of byProduct){
   const p=products.get(pid);assert.ok(p,'canonical product required');
   const slug=normalize(p.brand+' '+(p.attributes?.canonical_name||p.title));
   const page=await ctx.newPage(),errors=[];page.on('pageerror',e=>errors.push(e.message));
   try{
    const r=await page.goto('http://127.0.0.1:3019/duft/'+slug,{waitUntil:'domcontentloaded'});assert.equal(r.status(),200);
    const section=page.locator('[data-offer-state="available"]');await section.waitFor({state:'visible',timeout:12000});
    const text=await section.innerText();assert.match(text,/top parfümerie/i);assert.ok(text.includes(String(p.attributes?.volume_ml)+' ml'));
    assert.ok(text.includes('Gesamtpreis inkl. Versand'));
    const anchors=await section.locator('a[href*="/api/clickout/"]').evaluateAll(xs=>xs.map(a=>({href:a.getAttribute('href'),rel:a.getAttribute('rel')})));
    assert.ok(anchors.length===rows.length&&anchors.every(a=>a.rel.includes('sponsored')&&a.rel.includes('noopener')));
    const original=photos.find(p=>p.product_id===pid);
    if(original)assert.ok((await page.locator('img').evaluateAll(xs=>xs.map(x=>x.getAttribute('src')))).includes(original.url));
    assert.ok(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1));assert.deepEqual(errors,[]);
    if(pid==='SC-RABANNE-1-MILLION-EDT-100')assert.ok(text.indexOf('Perfumetrader')<text.indexOf('top Parfümerie'));
    cases.push({width,product_id:pid,status:'PASS',offers:anchors.length});
   }finally{await page.close();}
  }
  await ctx.close();
 }
 console.log('SECURITY_BROWSER_ACCEPTANCE='+JSON.stringify({status:'PASS',head:TARGET,cases:cases.length,widths:[320,390,768,1440],rows:cases,fixtures:true,real_photo_decode:false,live_price_evidence:false,external_network_requests:0,affiliate_clickouts:0,production_writes:0}));
}
async function shop(browser){
 const source=read('examples/retail/data/merchant_offers.json').offers;
 const products=read('examples/retail/data/scentai_products.json').products;
 const byId=new Map(products.map(p=>[p.product_id,p]));
 const targets=source.filter(o=>o.merchant_id==='top-parfuemerie');assert.equal(targets.length,10);
 const ctx=await browser.newContext({locale:'de-DE',viewport:{width:1280,height:900},serviceWorkers:'block'});
 let blocked=0;
 await ctx.route('**/*',async route=>{
   const r=route.request(),u=new URL(r.url());
   if(r.method()!=='GET'||r.resourceType()==='image'||!['www.topparfuemerie.de','topparfuemerie.de'].includes(u.hostname)||/\/(checkout|customer|wishlist|cart)\//i.test(u.pathname)){blocked++;return route.abort();}
   return route.continue();
 });
 const results=[];
 const snapshot=async page=>page.evaluate(()=>{
  const root=document.querySelector('.product-info-main')||document.querySelector('main')||document.body;
  const label=el=>Array.from(el.labels||[]).map(l=>l.innerText.trim()).join(' ')||el.getAttribute('aria-label')||el.title||'';
  const radios=Array.from(root.querySelectorAll('input[type="radio"]')).map(el=>({id:el.id,name:el.name,value:el.value,checked:el.checked,disabled:el.disabled,label:label(el)}));
  const selects=Array.from(root.querySelectorAll('select')).map(el=>({id:el.id,name:el.name,value:el.value,label:label(el),options:Array.from(el.options).map(o=>({value:o.value,label:o.label,selected:o.selected,disabled:o.disabled}))}));
  const priceNodes=Array.from(root.querySelectorAll('[data-price-amount]')).map(el=>({type:el.getAttribute('data-price-type'),amount:el.getAttribute('data-price-amount'),text:el.innerText}));
  const prices=Array.from(root.querySelectorAll('.price-box,.price-info')).map(el=>el.innerText.slice(0,500));
  const stock=Array.from(root.querySelectorAll('.stock,.availability,.delivery-time,[data-role="stock-status"],.delivery')).map(el=>el.innerText.slice(0,350));
  const sku=Array.from(root.querySelectorAll('[itemprop="sku"],.product.attribute.sku .value')).map(el=>el.textContent.trim());
  const buttons=Array.from(root.querySelectorAll('button')).filter(el=>/warenkorb/i.test(el.innerText)).map(el=>({id:el.id,text:el.innerText.trim(),disabled:el.disabled,visible:el.getBoundingClientRect().height>0}));
  const gallery=Array.from(document.querySelectorAll('.gallery-placeholder img,.fotorama img,[data-gallery-role] img')).map(el=>el.getAttribute('src')||el.getAttribute('data-src')).filter(Boolean);
  return {title:document.querySelector('h1')?.innerText,radios,selects,priceNodes,prices,stock,sku,buttons,gallery,body_excerpt:root.innerText.slice(0,4200)};
 });
 let inaccessible=0;
 for(const offer of targets){
  const p=byId.get(offer.product_id),ml=p?.volume_ml;assert.ok(Number.isInteger(ml)&&ml>0);
  const u=new URL(offer.product_url);assert.equal(u.hostname,'www.topparfuemerie.de');const page=await ctx.newPage();
  try{
    const response=await page.goto(offer.product_url,{waitUntil:'domcontentloaded',timeout:20000});
    if(response?.status()!==200){results.push({offer_id:offer.offer_id,status:'HOLD_HTTP',http_status:response?.status()});inaccessible++;continue;}
    await page.waitForTimeout(1800);const before=await snapshot(page);let selection='no_safe_exact_control';
    const exact=new RegExp('^'+ml+'\\s*ml$','i');
    const rad=before.radios.filter(r=>!r.disabled&&exact.test(r.label.trim()));
    const select=before.selects.flatMap(s=>s.options.filter(o=>!o.disabled&&exact.test(o.label.trim())).map(o=>({select:s,option:o})));
    if(rad.length===1&&rad[0].id){const r=rad[0];if(!r.checked)await page.locator('[id="'+r.id.replace(/"/g,'\\"')+'"]').check({force:true,timeout:3000});selection='exact_radio';}
    else if(select.length===1&&select[0].select.id){const s=select[0];await page.locator('[id="'+s.select.id.replace(/"/g,'\\"')+'"]').selectOption(s.option.value);selection='exact_select';}
    await page.waitForTimeout(1000);const after=await snapshot(page);const html=await page.content();
    results.push({offer_id:offer.offer_id,product_id:offer.product_id,expected_sku:offer.merchant_product_id,expected_ml:ml,url:offer.product_url,http_status:200,checked_at:new Date().toISOString(),html_sha256:crypto.createHash('sha256').update(html).digest('hex'),selection_method:selection,before:{sku:before.sku,radio_options:before.radios,selects:before.selects},after,status:'RAW_MERCHANT_OBSERVATION_REQUIRES_EXACT_VARIANT_VALIDATION',current_price_verified:false,public_offer_updated:false});inaccessible=0;
  }catch(e){inaccessible++;results.push({offer_id:offer.offer_id,status:'HOLD_SOURCE_ACCESS',reason:String(e.message).slice(0,250)});}
  finally{await page.close();}
  if(inaccessible>=2){results.push({status:'STOP_AFTER_TWO_ACCESS_FAILURES',unvisited:targets.length-results.length});break;}
 }
 console.log('MERCHANT_VARIANT_READONLY='+JSON.stringify({checked_at:new Date().toISOString(),source:'direct merchant browser, not search cache',observations:results,blocked_requests:blocked,affiliate_clickouts:0,cart_actions:0,price_activations:0,render_deploys:0}));await ctx.close();
}
(async()=>{const browser=await chromium.launch({headless:true});try{if(MODE==='security')await security(browser);else if(MODE==='merchant')await shop(browser);else throw Error('Unknown mode');}finally{await browser.close();}})().catch(e=>{console.error('BLOCK_QA_FAILED='+JSON.stringify({mode:MODE,error:String(e.stack).slice(0,1800)}));process.exitCode=2;});
