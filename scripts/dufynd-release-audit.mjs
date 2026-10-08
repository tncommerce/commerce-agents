import fs from 'node:fs';
const read = name => JSON.parse(fs.readFileSync(`examples/retail/data/${name}.json`, 'utf8'));
const staging = read('scentai_catalog_staging').products;
const source = read('scentai_products').products;
const catalog = read('catalog').products;
const live = catalog.filter(p => p.product_id.startsWith('SC-') && p.category === 'fragrance' && p.in_stock !== false && !source.find(s => s.product_id === p.product_id)?.validation?.blockers?.some(b => String(b || '').trim()));
const ids = new Set(live.map(p => p.product_id));
const manifests = [1,2,3,4,5].map(i => read(`scentai_release_batch_0${i}`));
const audit = p => ({
  product_id: p.product_id, brand: p.brand, name: p.name,
  already_public: ids.has(p.product_id),
  image_url: p.media?.image_url ?? null,
  image_status: p.media?.image_status ?? null,
  purchase_destination_status: p.commerce?.live_offer_status ?? null,
  merchant_coverage_count: p.commerce?.merchant_coverage_count ?? 0,
  community_provisional: p.community?.provisional ?? null,
  recommendation_customer_facing: p.fragrance_profile?.recommendation_profile?.customer_facing ?? null,
  stored_blockers: p.validation?.blockers ?? [],
  disposition: ids.has(p.product_id) ? 'already_public_do_not_reactivate' : 'owner_evidence_required_no_activation',
});
const candidates = staging.filter(p => p.classification?.target_groups?.includes('women') && !ids.has(p.product_id)).slice(0, 10).map(audit);
const report = {
  checked_at: '2026-10-08', source: 'repository fields; no image rights or purchase destination inferred',
  catalog_rows: catalog.length, public_fragrances: live.length, staging_rows: staging.length,
  staging_without_image_url: staging.filter(p => !p.media?.image_url).length,
  activation_performed: false,
  candidates,
  manifests: manifests.map(m => ({
    release_id: m.release_id, required_gates: m.required_gates,
    products: m.product_ids.map(id => {
      const p = staging.find(p => p.product_id === id);
      return p ? audit(p) : { product_id: id, already_public: ids.has(id), disposition: 'missing_staging_record_verify_source' };
    }),
    release_allowed: false,
  })),
};
fs.writeFileSync('docs/dufynd-release-audit-20261008.json', JSON.stringify(report, null, 2) + '\n');
console.log(JSON.stringify({public_fragrances: live.length, candidates: candidates.length, manifests: manifests.length}));
