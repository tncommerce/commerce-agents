import { writeFileSync } from 'node:fs';
import { canonical, readData, releaseState, rendererDigest } from './release-gate.mjs';

// Owner-reviewed facts-only source packets are review input, never a release
// authorization. Only releaseState() can promote a page to the static build.
const reviewWave = readData('dufynd_facts_wave_01_review.json');
if (reviewWave.status !== 'REVIEW_ONLY_NOT_PUBLISHED' ||
    reviewWave.profile_count !== 20 || !Array.isArray(reviewWave.profiles)) {
  throw new Error('Facts-only wave 1 source contract changed');
}
const waveById = new Map(reviewWave.profiles.map(p => [p.product_id, p]));
if (waveById.size !== 20) throw new Error('Duplicate wave 1 product identities');
const staged = readData('scentai_catalog_staging.json').products;
const stagedById = new Map(staged.map(p => [p.product_id, p]));

const profiles = releaseState().filter(r => r.state.eligible).map(({ p, f, state }) => {
  const result = {
    product_id: p.product_id, slug: p.slug, brand: f.brand, name: f.name,
    concentration: f.concentration, volume_ml: f.volume_ml,
    notes: f.notes, summary_de: f.summary_de, seo: p.seo,
    indexing_approved: state.indexing_approved,
  };
  const review = waveById.get(p.product_id);
  if (!review) return result; // Future releases use their own bound source packet.
  const stage = stagedById.get(p.product_id);
  const groups = Object.fromEntries(['top', 'heart', 'base', 'key'].map(key => [key, f.notes?.[key] || []]));
  if (!stage || review.slug !== p.slug ||
      review.evidence_sha256 !== state.evidence_sha256 ||
      review.summary_de !== f.summary_de ||
      review.concentration !== f.concentration ||
      review.volume_ml !== f.volume_ml ||
      review.brand !== f.brand || review.name !== f.name ||
      review.identity?.value !== f.identity?.value ||
      canonical(groups) !== canonical(review.notes) ||
      canonical(review.seo) !== canonical(p.seo)) {
    throw new Error(`Facts-only release identity/source drift: ${p.product_id}`);
  }
  const groupsFromStage = stage.classification?.target_groups;
  if (!Array.isArray(groupsFromStage) || groupsFromStage.length === 0 ||
      !groupsFromStage.every(x => ['men', 'women', 'unisex'].includes(x)) ||
      !String(review.editorial_description_de || '').startsWith(f.summary_de)) {
    throw new Error(`Facts-only review description/audience changed: ${p.product_id}`);
  }
  return {
    ...result,
    notes: groups,
    editorial_description_de: review.editorial_description_de,
    target_groups: groupsFromStage,
  };
});
writeFileSync(new URL('../lib/generated/released-profiles.json', import.meta.url), JSON.stringify({ profiles }, null, 2) + '\n');
writeFileSync(new URL('../lib/generated/review-build-fingerprint.json', import.meta.url), JSON.stringify({ renderer_sha256: rendererDigest() }, null, 2) + '\n');
console.log(`Owner-authorized independent profiles: ${profiles.length}. Affiliate availability is not a release condition.`);
