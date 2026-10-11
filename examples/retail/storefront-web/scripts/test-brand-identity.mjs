import assert from 'node:assert/strict';
import {publicRows} from './public-catalog-summary.mjs';
import {readFileSync} from 'node:fs';
import vm from 'node:vm';
import ts from 'typescript';
const source=readFileSync(new URL('../lib/brandIdentity.ts',import.meta.url),'utf8');
const code=ts.transpileModule(source,{compilerOptions:{module:ts.ModuleKind.CommonJS}}).outputText;
const context={exports:{}};vm.runInNewContext(code,context);const {canonicalBrand,brandKey}=context.exports;
assert.equal(canonicalBrand(' CHANEL '),'Chanel');assert.equal(canonicalBrand('chanel'),'Chanel');assert.equal(canonicalBrand('Chanel'),'Chanel');
assert.equal(canonicalBrand('YSL'),'Yves Saint Laurent');assert.equal(canonicalBrand('chloe'),'Chloé');assert.equal(brandKey(' CHLOÉ '),brandKey('Chloe'));
const facts=JSON.parse(readFileSync(new URL('../lib/generated/public-fragrances.json',import.meta.url))).products;
const blocked=new Set(facts.filter(p=>p.validation?.blockers?.some(x=>String(x).trim())).map(p=>p.product_id));
const rows=JSON.parse(readFileSync(new URL('../lib/generated/public-catalog.json',import.meta.url))).products.filter(p=>p.product_id.startsWith('SC-')&&p.category==='fragrance'&&p.in_stock!==false&&!blocked.has(p.product_id));
const counts=new Map();for(const p of publicRows){const name=canonicalBrand(p.brand||'');counts.set(name,(counts.get(name)||0)+1);}
assert.equal([...counts.values()].reduce((a,b)=>a+b,0),publicRows.length);
assert.equal(new Set([...counts.keys()].map(brandKey)).size,counts.size);
console.log(`Brand identities verified: ${counts.size} brands, ${publicRows.length} public products; aliases do not add products.`);
