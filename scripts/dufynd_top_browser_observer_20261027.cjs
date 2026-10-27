'use strict';
const fs=require('node:fs'),path=require('node:path'),assert=require('node:assert/strict'),crypto=require('node:crypto');
const {chromium}=require(process.env.DUFYND_BROWSER_MODULE);
const ROOT=path.resolve('candidate');
const read=p=>JSON.parse(fs.readFileSync(path.join(ROOT,p),'utf8'));
const all=read('examples/retail/data/merchant_offers.json').offers.filter(o=>o.merchant_id==='top-parfuemerie');
const facts=new Map(read('examples/retail/data/scentai_products.json').products.map(p=>[p.product_id,p]));
const limit=Number(process.env.DUFYND_PROBE_LIMIT||2);assert.ok([2,10].includes(limit));assert.equal(all.length,10);
const targets=limit===2?all.filter(o=>['707368','849457'].includes(o.merchant_product_id)):all;
const hash=x=>crypto.createHash('sha256').update(x).digest('hex');
async function snapshot(page,ml,sku){return page.evaluate(({ml,sku})=>{
 const norm=s=>String(s||'').replace(/\s+/g,' ').trim();
 const label=el=>norm(Array.from(el.labels||[]).map(l=>l.innerText).join(' ')||el.getAttribute('aria-label')||el.title);
 const radios=Array.from(document.querySelectorAll('input[type="radio"]')).map(el=>({id:el.id,name:el.name,value:el.value,checked:el.checked,disabled:el.disabled,label:label(el),form:el.form?.id||''}));
 const selects=Array.from(document.querySelectorAll('select')).map(el=>({id:el.id,name:el.name,value:el.value,label:label(el),form:el.form?.id||'',options:Array.from(el.options).map(o=>({value:o.value,label:norm(o.label),selected:o.selected,disabled:o.disabled}))}));
 const prices=Array.from(document.querySelectorAll('[data-price-amount]')).map(el=>({id:el.id,priceType:el.getAttribute('data-price-type'),amount:el.getAttribute('data-price-amount'),text:norm(el.innerText),priceBox:el.closest('[data-product-id]')?.getAttribute('data-product-id')}));
 const skuTexts=Array.from(document.querySelectorAll('[itemprop="sku"],.product.attribute.sku .value,.product-sku')).map(el=>norm(el.textContent));
 const stock=Array.from(document.querySelectorAll('.stock,.availability,.delivery-time,[data-role="stock-status"],.delivery,.delivery-information')).map(el=>norm(el.innerText)).filter(Boolean);
 const buttons=Array.from(document.querySelectorAll('button')).filter(el=>/warenkorb/i.test(el.innerText)).map(el=>({id:el.id,text:norm(el.innerText),disabled:el.disabled,visible:el.getBoundingClientRect().height>0,form:el.form?.id||''}));
 const gallery=Array.from(document.querySelectorAll('.gallery-placeholder img,.fotorama img,[data-gallery-role] img')).map(el=>el.getAttribute('src')||el.getAttribute('data-src')).filter(Boolean);
 const configs=[];function scan(o,depth=0){if(depth>15||configs.length>6)return;if(o&&typeof o==='object'){if(o.optionPrices&&o.attributes){const options=[];for(const a of Object.values(o.attributes))for(const op of a.options||[]){if(new RegExp('^'+ml+'\\s*ml$','i').test(String(op.label).trim()))for(const id of op.products||[]){const entry=o.optionPrices[String(id)];options.push({label:op.label,internalId:String(id),price:entry?.finalPrice?.amount,images:(o.images?.[String(id)]||[]).map(i=>({img:i.img,full:i.full,caption:i.caption})),sku:o.skus?.[String(id)]||o.sku?.[String(id)]||null,salable:o.salable?.[String(id)]??null});}}configs.push({keys:Object.keys(o),options});}for(const v of Object.values(o).slice(0,100))if(v&&typeof v==='object')scan(v,depth+1);}}
 for(const s of document.querySelectorAll('script[type="text/x-magento-init"]')){try{scan(JSON.parse(s.textContent))}catch{}}
 const full=document.body.innerText,title=document.querySelector('h1')?.innerText||'',idx=full.indexOf(title);
 return {title,radios,selects,prices,skuTexts,stock,buttons,gallery,configs,body_excerpt:full.slice(Math.max(0,idx),Math.max(0,idx)+6500)};
},{ml,sku});}
(async()=>{
 const browser=await chromium.launch({headless:true}),ctx=await browser.newContext({locale:'de-DE',viewport:{width:1280,height:900},serviceWorkers:'block'});
 const blocked=[];
 await ctx.route('**/*',async route=>{const r=route.request(),u=new URL(r.url());const merchant=['www.topparfuemerie.de','topparfuemerie.de'].includes(u.hostname);const staticAsset=['script','stylesheet','font'].includes(r.resourceType());
 if(r.method()!=='GET'||r.resourceType()==='image'||/awin1\.com|google-analytics|googletagmanager|doubleclick|facebook|clarity\.ms|jdoqocy\.com|hotjar/i.test(u.hostname)||/\/(checkout|customer|wishlist|cart)\//i.test(u.pathname)||(!merchant&&!staticAsset)){blocked.push({host:u.hostname,type:r.resourceType(),method:r.method(),path:u.pathname.slice(0,100)});return route.abort();}return route.continue();});
 try{
  for(const offer of targets){const product=facts.get(offer.product_id),ml=product.volume_ml;assert.equal(new URL(offer.product_url).hostname,'www.topparfuemerie.de');const page=await ctx.newPage(),errors=[];page.on('pageerror',e=>errors.push(e.message.slice(0,200)));
   try{
    const response=await page.goto(offer.product_url,{waitUntil:'domcontentloaded',timeout:25000});assert.equal(response.status(),200);
    await page.waitForFunction(()=>document.querySelector('input[type="radio"], [data-price-amount]'),{},{timeout:10000}).catch(()=>{});
    const before=await snapshot(page,ml,offer.merchant_product_id);let method='NO_EXACT_CONTROL';const exact=new RegExp('^'+ml+'\\s*ml(?:\\s|$)','i');
    const radio=before.radios.filter(r=>!r.disabled&&exact.test(r.label));const selects=before.selects.flatMap(s=>s.options.filter(o=>!o.disabled&&exact.test(o.label)).map(o=>({s,o})));
    if(radio.length===1&&radio[0].id){const r=radio[0];if(!r.checked)await page.locator('[id="'+r.id.replace(/"/g,'\\"')+'"]').check({force:true,timeout:5000});method='EXACT_SIZE_RADIO';}
    else if(selects.length===1&&selects[0].s.id){const {s,o}=selects[0];await page.locator('[id="'+s.id.replace(/"/g,'\\"')+'"]').selectOption(o.value);method='EXACT_SIZE_SELECT';}
    await page.waitForTimeout(1500);const after=await snapshot(page,ml,offer.merchant_product_id);const html=await page.content();
    console.log('TOP_BROWSER_SOURCE='+JSON.stringify({offer_id:offer.offer_id,product_id:offer.product_id,url:offer.product_url,expected_sku:offer.merchant_product_id,expected_ml:ml,checked_at:new Date().toISOString(),html_sha256:hash(html),selection_method:method,before:{radios:before.radios,selects:before.selects,prices:before.prices},after,js_errors:errors,decision:'REVIEW_ONLY',public_offer_updated:false}));
   }catch(e){console.log('TOP_BROWSER_SOURCE='+JSON.stringify({offer_id:offer.offer_id,status:'HOLD',reason:String(e.message).slice(0,300)}));}finally{await page.close();}
  }
  const shipping=await ctx.newPage();try{const r=await shipping.goto('https://www.topparfuemerie.de/zahlung-versand',{waitUntil:'domcontentloaded',timeout:20000});const text=await shipping.locator('body').innerText();const at=text.search(/versandkosten|deutschland/i);console.log('TOP_SHIPPING_SOURCE='+JSON.stringify({url:shipping.url(),http_status:r.status(),checked_at:new Date().toISOString(),text_sha256:hash(text),excerpt:text.slice(Math.max(0,at-150),Math.max(0,at-150)+4500),decision:'REVIEW_ONLY'}));}catch(e){console.log('TOP_SHIPPING_SOURCE='+JSON.stringify({status:'HOLD',reason:String(e.message).slice(0,200)}));}finally{await shipping.close();}
  console.log('TOP_OBSERVER_SUMMARY='+JSON.stringify({target_count:targets.length,blocked_requests:blocked.length,blocked_samples:blocked.slice(0,15),affiliate_clickouts:0,cart_actions:0,production_mutations:0}));
 }finally{await ctx.close();await browser.close();}
})().catch(e=>{console.error(String(e.stack));process.exitCode=2;});
