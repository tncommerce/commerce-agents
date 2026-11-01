import assert from 'node:assert/strict';
import './test-manufacturer-source-intake.mjs';
import {buildGrowth,inputs,boundedBatch,variantKey,validateEvidence} from './catalog-growth.mjs';
import {readData} from './release-gate.mjs';
const data=inputs(),snapshot=JSON.stringify({...data,publicIds:[...data.publicIds]});
const result=buildGrowth(data);
assert.equal(result.counts.exact_sku_union,83);
assert.equal(result.counts.canonical_staging_overlap,5);
// The original qualified cohort and the owner-signed fact-only release are
// distinct. Never mistake 20 already-public profiles for pending candidates.
const originallyPublic=data.canonical.filter(row=>
  String(row.product_id||'').startsWith('SC-') &&
  !(row.validation?.blockers||[]).some(v=>String(v||'').trim())
).map(row=>row.product_id);
const approvals=readData('dufynd_release_authorizations.json').approvals;
const publishedApprovals=approvals.filter(a=>a.publication_approved===true&&a.indexing_approved===true);
const approvedIds=new Set(publishedApprovals.map(a=>a.product_id));
assert.equal(originallyPublic.length,37,'original qualified public cohort');
assert.equal(approvedIds.size,20,'only owner-authorized wave one is public');
const exactPublicIds=new Set([...originallyPublic,...approvedIds]);
assert.equal(exactPublicIds.size,originallyPublic.length+approvedIds.size,'duplicate public SKU');
assert.deepEqual([...data.publicIds].sort(),[...exactPublicIds].sort(),
  'catalog-growth must read only actual qualified and approved public IDs');
const waveTwo=readData('dufynd_facts_wave_02_review.json');
assert.equal(waveTwo.public_release_authorized,false);
assert.ok(waveTwo.profiles.every(row=>!data.publicIds.has(row.product_id)),
  'held second wave was counted as published');
assert.equal(result.counts.existing_public,exactPublicIds.size);
assert.ok(result.counts.existing_review_pages>=28);
assert.ok(result.counts.existing_owner_candidate_wave<=result.counts.existing_review_pages-1);
assert.equal(result.counts.newly_facts_qualified,13);
assert.equal(result.next_page_batch.count,41-result.counts.existing_review_pages);
assert.equal(result.counts.additional_stages.owner_approved,0);
assert.equal(result.counts.additional_stages.indexed,null);
assert.deepEqual(result.milestones.map(m=>m.public_delta),
  [50,75,100,101].map(target=>Math.max(0,target-exactPublicIds.size)),
  'milestones may never double-count already released facts-only profiles');
assert.equal(JSON.stringify({...data,publicIds:[...data.publicIds]}),snapshot,'read-only inputs');
assert.equal(new Set(result.products.map(p=>p.variant_key)).size,83);
const clone=()=>structuredClone(data);
let bad=clone();bad.staging.push(bad.staging[0]);assert.throws(()=>buildGrowth(bad),/duplicate/);
bad=clone();bad.staging[0].volume_ml=1;assert.throws(()=>buildGrowth(bad),/variant|same_id/);
bad=clone();bad.evidence.products[0].volume_ml=50;assert.throws(()=>buildGrowth(bad),/variant/);
for(const key of ['price','rating','gtin','affiliate_url','image_url']){bad=clone();bad.evidence.products[0][key]='invented';assert.throws(()=>buildGrowth(bad),/unsupported/);}
bad=clone();bad.evidence.publication_authorized=true;assert.throws(()=>buildGrowth(bad),/scope/);
bad=clone();bad.evidence.products[0].source_url='https://jeanpaulgaultier.com.evil.example/p';assert.throws(()=>buildGrowth(bad),/manufacturer/);
bad=clone();bad.evidence.products[0].product_id=data.facts[0].product_id;assert.throws(()=>buildGrowth(bad),/variant|already/);
bad=clone();bad.evidence.products[0].notes={key:['']};assert.throws(()=>validateEvidence(bad.evidence,bad.staging,bad.facts),/notes/);
const base={brand:'CHANEL',name:'Example',concentration:'Eau de Parfum',volume_ml:100};
assert.equal(variantKey(base),variantKey({...base,brand:'Chanel'}));
assert.notEqual(variantKey(base),variantKey({...base,volume_ml:50}));
assert.notEqual(variantKey(base),variantKey({...base,concentration:'Eau de Parfum Intense'}));
assert.notEqual(variantKey(base),variantKey({...base,name:'Example (2025)'}));
const first=boundedBatch(result,{limit:13});assert.equal(first.selected.length,13);
const second=boundedBatch(result,{limit:24,completed:first.selected});assert.equal(second.selected.some(id=>first.selected.includes(id)),false);
assert.throws(()=>boundedBatch(result,{limit:0}),/limit/);
assert.throws(()=>boundedBatch(result,{completed:['not-a-product']}),/checkpoint/);
assert.equal(boundedBatch(result).publication_authorized,false);
console.log('Catalog growth: 83 exact IDs, bounded resume, source/variant/default-deny and dedupe regression checks passed.');
