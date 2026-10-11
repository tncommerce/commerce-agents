import assert from 'node:assert/strict';
import {chromium} from 'playwright';
import {writeFileSync,mkdirSync} from 'node:fs';
const base=process.env.QA_BASE_URL||'http://127.0.0.1:3013',out=process.env.QA_OUTPUT||'/tmp/dufynd-brand-qa';mkdirSync(out,{recursive:true});
const browser=await chromium.launch();const report=[];
try{for(const width of [320,390,768,1440]){
const page=await browser.newPage({viewport:{width,height:900},reducedMotion:'reduce'});const errors=[];page.on('pageerror',e=>errors.push(e.message));
await page.goto(base+'/marken');const links=await page.locator('[data-brand-slug]').evaluateAll(xs=>xs.map(x=>({href:x.getAttribute('href'),count:Number(x.querySelector('small').textContent.match(/\d+/)[0])})));
assert.equal(new Set(links.map(l=>l.href)).size,links.length);assert.equal(links.reduce((n,l)=>n+l.count,0),37);
assert.ok((await page.locator('meta[name=robots]').getAttribute('content')).includes('noindex'));
await page.getByRole('searchbox').fill('CHANEL');assert.equal(await page.locator('[data-brand-slug]').count(),1);await page.getByRole('searchbox').fill('');
if([390,1440].includes(width))await page.screenshot({path:`${out}/brands-${width}.png`,fullPage:true});
for(const l of links){const res=await page.goto(base+l.href);assert.equal(res.status(),200);assert.equal(Number(await page.locator('[data-brand-public-count]').getAttribute('data-brand-public-count')),l.count);assert.equal(await page.locator('.dufynd-catalog-card').count(),Math.min(12,l.count));assert.ok(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth));}
await page.goto(base+'/marken/chanel');const href=await page.locator('.dufynd-catalog-card a[href^="/duft/"]').first().getAttribute('href');assert.ok(href);await page.locator('.dufynd-catalog-card a[href^="/duft/"]').first().click();assert.equal(new URL(page.url()).pathname,href);
assert.deepEqual(errors,[]);report.push({width,brands:links.length,public_products:37,status:'passed'});await page.close();
}}finally{await browser.close();}writeFileSync(`${out}/brands-qa.json`,JSON.stringify(report,null,2));console.log(JSON.stringify(report));
