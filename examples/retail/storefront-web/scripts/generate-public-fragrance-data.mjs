import { readFileSync, writeFileSync, mkdirSync } from 'node:fs';
const read = name => JSON.parse(readFileSync(new URL(`../../data/${name}`, import.meta.url), 'utf8'));
// No third-party community metrics have a documented public reuse grant.
// Sanitize before bundling: hiding the UI alone would still ship the source data.
export function publicCatalogRow(row) {
  const clean = structuredClone(row);
  delete clean.review_count;
  delete clean.rating;
  for (const key of Object.keys(clean.attributes || {})) {
    if (/community|rating|rank|longevity|projection/i.test(key)) delete clean.attributes[key];
  }
  return clean;
}
export function publicSourceRow(row) {
  const keys = ['product_id','brand','name','concentration','volume_ml','release_year','notes','visuals','validation','relationships','market','fragrance_profile'];
  const clean = Object.fromEntries(keys.filter(k => row[k] !== undefined).map(k => [k, row[k]]));
  const c = row.classification || {};
  clean.classification = {scentai_target_groups:c.scentai_target_groups,role:c.role,cluster_id:c.cluster_id};
  clean.community = {source:'',rating_10:null,rating_count:0,longevity_10:null,projection_10:null,provisional:false};
  return clean;
}
const dir = new URL('../lib/generated/', import.meta.url);
mkdirSync(dir, {recursive:true});
writeFileSync(new URL('public-catalog.json',dir), JSON.stringify({products:read('catalog.json').products.map(publicCatalogRow)},null,2)+'\n');
writeFileSync(new URL('public-fragrances.json',dir), JSON.stringify({products:read('scentai_products.json').products.map(publicSourceRow)},null,2)+'\n');
console.log('Public fragrance projection: third-party community metrics excluded.');
const approved = [...read('dufynd_approved_feed_image_candidates.json').candidates,...read('dufynd_rights_cleared_image_candidates.json').candidates]
  .filter(c=>c.review_status==='approved' && c.exact_variant_verified===true && c.rights_status==='verified_for_publisher_service')
  .map(c=>({product_id:c.product_id,url:c.image_url,volume_ml:c.volume_ml,rights_basis_id:c.rights_basis_id,
    ...Object.fromEntries(['width','height','image_sha256'].filter(key=>c[key]!==undefined).map(key=>[key,c[key]]))}));
writeFileSync(new URL('original-photos.json',dir),JSON.stringify(approved,null,2)+'\n');
