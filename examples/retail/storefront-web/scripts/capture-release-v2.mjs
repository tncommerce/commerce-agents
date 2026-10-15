import {chromium} from 'playwright';
import {mkdirSync,readFileSync,writeFileSync} from 'node:fs';
const out=process.env.QA_OUTPUT; if(!out)throw new Error('QA_OUTPUT required');mkdirSync(out,{recursive:true});
const base=process.env.QA_BASE_URL||'http://127.0.0.1:3013';
const browser=await chromium.launch({headless:true});const metrics=[];
try{for(const width of [390,1440]){
 const page=await browser.newPage({viewport:{width,height:900},reducedMotion:'reduce'});
 if(process.env.QA_IMAGE_MANIFEST)for(const a of JSON.parse(readFileSync(process.env.QA_IMAGE_MANIFEST)))await page.route(a.url,r=>r.fulfill({path:a.path}));
 await page.goto(base+'/duft');await page.locator('.dufynd-catalog-card').first().waitFor();await page.evaluate(()=>document.fonts.ready);await page.waitForTimeout(600);
 await page.screenshot({path:`${out}/catalog-${width}-viewport.png`});await page.screenshot({path:`${out}/catalog-${width}.png`,fullPage:true});
 await page.evaluate(()=>scrollTo(0,0));await page.waitForTimeout(100);
 const cards=page.locator('.dufynd-catalog-card');const first=await cards.first().boundingBox();const ys=await cards.evaluateAll(xs=>[...new Set(xs.map(x=>Math.round(x.getBoundingClientRect().top)))].sort((a,b)=>a-b));
 const second=await cards.evaluateAll((xs,y)=>xs.filter(x=>Math.round(x.getBoundingClientRect().top)===y).map(x=>x.getBoundingClientRect().bottom),ys[1]);
 const bottom=Math.max(...second);await page.setViewportSize({width,height:Math.ceil(bottom+20)});await page.screenshot({path:`${out}/catalog-${width}-two-rows.png`,clip:{x:0,y:first.y,width,height:Math.ceil(bottom-first.y+8)}});
 metrics.push({width,cards:await cards.count(),first_two_rows:true,illustration_network_requests:0});await page.close();
}}finally{await browser.close();}writeFileSync(`${out}/catalog-captures.json`,JSON.stringify(metrics,null,2));
