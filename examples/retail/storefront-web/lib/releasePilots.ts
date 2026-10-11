import facts from '../../data/dufynd_discovery_qualification.json';
import manifest from '../../data/dufynd_release_pilots.json';

// Server-only route dependency. Never feed private staging/commerce rows to clients.
export const RELEASE_PILOTS = manifest.pilots.map(pilot => {
  const fact = facts.products.find(f => f.product_id === pilot.product_id);
  if (!fact || !fact.identity.verified || !fact.facts_only || fact.community_data_included || fact.publication_authorized) {
    throw new Error(`Invalid review evidence: ${pilot.product_id}`);
  }
  for (const key of ['product_id','brand','name','concentration','volume_ml'] as const) {
    if (pilot.expected_variant[key] !== fact[key]) throw new Error(`Pilot variant changed: ${pilot.product_id}`);
  }
  return { ...pilot, fact };
});
export const PILOT_REVIEW_ENABLED = process.env.DUFYND_CATALOG_REVIEW === '1';
