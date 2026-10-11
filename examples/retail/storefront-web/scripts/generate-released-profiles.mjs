import {writeFileSync} from 'node:fs';
import {releaseState,rendererDigest} from './release-gate.mjs';
const profiles=releaseState().filter(r=>r.state.eligible).map(({p,f,state})=>({product_id:p.product_id,slug:p.slug,brand:f.brand,name:f.name,concentration:f.concentration,volume_ml:f.volume_ml,notes:f.notes,summary_de:f.summary_de,seo:p.seo,indexing_approved:state.indexing_approved}));
writeFileSync(new URL('../lib/generated/released-profiles.json',import.meta.url),JSON.stringify({profiles},null,2)+'\n');
writeFileSync(new URL('../lib/generated/review-build-fingerprint.json',import.meta.url),JSON.stringify({renderer_sha256:rendererDigest()},null,2)+'\n');
console.log(`Owner-authorized independent profiles: ${profiles.length}. Affiliate availability is not a release condition.`);
