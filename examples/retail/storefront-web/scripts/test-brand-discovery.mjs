// Offline behavior against the production catalog; no HTTP or analytics.
import assert from 'node:assert/strict';
import fs from 'node:fs';
import path from 'node:path';
import vm from 'node:vm';
import {createRequire} from 'node:module';
import ts from 'typescript';
const root=path.resolve(import.meta.dirname,'..');
const nativeRequire=createRequire(import.meta.url);
function loader(siteIndexable=false){
  const cache=new Map();
  function load(file){
    if(!path.extname(file))file+=fs.existsSync(file+'.ts')?'.ts':'.tsx';
    if(cache.has(file))return cache.get(file).exports;
    if(file.endsWith('.json'))return JSON.parse(fs.readFileSync(file,'utf8'));
    if(file.endsWith('.css'))return new Proxy({},{get:(_,name)=>String(name)});
    if(file.endsWith('/lib/site.ts'))return {SITE_URL:'https://dufynd.example',SITE_INDEXABLE:siteIndexable};
    const mod={exports:{}};cache.set(file,mod);
    const code=ts.transpileModule(fs.readFileSync(file,'utf8'),{compilerOptions:{target:ts.ScriptTarget.ES2020,module:ts.ModuleKind.CommonJS,jsx:ts.JsxEmit.ReactJSX,esModuleInterop:true}}).outputText;
    vm.runInNewContext(code,{module:mod,exports:mod.exports,process,URL,console,require(name){
      if(name==='next/navigation')return {notFound(){throw Error('NOT_FOUND');}};
      // No client render or side effects needed to execute server route contracts.
      if(name.startsWith('@/components/'))return {__esModule:true,default:()=>null};
      if(name.startsWith('@/'))return load(path.join(root,name.slice(2)));
      if(name.startsWith('.'))return load(path.resolve(path.dirname(file),name));
      return nativeRequire(name);
    }},{filename:file});
    return mod.exports;
  }
  return rel=>load(path.join(root,rel));
}
const load=loader();
const {LIVE_FRAGRANCES}=load('lib/fragranceCatalog');
const {PUBLIC_BRANDS,fragrancesForBrand}=load('lib/brands');
const {canonicalBrand,brandSlug}=load('lib/brandIdentity');
assert.equal(canonicalBrand(' CHANEL '),'Chanel');
assert.equal(brandSlug('YSL'),brandSlug('Yves Saint Laurent'));
assert.equal(brandSlug('CHLOÉ'),brandSlug('Chloe'));
assert.equal(new Set(PUBLIC_BRANDS.map(b=>b.slug)).size,PUBLIC_BRANDS.length);
assert.equal(PUBLIC_BRANDS.reduce((n,b)=>n+b.count,0),LIVE_FRAGRANCES.length);
const listed=PUBLIC_BRANDS.flatMap(b=>fragrancesForBrand(b.slug));
assert.equal(JSON.stringify(listed.map(f=>f.product_id).sort()),JSON.stringify(LIVE_FRAGRANCES.map(f=>f.product_id).sort()));
const source=JSON.parse(fs.readFileSync(path.join(root,'../data/scentai_products.json')));
const blocked=source.products.filter(p=>p.validation?.blockers?.some(x=>String(x||'').trim()));
assert.ok(blocked.length>0,'exercise existing held identities');
for(const row of blocked)assert.ok(!listed.some(f=>f.product_id===row.product_id));
for(const flag of [false,true]){
  const module=loader(flag);
  const route=module('app/marken/[slug]/page');
  assert.equal(route.dynamicParams,false);
  assert.deepEqual(JSON.parse(JSON.stringify(route.generateStaticParams())),JSON.parse(JSON.stringify(PUBLIC_BRANDS.map(b=>({slug:b.slug})))));
  assert.equal(module('app/marken/page').metadata.robots.index,false);
  assert.equal(module('app/marken/page').metadata.robots.follow,flag);
  for(const brand of PUBLIC_BRANDS){
    const meta=await route.generateMetadata({params:Promise.resolve({slug:brand.slug})});
    assert.equal(meta.alternates.canonical,`/marken/${brand.slug}`);
    assert.equal(meta.robots.index,false);
    assert.equal(meta.robots.follow,flag);
    assert.ok(meta.title.startsWith(brand.name));
    assert.equal(fragrancesForBrand(brand.slug).length,brand.count);
  }
  await assert.rejects(route.default({params:Promise.resolve({slug:'unapproved-brand'})}),/NOT_FOUND/);
}
console.log(JSON.stringify({status:'PASS',public_products:LIVE_FRAGRANCES.length,brands:PUBLIC_BRANDS.length,blocked_products:blocked.length,indexing_approved:false}));
