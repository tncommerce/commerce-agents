import facts from '../../data/dufynd_discovery_qualification.json';
import manifest from '../../data/dufynd_release_pilots.json';
import { createHash } from 'node:crypto';
import publicCatalog from './generated/public-catalog.json';

// Matches the evidence file's Python sorted JSON serialization, including spaces.
function evidenceJson(value:unknown):string {
  if(Array.isArray(value)) return `[${value.map(evidenceJson).join(', ')}]`;
  if(value && typeof value==='object') return `{${Object.entries(value).sort(([a],[b])=>a<b?-1:a>b?1:0).map(([k,v])=>`${JSON.stringify(k)}: ${evidenceJson(v)}`).join(', ')}}`;
  return JSON.stringify(value);
}
for(const key of ['product_id','slug'] as const) {
 if(new Set(manifest.pilots.map(p=>p[key])).size!==manifest.pilots.length) throw new Error(`Duplicate review ${key}`);
}

// Server-only route dependency. Never feed private staging/commerce rows to clients.
export const RELEASE_PILOTS = manifest.pilots.map(pilot => {
  const fact = facts.products.find(f => f.product_id === pilot.product_id);
  if (!fact || !fact.identity.verified || !fact.facts_only || fact.community_data_included || fact.publication_authorized) {
    throw new Error(`Invalid review evidence: ${pilot.product_id}`);
  }
  for (const key of ['product_id','brand','name','concentration','volume_ml'] as const) {
    if (pilot.expected_variant[key] !== fact[key]) throw new Error(`Pilot variant changed: ${pilot.product_id}`);
  }
  if(createHash('sha256').update(evidenceJson(fact)).digest('hex')!==pilot.evidence_sha256) throw new Error(`Evidence changed: ${pilot.product_id}`);
  if(publicCatalog.products.some(p=>p.product_id===pilot.product_id)) throw new Error(`Already public: ${pilot.product_id}`);
  if(pilot.visual.kind!=='dufynd_original_vector_illustration'||pilot.visual.third_party_asset_used||pilot.visual.contains_product_replica||!pilot.visual.label) throw new Error(`Invalid visual: ${pilot.product_id}`);
  if(pilot.seo.public_path!==`/duft/${pilot.slug}`) throw new Error(`Invalid future canonical: ${pilot.product_id}`);
  return { ...pilot, fact };
});
export const PILOT_REVIEW_ENABLED = process.env.DUFYND_CATALOG_REVIEW === '1';
