import { chromium } from 'playwright';
import { mkdir, writeFile, readFile } from 'node:fs/promises';
import { chooseMeasurement } from './measurement-choice-qa.mjs';
// Read-only, localhost-only review captures; every API response is isolated.
const [baseUrl='http://127.0.0.1:3000',outputDir='.visual-qa/editorial-review']=process.argv.slice(2);
if(!/^http:\/\/(127\.0\.0\.1|localhost):\d+$/.test(baseUrl)) throw new Error('Review capture requires localhost');
const originals=JSON.parse(await readFile(new URL("../lib/generated/original-photos.json",import.meta.url),"utf8"));
const allowedOriginals=new Set(originals.filter(x=>x.rights_basis_id).map(x=>x.url));
await mkdir(outputDir,{recursive:true});
const browser=await chromium.launch({headless:true,args:['--no-sandbox','--enable-unsafe-swiftshader']});
const metrics=[];
for(const width of [320,390,768,1024,1440]){
 const context=await browser.newContext({viewport:{width,height:width<640?844:1000},hasTouch:width<1024,reducedMotion:'reduce'});
 await context.route('**/*',r=>{
  const url=new URL(r.request().url());
  if(url.origin!==baseUrl && url.protocol!=='data:') {
    if(r.request().resourceType()==='image' && allowedOriginals.has(url.href))return r.continue();
    return r.abort();
  }
  if(!url.pathname.startsWith('/api/'))return r.continue();
  if(url.pathname.endsWith('/session'))return r.fulfill({json:{session_id:'isolated-local-design',name:'QA'}});
  if(url.pathname.endsWith('/products'))return r.fulfill({json:{products:[]}});
  if(url.pathname.endsWith('/merchant-partners'))return r.fulfill({json:{partners:[]}});
  if(url.pathname.endsWith('/analytics/events'))return r.fulfill({json:{ok:true}});
  return r.fulfill({status:503,json:{detail:'Isolated offer-unavailable fixture'}});
 });
 const page=await context.newPage();
 const errors=[];page.on('pageerror',e=>errors.push(e.message));
 for(const [name,route]of [['home','/'],['catalog','/duft'],['black-opium','/duft/yves-saint-laurent-black-opium']]){
  const response=await page.goto(baseUrl+route,{waitUntil:'load'});
  await chooseMeasurement(page,'denied');
  await page.locator('h1').first().waitFor({state:'visible'});
  await page.evaluate(async()=>{
    await document.fonts.ready;
    await Promise.all([...document.images].map(async image=>{
      image.loading='eager';
      await Promise.race([image.decode().catch(()=>{}),new Promise(resolve=>setTimeout(resolve,8000))]);
    }));
  });
  const originalImages=page.locator(name==='home'?'.vr-feature-photo img':name==='catalog'?'[data-dufynd-directory-original] img':'.dufynd-fragrance-stage-shell img');
  await originalImages.evaluateAll(async images=>{
    if(!images.length)throw new Error('Missing approved featured original');
    await Promise.all(images.map(image=>Promise.race([image.decode(),new Promise((_,reject)=>setTimeout(()=>reject(new Error('Original decode timed out')),8000))])));
    if(images.some(image=>!image.complete || image.naturalWidth===0))throw new Error('Original did not load');
  });
  await page.screenshot({path:`${outputDir}/${name}-${width}-first.png`});
  const info=await page.evaluate(()=>({viewport:innerWidth,overflow:Math.max(0,document.documentElement.scrollWidth-innerWidth,...[...document.querySelectorAll('.panel-scroll')].map(e=>e.scrollWidth-e.clientWidth)),scrollHeight:document.querySelector('.panel-scroll')?.scrollHeight??document.documentElement.scrollHeight,search:document.querySelector('.wow-search')?.getBoundingClientRect().toJSON(),catalogHero:document.querySelector('.dufynd-catalog-discovery-hero')?.getBoundingClientRect().toJSON(),photo:document.querySelector('.dufynd-fragrance-stage-shell')?.getBoundingClientRect().toJSON(),images:[...document.images].filter(i=>i.getBoundingClientRect().width>0).map(i=>({src:i.getAttribute('src'),width:i.naturalWidth,height:i.naturalHeight}))}));
  metrics.push({name,width,status:response.status(),errors:[...errors],...info});
  if(width===390||width===1440){
   if(name==='home'){
    const scroll=page.locator('.panel-scroll').filter({has:page.locator('.wow-home')});
    for(const [part,selector]of [['selection','.wow-selection'],['atlas','[data-scent-atlas]'],['audience','.wow-audiences']]){
      const element=page.locator(selector);await element.scrollIntoViewIfNeeded();await element.screenshot({path:`${outputDir}/${name}-${width}-${part}.png`});
    }
    if(await scroll.count()){await scroll.evaluate(el=>{el.scrollTop=0;});}
   } else await page.screenshot({path:`${outputDir}/${name}-${width}-full.png`,fullPage:true});
  }
 }
 await context.close();
}
await browser.close();await writeFile(`${outputDir}/metrics.json`,JSON.stringify({fixtureOnly:true,realApiRequests:0,affiliateClicks:0,metrics},null,2));
console.log(JSON.stringify(metrics.map(({name,width,status,overflow,scrollHeight,search,catalogHero})=>({name,width,status,overflow,scrollHeight,searchBottom:search?search.y+search.height:null,catalogHero:catalogHero?.height})),null,2));
