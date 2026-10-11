import {createHash} from 'node:crypto';
import {readFileSync} from 'node:fs';
export const canonical=value=>Array.isArray(value)?`[${value.map(canonical).join(', ')}]`:value&&typeof value==='object'?`{${Object.entries(value).sort(([a],[b])=>a<b?-1:a>b?1:0).map(([k,v])=>`${JSON.stringify(k)}: ${canonical(v)}`).join(', ')}}`:JSON.stringify(value);
export const digest=value=>createHash('sha256').update(typeof value==='string'?value:canonical(value)).digest('hex');
export const readData=name=>JSON.parse(readFileSync(new URL(`../../data/${name}`,import.meta.url),'utf8'));
const renderFiles=['components/QualifiedProductPage.tsx','components/ScentArtwork.tsx','components/ScentStudy.tsx','components/ScentStudy.module.css','components/ScentScene.tsx','app/review/duft/[slug]/review.module.css','app/globals.css','app/layout.tsx','lib/noteLabels.ts','lib/brandIdentity.ts','../data/dufynd_release_pilots.json','../data/dufynd_discovery_qualification.json'];
export const rendererDigest=()=>digest(renderFiles.map(p=>[p,readFileSync(new URL(`../${p}`,import.meta.url),'utf8')]));
export const renderDigest=(p,renderer)=>digest({renderer,presentation:{slug:p.slug,motif:p.motif,tone:p.tone,headline:p.headline,art_notes:p.art_notes,visual:p.visual,seo:p.seo}});
export function evaluateRelease(f,p,qa,approval,holds,renderer){
 const blockers=[];
 const facts=Boolean(f?.identity?.verified&&['gtin','manufacturer_reference'].includes(f.identity.kind)&&f.facts_only&&f.community_data_included===false&&Object.values(f.notes||{}).some(n=>n.length)&&f.notes_source?.url);
 if(!facts||p.evidence_sha256!==digest(f))blockers.push('FACTS_EVIDENCE');
 if(['product_id','brand','name','concentration','volume_ml'].some(k=>p.expected_variant[k]!==f[k]))blockers.push('VARIANT_MISMATCH');
 if(holds.some(h=>h.product_id===p.product_id))blockers.push('VARIANT_SOURCE_CONFLICT');
 const v=p.visual;
 if(v.kind!=='dufynd_original_vector_illustration'||v.third_party_asset_used!==false||v.contains_product_replica!==false||!v.label)blockers.push('VISUAL_PROVENANCE');
 const render=renderDigest(p,renderer);
 const qaValid=qa?.product_id===p.product_id&&qa.passed===true&&qa.evidence_sha256===p.evidence_sha256&&qa.render_sha256===render&&[320,390,768,1440].every(w=>qa.widths?.includes(w));
 if(!qaValid)blockers.push('FUNCTIONAL_QA');
 const owner=approval?.product_id===p.product_id&&approval.evidence_sha256===p.evidence_sha256&&approval.render_sha256===render&&approval.qa_sha256===digest(qa)&&approval.variant_approved===true&&approval.illustration_approved===true&&approval.publication_approved===true&&Boolean(approval.approved_by?.trim()&&approval.approval_reference?.trim()&&/^\d{4}-\d{2}-\d{2}/.test(approval.approved_at||''));
 if(!owner)blockers.push('OWNER_REVIEW');
 const stages=['FACTS_QUALIFIED','VARIANT_CHECKED','VISUAL_READY','FUNCTIONAL_QA','OWNER_REVIEW','PUBLIC_RELEASE'];
 const completed=[facts&&!blockers.includes('FACTS_EVIDENCE'),!blockers.some(b=>b.startsWith('VARIANT')),!blockers.includes('VISUAL_PROVENANCE'),qaValid,Boolean(owner),blockers.length===0];
 return {product_id:p.product_id,public_path:p.seo.public_path,stages:stages.map((name,i)=>({name,complete:completed.slice(0,i+1).every(Boolean)})),blockers,eligible:blockers.length===0,evidence_sha256:p.evidence_sha256,render_sha256:render,qa_sha256:qa?digest(qa):null,original_photo_status:p.original_photo_status,affiliate_required:false,indexing_approved:owner&&approval.indexing_approved===true};
}
export function releaseState(){
 const facts=readData('dufynd_discovery_qualification.json').products, pilots=readData('dufynd_release_pilots.json').pilots, auth=readData('dufynd_release_authorizations.json'), qa=readData('dufynd_release_qa.json').profiles, renderer=rendererDigest();
 for(const [label,rows,key] of [['product',pilots,'product_id'],['slug',pilots,'slug'],['approval',auth.approvals,'product_id'],['qa',qa,'product_id']])if(new Set(rows.map(p=>p[key])).size!==rows.length)throw Error(`Duplicate ${label}`);
 for(const p of pilots)if(!/^[a-z0-9]+(?:-[a-z0-9]+)*$/.test(p.slug)||p.seo.public_path!==`/duft/${p.slug}`)throw Error(`Invalid release path: ${p.product_id}`);
 for(const a of auth.approvals)if(!pilots.some(p=>p.product_id===a.product_id))throw Error(`Unknown approved product: ${a.product_id}`);
 return pilots.map(p=>{const f=facts.find(f=>f.product_id===p.product_id);if(!f)throw Error(`Missing fact ${p.product_id}`);const a=auth.approvals.find(a=>a.product_id===p.product_id);const state=evaluateRelease(f,p,qa.find(q=>q.product_id===p.product_id),a,auth.product_holds,renderer);if(a?.publication_approved&&!state.eligible)throw Error(`Stale or invalid release approval: ${p.product_id}: ${state.blockers.join(', ')}`);return {p,f,state};});
}
