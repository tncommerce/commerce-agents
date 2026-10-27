import assert from 'node:assert/strict';
import {mkdtempSync,readFileSync,writeFileSync,existsSync,mkdirSync,rmSync} from 'node:fs';
import {tmpdir} from 'node:os';
import {pathToFileURL} from 'node:url';
import {createHash} from 'node:crypto';
import {preparePhotoReview} from './prepare-photo-review.mjs';
const source=JSON.parse(readFileSync(new URL('../../data/dufynd_photo_integration_review.json',import.meta.url),'utf8'));
const root=mkdtempSync(`${tmpdir()}/dufynd-photo-gate-`),destination=pathToFileURL(`${root}/photos/`);
const bytes=Buffer.from('fixed reviewed bytes');
const item={...source.items[0],image_sha256:createHash('sha256').update(bytes).digest('hex')};
let requests=0;
const fetchSource=async()=>{requests++;return {ok:true,arrayBuffer:async()=>bytes};};
try {
  mkdirSync(destination);writeFileSync(new URL('stale.png',destination),'stale');
  await preparePhotoReview({enabled:false,destination,manifest:source,fetchSource});
  assert.equal(requests,0);assert.equal(existsSync(destination),false,'Normal build removes stale review images without fetching');
  await preparePhotoReview({enabled:true,destination,manifest:{items:[item]},fetchSource});
  assert.deepEqual(readFileSync(new URL(`${item.merchant_product_id}-${item.image_sha256}.png`,destination)),bytes);
  for(const mutation of [
    {owner_visual_approved:false},{exact_variant_verified:false},{publication_authorized:true},
    {offer_activation_authorized:true},{placement:'independent_product_advertising'},
    {merchant_id:'perfumetrader'},{source_advertiser_id:'11672'},{source_feed_id:'other'},
    {rights_basis_id:'unverified'},{image_url:'https://example.com/asset.png'},
    {merchant_product_id:'../escape'},
  ]) {
    const before=requests;
    await assert.rejects(preparePhotoReview({enabled:true,destination,manifest:{items:[{...item,...mutation}]},fetchSource}),/Invalid private photo source/);
    assert.equal(requests,before,'Invalid gate rejected before download');
    assert.equal(existsSync(destination),false,'No partial review assets survive failure');
  }
  await assert.rejects(preparePhotoReview({enabled:true,destination,manifest:{items:[{...item,image_sha256:'a'.repeat(64)}]},fetchSource}),/Photo bytes changed/);
  assert.equal(existsSync(destination),false);
  assert.equal(source.items.length,6);
  assert.equal(new Set(source.items.map(x=>x.product_id)).size,6);
  assert.ok(source.items.some(x=>x.product_id==='SC-PDM-ALTHAIR-125'&&x.volume_ml===125&&x.owner_visual_approved));
  const route=readFileSync(new URL('../app/duft/[slug]/page.tsx',import.meta.url),'utf8');
  assert.ok(!route.includes('merchantPhotoReview'),'Public route cannot opt into merchant preview');
  console.log('Photo integration gates: default-off cleanup, exact bytes, 11 negative permission/source cases and public-route separation passed.');
} finally {rmSync(root,{recursive:true,force:true});}
