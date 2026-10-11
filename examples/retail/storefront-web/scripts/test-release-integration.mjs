/** Isolated build fixture only. NEVER writes authorizations in the actual worktree. */
import assert from 'node:assert/strict';
import {mkdtempSync,mkdirSync,cpSync,readFileSync,writeFileSync,symlinkSync,existsSync} from 'node:fs';
import {tmpdir} from 'node:os';
import path from 'node:path';
import {fileURLToPath} from 'node:url';
import {spawnSync,spawn} from 'node:child_process';
import {chromium} from 'playwright';
import {releaseState,readData} from './release-gate.mjs';
const web=fileURLToPath(new URL('..',import.meta.url));
const actualAuth=readFileSync(new URL('../../data/dufynd_release_authorizations.json',import.meta.url),'utf8');
const candidates=releaseState().filter(r=>r.state.blockers.length===1&&r.state.blockers[0]==='OWNER_REVIEW');
assert.equal(candidates.length,27,'Expected complete 27-product candidate wave');
const root=mkdtempSync(path.join(tmpdir(),'dufynd-release-fixture-'));const fixture=path.join(root,'examples/retail/storefront-web');mkdirSync(fixture,{recursive:true});
for(const entry of ['app','components','lib','scripts','public','next.config.ts','next-env.d.ts','tsconfig.json','package.json','postcss.config.mjs'])cpSync(path.join(web,entry),path.join(fixture,entry),{recursive:true});
cpSync(path.resolve(web,'../data'),path.join(root,'examples/retail/data'),{recursive:true});
cpSync(path.resolve(web,'../../web-shared'),path.join(root,'examples/web-shared'),{recursive:true});
symlinkSync(path.resolve(web,'../../node_modules'),path.join(root,'examples/node_modules'),'dir');
const auth=readData('dufynd_release_authorizations.json');
auth.approvals=candidates.map(({p,state})=>({product_id:p.product_id,evidence_sha256:state.evidence_sha256,render_sha256:state.render_sha256,qa_sha256:state.qa_sha256,variant_approved:true,illustration_approved:true,publication_approved:true,indexing_approved:false,approved_by:'ISOLATED TEST FIXTURE — NOT OWNER',approved_at:'2026-10-11',approval_reference:'fixture://not-valid-outside-temporary-test'}));
writeFileSync(path.join(root,'examples/retail/data/dufynd_release_authorizations.json'),JSON.stringify(auth,null,2));
const build=spawnSync('npm',['run','build','--','--webpack'],{cwd:fixture,env:{...process.env,DUFYND_CATALOG_REVIEW:'0'},encoding:'utf8',maxBuffer:20*1024*1024});
writeFileSync(path.join(root,'build.log'),build.stdout+build.stderr);
if(build.status!==0)throw Error(`Isolated fixture build failed: ${root}\n${(build.stdout+build.stderr).slice(-5000)}`);
const generated=JSON.parse(readFileSync(path.join(fixture,'lib/generated/released-profiles.json'),'utf8')).profiles;assert.equal(generated.length,27);
assert.ok(!existsSync(path.join(fixture,'out/review')));
const sitemap=readFileSync(path.join(fixture,'out/sitemap.xml'),'utf8');
assert.ok(candidates.every(({p})=>!sitemap.includes(p.seo.public_path+'<')),'No indexing implied by publication');
const server=spawn(process.execPath,['scripts/serve-static-export.mjs','--root','out','--port','3014'],{cwd:fixture,stdio:'ignore'});
const browser=await chromium.launch();const checks=[];
try{const page=await browser.newPage({viewport:{width:390,height:900},reducedMotion:'reduce'});
await page.goto('http://127.0.0.1:3014/marken');const count=await page.locator('[data-brand-slug] small').allTextContents();assert.equal(count.reduce((n,s)=>n+Number(s.match(/\d+/)[0]),0),64);
for(const {p} of candidates){const res=await page.goto('http://127.0.0.1:3014'+p.seo.public_path);assert.equal(res.status(),200);assert.equal(await page.locator('[data-product-id]').getAttribute('data-product-id'),p.product_id);assert.equal(await page.locator('[data-review-product]').count(),0);assert.ok((await page.locator('link[rel=canonical]').getAttribute('href')).endsWith(p.seo.public_path));assert.ok((await page.locator('meta[name=robots]').getAttribute('content')).includes('noindex'));assert.equal(await page.locator('a[href*="/review/"]').count(),0);assert.equal(await page.locator('a[href*="clickout"],a[href*="awin"]').count(),0);assert.ok(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth));checks.push(p.product_id);}
const held=await page.goto('http://127.0.0.1:3014/duft/hugo-boss-bottled-absolu-100');assert.equal(held.status(),404);
}finally{await browser.close();server.kill();assert.equal(readFileSync(new URL('../../data/dufynd_release_authorizations.json',import.meta.url),'utf8'),actualAuth,'Actual approvals untouched');}
const result={mode:'isolated_fixture_not_owner_authorization',public_profiles:64,promoted_pages_checked:checks.length,product_ids:checks,conflicting_variant_http:404,review_routes_exported:false,new_sitemap_entries:0,actual_authorizations_changed:false,fixture_directory:root};
const output=process.env.QA_OUTPUT;if(output){mkdirSync(output,{recursive:true});writeFileSync(path.join(output,'promotion-fixture.json'),JSON.stringify(result,null,2)+'\n');}console.log(JSON.stringify(result));
