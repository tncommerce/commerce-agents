/** Actual first-two-row captures; no affiliate navigation or external writes. */
import {chromium} from 'playwright';
import {mkdirSync,writeFileSync} from 'node:fs';
import assert from 'node:assert/strict';
const base=process.env.QA_BASE_URL||'http://127.0.0.1:3013';
const out=process.env.QA_OUTPUT||'/tmp/dufynd-catalog-rows';mkdirSync(out,{recursive:true});
const browser=await chromium.launch();const report=[];
try{for(const width of [320,390,768,1440]){
 const page=await browser.newPage({viewport:{width,height:900},reducedMotion:'reduce'});
 await page.route('**/api/**',r=>r.fulfill({json:{ok:true,session_id:'local-qa'}}));
 await page.goto(base+'/duft');await page.evaluate(()=>document.fonts.ready);
 const cards=page.locator('.dufynd-catalog-card');await cards.first().waitFor();
 const boxes=await cards.evaluateAll(xs=>xs.map(x=>{const r=x.getBoundingClientRect();return {x:r.x,y:r.y,width:r.width,height:r.height}}));
 const tops=[...new Set(boxes.map(b=>Math.round(b.y)))].sort((a,b)=>a-b).slice(0,2);
 const first=boxes.filter(b=>tops.includes(Math.round(b.y)));
 assert.ok(first.length>=2);assert.ok(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth));
 const bottom=Math.ceil(Math.max(...first.map(b=>b.y+b.height)));
 const png=await page.screenshot({path:`${out}/catalog-${width}-two-rows.png`,fullPage:true,clip:{x:0,y:0,width,height:bottom+24}});
 assert.equal(png.readUInt32BE(16),width);assert.equal(png.readUInt32BE(20),bottom+24,'Capture must include both rows, not only the viewport');
 report.push({width,rows:2,cards:first.length,status:'passed',height:bottom+24});await page.close();
}}finally{await browser.close();}
writeFileSync(`${out}/catalog-rows-qa.json`,JSON.stringify(report,null,2)+'\n');console.log(JSON.stringify(report));
