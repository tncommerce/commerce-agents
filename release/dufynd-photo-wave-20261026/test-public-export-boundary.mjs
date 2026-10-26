// Run from a built storefront-web directory. Mutates only the local generated
// registry and restores its exact bytes even if an assertion fails.
import assert from 'node:assert/strict';
import {readFileSync,writeFileSync} from 'node:fs';
import {spawnSync} from 'node:child_process';
const file='lib/generated/original-photos.json',bytes=readFileSync(file),baseline=JSON.parse(bytes);
const id='SC-ESSENTIAL-PARFUMS-BOIS-IMPERIAL-100';
assert.ok(baseline.some(p=>p.product_id===id));
const run=()=>spawnSync(process.execPath,['scripts/verify-public-export.mjs'],{encoding:'utf8',env:{...process.env,DUFYND_CATALOG_REVIEW:'0'}});
let checked=0;
try {
 const positive=run();assert.equal(positive.status,0,positive.stderr);checked++;
 for(const mutation of ['missing','hash','url','size','rights']) {
  const registry=structuredClone(baseline),photo=registry.find(p=>p.product_id===id);
  if(mutation==='missing')registry.splice(registry.indexOf(photo),1);
  if(mutation==='hash')photo.image_sha256='0'.repeat(64);
  if(mutation==='url')photo.url='https://example.invalid/not-this-source.png';
  if(mutation==='size')photo.volume_ml=50;
  if(mutation==='rights')photo.rights_basis_id='unverified';
  writeFileSync(file,JSON.stringify(registry));
  const rejected=run();assert.notEqual(rejected.status,0,mutation);assert.match(rejected.stderr,/Private merchant photo leaked into normal export/);checked++;
 }
} finally {writeFileSync(file,bytes);}
assert.equal(run().status,0,'Exact original registry restored');
console.log(JSON.stringify({status:'PASS',checks:checked,negative_cases:5,registry_restored:true}));
