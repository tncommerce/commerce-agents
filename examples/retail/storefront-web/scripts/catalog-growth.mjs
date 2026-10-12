/** Offline, bounded research intake. Never writes release authorizations or public data. */
import {readFileSync, writeFileSync} from 'node:fs';
import {createHash} from 'node:crypto';
import {pathToFileURL} from 'node:url';
import {releaseState, readData} from './release-gate.mjs';
import {publicRows} from './public-catalog-summary.mjs';

const fields=['brand','name','concentration','volume_ml'];
const normalize=value=>String(value??'').normalize('NFKD').replace(/[\u0300-\u036f]/g,'').toLowerCase().replace(/&/g,' ').replace(/[^a-z0-9]+/g,' ').trim().replace(/\s+/g,' ');
const brandAliases={'ysl':'yves saint laurent','afnan':'afnan perfumes','boss':'hugo boss','armani':'giorgio armani','pdm':'parfums de marly','jpg':'jean paul gaultier'};
export const brandKey=value=>brandAliases[normalize(value)]??normalize(value);
// Existing qualified manufacturer reference R740110-R100MLS calls this Eros EDP;
// staging's longer display name is Eros Pour Homme. This is not a fuzzy rule.
const nameKey=row=>brandKey(row.brand)==='versace'&&normalize(row.name??row.canonical_name)==='eros'?'eros pour homme':normalize(row.name??row.canonical_name);
// Deliberately keep Intense, Elixir, years and concentration. Fuzzy matching is not identity.
export const familyKey=row=>[brandKey(row.brand),nameKey(row),normalize(row.concentration)].join('|');
export const variantKey=row=>`${familyKey(row)}|${row.volume_ml??'UNVERIFIED_VOLUME'}`;
export const digest=value=>createHash('sha256').update(JSON.stringify(value)).digest('hex');
export const qualifiedFact=(row,date)=>({product_id:row.product_id,...Object.fromEntries(fields.map(f=>[f,row[f]])),checked_at:date,identity:{kind:'manufacturer_reference',value:row.manufacturer_reference,source_url:row.source_url,verified:true},notes:row.notes,notes_source:{url:row.notes_source_url??row.source_url,kind:'manufacturer_product_facts'},summary_de:row.summary_de,variant_evidence_note:[row.variant_evidence,row.caveat].filter(Boolean).join(' '),facts_only:true,community_data_included:false,image_rights_status:'HOLD',publication_authorized:false});
const sourceDomains=['jeanpaulgaultier.com','viktor-rolf.com','amouage.com','chloe.com','parfums-de-marly.com','yslbeauty.com','yslbeauty.de','dior.com','initioparfums.com','armanibeauty.it','armanibeauty.de','afnan.com'];
// Additional manufacturer sources are bound to their evidenced brand, not a
// general-purpose allowlist. A source URL still does not verify its facts/rights.
const intakeDomains={'bdk parfums':'bdkparfums.com','montale':'montaleparfums.com','hermes':'hermes.com','zadig voltaire':'zadig-et-voltaire.com'};
const official=(url,brand)=>{try{const u=new URL(url),intake=intakeDomains[brandKey(brand)];return u.protocol==='https:'&&!u.username&&!u.password&&(sourceDomains.some(d=>u.hostname===d||u.hostname.endsWith(`.${d}`))||Boolean(intake&&(u.hostname===intake||u.hostname===`www.${intake}`)));}catch{return false;}};
const indexUnique=(rows,key)=>{const result=new Map();for(const row of rows){if(!row[key]||result.has(row[key]))throw Error(`duplicate_or_missing_${key}`);result.set(row[key],row);}return result;};

export function validateEvidence(evidence,staging,existingFacts){
  if(evidence.facts_only!==true||evidence.community_data_included!==false||evidence.publication_authorized!==false||!/^\d{4}-\d{2}-\d{2}$/.test(evidence.checked_at))throw Error('unsafe_evidence_scope');
  const staged=indexUnique(staging,'product_id'),prior=indexUnique(existingFacts,'product_id');
  const rows=indexUnique(evidence.products,'product_id');
  for(const [id,row] of rows){
    if(!staged.has(id))throw Error('unknown_product');
    if(row.status==='HOLD'){if(!row.reason)throw Error('missing_hold_reason');continue;}
    if(row.status!=='facts_qualified'||fields.some(f=>row[f]!==staged.get(id)[f]))throw Error('evidence_variant_mismatch');
    if(!Number.isInteger(row.volume_ml)||row.volume_ml<=0||!official(row.source_url,row.brand)||!official(row.notes_source_url??row.source_url,row.brand)||!row.manufacturer_reference||!row.variant_evidence||!row.summary_de)throw Error('missing_manufacturer_evidence');
    if(!row.notes||!Object.values(row.notes).some(n=>Array.isArray(n)&&n.length)||Object.entries(row.notes).some(([k,v])=>!['top','heart','base','key'].includes(k)||!Array.isArray(v)||v.some(n=>typeof n!=='string'||!n.trim())))throw Error('invalid_documented_notes');
    if(['gtin','price','rating','review_count','community','affiliate_url','image_url','publication_authorized'].some(k=>k in row))throw Error('unsupported_claim_in_evidence');
    if(prior.has(id)&&digest(prior.get(id))!==digest(qualifiedFact(row,evidence.checked_at)))throw Error('already_qualified_evidence_conflict');
  }
  return rows;
}

