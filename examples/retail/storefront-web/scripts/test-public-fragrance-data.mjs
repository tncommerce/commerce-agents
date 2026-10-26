import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import {publicCatalogRow,publicSourceRow} from './generate-public-fragrance-data.mjs';
const privateRow={product_id:'SC-TEST',community:{source:'Parfumo',rating_10:9.9,rating_count:12345,rank:1},commercial:{community_demand:99},classification:{community_category:'top',scentai_target_groups:['unisex']},notes:{top:['bergamot']}};
const published=publicSourceRow(privateRow);
assert.equal(published.community.rating_10,null);
assert.equal(published.community.rating_count,0);
assert.equal(published.community.source,'');
assert.ok(!JSON.stringify(published).includes('12345'));
assert.ok(!published.commercial);
assert.equal(privateRow.community.rating_count,12345,'Source stays intact');
const c=publicCatalogRow({product_id:'SC-TEST',review_count:500,attributes:{community_rating_10:'9.5',longevity:'8',volume_ml:'100'}});
assert.equal(c.review_count,undefined);
assert.deepEqual(c.attributes,{volume_ml:'100'});
const source=JSON.parse(readFileSync(new URL('../lib/generated/public-fragrances.json',import.meta.url),'utf8'));
assert.ok(source.products.every(p=>p.community.rating_10===null&&p.community.rating_count===0));
const originals=JSON.parse(readFileSync(new URL('../lib/generated/original-photos.json',import.meta.url),'utf8'));
const expectedOriginalIds = [
  "SC-PDM-DELINA-EDP-75",
  "SC-YSL-BLACK-OPIUM-EDP-90",
  "SC-YSL-LIBRE-EDP-90",
  "SC-LANCOME-LA-VIE-EST-BELLE-EDP-100",
  "SC-ESSENTIAL-PARFUMS-BOIS-IMPERIAL-100",
  "SC-ARMANI-SWY-INTENSELY-100",
  "SC-PDM-LAYTON-125",
  "SC-VALENTINO-BORN-IN-ROMA-INTENSE-100",
  "SC-PDM-ALTHAIR-125",
  "SC-RABANNE-1-MILLION-EDT-100"
];
assert.deepEqual(originals.map(p=>p.product_id).sort(), expectedOriginalIds.sort());
const sourceById=new Map(source.products.map(p=>[p.product_id,p]));
for (const image of originals.filter(p=>p.width !== undefined)) {
  assert.ok(Number.isInteger(image.width)&&image.width>0&&Number.isInteger(image.height)&&image.height>0);
  assert.match(image.image_sha256,/^[a-f0-9]{64}$/);
  const visual=sourceById.get(image.product_id)?.visuals.find(v=>v.role==='primary'&&v.url===image.url);
  assert.ok(visual&&visual.fidelity_status==='verified'&&visual.source_merchant_id==='top-parfuemerie');
  assert.equal(visual.image_sha256,image.image_sha256);
  assert.equal(visual.width,image.width);assert.equal(visual.height,image.height);
  assert.ok(visual.source_page_url.startsWith('https://www.topparfuemerie.de/'));
  assert.equal(visual.rights_checked_at,'2026-09-28');
}
assert.ok(originals.every(a=>a.url.startsWith('https://')&&a.rights_basis_id&&a.volume_ml));
console.log('Public boundary: third-party metrics stripped, private sources intact, 10 exact approved photographs; source dimensions and Top merchant binding verified.');