export function buildGrowth({canonical,staging,candidates,facts,evidence,states,publicIds,photoHolds}){
  const extra=validateEvidence(evidence,staging,facts);
  const canonicalById=indexUnique(canonical,'product_id'),stagingById=indexUnique(staging,'product_id');
  const factById=indexUnique(facts,'product_id'),stateById=indexUnique(states,'product_id');
  for(const fact of facts)if(!stagingById.has(fact.product_id)||fields.some(f=>fact[f]!==stagingById.get(fact.product_id)[f]))throw Error('existing_fact_variant_mismatch');
  indexUnique(candidates,'candidate_id');
  const products=new Map(canonicalById),occurrences=new Map();
  for(const row of staging){
    const old=products.get(row.product_id);
    if(old&&fields.some(f=>normalize(old[f])!==normalize(row[f])))throw Error(`same_id_different_variant:${row.product_id}`);
    if(!old)products.set(row.product_id,row);
  }
  const variantIds=new Map();
  for(const row of products.values()){
    const key=variantKey(row);
    if(variantIds.has(key))throw Error(`duplicate_variant_ids:${variantIds.get(key)}:${row.product_id}`);
    variantIds.set(key,row.product_id);
    occurrences.set(row.product_id,[]);
  }
  const unmatched=[];
  for(const candidate of candidates){
    // Stable candidate_id is stronger than cosmetic name matching; surface discrepancies.
    let matches=staging.filter(p=>p.candidate_id===candidate.candidate_id);
    const possible=matches.map(p=>p.product_id);
    // A reused legacy key does not resolve a named edition, e.g. The One (2025).
    matches=matches.filter(p=>brandKey(p.brand)===brandKey(candidate.brand)&&nameKey(p)===nameKey(candidate));
    const method=matches.length?'existing_candidate_id':'exact_brand_name_concentration';
    if(!matches.length)matches=[...products.values()].filter(p=>familyKey(p)===familyKey(candidate));
    if(matches.length>1)throw Error(`ambiguous_candidate:${candidate.candidate_id}`);
    if(matches.length){
      const row=matches[0];
      occurrences.get(row.product_id).push({candidate_id:candidate.candidate_id,method,metadata_discrepancy:familyKey(row)!==familyKey(candidate)});
    }else unmatched.push({candidate_id:candidate.candidate_id,brand:candidate.brand,name:candidate.canonical_name,concentration:candidate.concentration,volume_ml:null,state:'RESEARCH_ONLY',possible_existing_ids:possible,reason:possible.length?'Legacy key points to a differently named edition; resolve identity before counting any additional product.':'Exact volume and manufacturer variant not verified; not counted as an exact SKU.'});
  }
  const rows=[...products.values()].map(p=>{
    const id=p.product_id,state=stateById.get(id),supplement=extra.get(id),isPublic=publicIds.has(id);
    const completed=n=>state?.stages.find(s=>s.name===n)?.complete===true;
    const factual=factById.has(id)||supplement?.status==='facts_qualified';
    const variant=state?completed('VARIANT_CHECKED'):supplement?.status==='facts_qualified';
    const hold=supplement?.status==='HOLD'?supplement.reason:null;
    return {product_id:id,...Object.fromEntries(fields.map(f=>[f,p[f]])),variant_key:variantKey(p),in_canonical:canonicalById.has(id),in_staging:stagingById.has(id),legacy_candidates:occurrences.get(id),
      stages:{research_staged:stagingById.has(id),facts_qualified:factual,variant_checked:variant,visual_ready:completed('VISUAL_READY'),browser_QA:completed('FUNCTIONAL_QA'),owner_review:Boolean(state)&&!state.eligible,owner_approved:state?.eligible===true,published:isPublic,indexed:null,indexing_approved:state?.indexing_approved===true},
      source_evidence:factById.get(id)??(supplement?.status==='facts_qualified'?supplement:null),
      source_hold:hold,remaining_gates:isPublic?[]:state?.blockers??(hold?['SOURCE_HOLD']:factual?['VISUAL_READY','FUNCTIONAL_QA','OWNER_REVIEW','PUBLIC_RELEASE']:['FACTS_QUALIFIED','VARIANT_CHECKED','VISUAL_READY','FUNCTIONAL_QA','OWNER_REVIEW','PUBLIC_RELEASE']),
      original_photo_hold:photoHolds.find(r=>r.product_id===id)?.reason??(isPublic?null:'no_approved_asset_specific_license_and_exact_variant_pair'),affiliate_required:false,
      evidence_sha256:supplement?.status==='facts_qualified'?digest(supplement):state?.evidence_sha256??null};
  }).sort((a,b)=>a.product_id.localeCompare(b.product_id));
  const additional=rows.filter(p=>!p.stages.published),wave=additional.filter(p=>p.remaining_gates.length===1&&p.remaining_gates[0]==='OWNER_REVIEW');
  const counts=Object.fromEntries(['research_staged','facts_qualified','variant_checked','visual_ready','browser_QA','owner_review','owner_approved','published'].map(k=>[k,additional.filter(p=>p.stages[k]).length]));
  counts.indexed=null; // Search-engine indexing cannot be established by local route existence.
  const next=additional.filter(p=>p.source_evidence&&!stateById.has(p.product_id)&&p.stages.variant_checked).map(p=>p.product_id);
  return {schema_version:1,status:'DEVELOPMENT_ONLY_NO_RELEASE_AUTHORITY',checked_at:evidence.checked_at,
    counting_policy:'Exact SKU union by stable ID plus strict normalized variant; unresolved research names remain separate. Additional-stage counts exclude existing public profiles. Published is repository projection, not a newly performed production crawl. Indexed is unknown, never inferred.',
    counts:{canonical:canonical.length,staging:staging.length,canonical_staging_overlap:staging.filter(p=>canonicalById.has(p.product_id)).length,exact_sku_union:rows.length,legacy_research_rows:candidates.length,legacy_matched:candidates.length-unmatched.length,research_only_names:unmatched.length,existing_public:publicIds.size,existing_review_pages:states.length,existing_owner_candidate_wave:wave.length,newly_facts_qualified:[...extra.values()].filter(p=>p.status==='facts_qualified').length,additional_stages:counts},
    milestones:[50,75,100,101].map(target=>({target,current_public:publicIds.size,public_delta:Math.max(0,target-publicIds.size),possible_after_existing_owner_wave:publicIds.size+wave.length,extra_complete_pages_needed_beyond_wave:Math.max(0,target-publicIds.size-wave.length),publication_authorized:false})),
    next_page_batch:{product_ids:next,count:next.length,stage:'FACTS_QUALIFIED_VARIANT_CHECKED_NOT_RENDERED',next:'Promote source facts through existing qualified review pipeline, supply distinct editorial compositions, rebuild and bind fresh four-width QA. Do not add a release authorization.'},
    products:rows,research_only:unmatched};
}

export function inputs(){return {canonical:readData('scentai_products.json').products,staging:readData('scentai_catalog_staging.json').products,candidates:readData('scentai_catalog_candidates.json').products,facts:readData('dufynd_discovery_qualification.json').products,evidence:readData('dufynd_growth_evidence.json'),states:releaseState().map(r=>r.state),publicIds:new Set(publicRows.map(p=>p.product_id)),photoHolds:readData('dufynd_core_scale_release_decision.json').photo_holds};}

export function boundedBatch(matrix,{limit=24,completed=[]}={}){
  if(!Number.isInteger(limit)||limit<1||limit>100)throw Error('batch_limit_must_be_1_to_100');
  const all=[...matrix.next_page_batch.product_ids,...matrix.products.filter(p=>!p.stages.published&&!p.stages.facts_qualified&&!p.source_hold).map(p=>p.product_id),...matrix.research_only.map(p=>p.candidate_id)];
  const known=new Set(all);if(completed.some(id=>!known.has(id))||new Set(completed).size!==completed.length)throw Error('invalid_completed_checkpoint');
  const pending=all.filter(id=>!completed.includes(id));
  return {input_sha256:digest(matrix),selected:pending.slice(0,limit),remaining:pending.slice(limit),completed,limit,publication_authorized:false};
}

if(process.argv[1]&&import.meta.url===pathToFileURL(process.argv[1]).href){
  const matrix=buildGrowth(inputs()),limit=Number(process.argv.find(a=>a.startsWith('--limit='))?.split('=')[1]??24);
  const resumePath=process.argv.find(a=>a.startsWith('--resume='))?.slice(9);
  const checkpoint=resumePath?JSON.parse(readFileSync(resumePath,'utf8')):null;
  if(checkpoint&&checkpoint.input_sha256!==digest(matrix))throw Error('stale_batch_checkpoint');
  const batch=boundedBatch(matrix,{limit,completed:checkpoint?.completed??[]});
  const output={...matrix,batch};
  if(process.argv.includes('--write'))writeFileSync(new URL('../../data/dufynd_catalog_growth_matrix.json',import.meta.url),JSON.stringify(output,null,2)+'\n');
  console.log(JSON.stringify({counts:matrix.counts,milestones:matrix.milestones,batch},null,2));
}
