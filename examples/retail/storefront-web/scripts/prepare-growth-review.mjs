/** Explicit append-only batch conversion. No owner approvals, offers or original images. */
import {writeFileSync} from 'node:fs';
import {readData,digest} from './release-gate.mjs';
import {validateEvidence,qualifiedFact} from './catalog-growth.mjs';
const evidence=readData('dufynd_growth_evidence.json'),facts=readData('dufynd_discovery_qualification.json'),manifest=readData('dufynd_release_pilots.json');
validateEvidence(evidence,readData('scentai_catalog_staging.json').products,facts.products);
const presentations={
 'SC-JPG-LE-MALE-LE-PARFUM-125':['jean-paul-gaultier-le-male-le-parfum-edpi-125','sage','Würziger Auftakt. Weiche Iris.',['Kardamom','Iris'],'botanical'],
 'SC-VIKTOR-ROLF-SPICEBOMB-EXTREME-EDP-90':['viktor-rolf-spicebomb-extreme-edp-90','amber','Gewürze. Tabak. Warme Vanille.',['Tabak','Vanille'],'embers'],
 'SC-AMOUAGE-GUIDANCE-46-EXTRAIT-100':['amouage-guidance-46-extrait-100','sage','Birne und Weihrauch. Florale Tiefe.',['Birne','Weihrauch'],'botanical'],
 'SC-CHLOE-CHLOE-EDP-100':['chloe-chloe-edp-100','rose','Rosenblätter. Leichte Holznoten.',['Rose','Zeder'],'blossom'],
 'SC-PDM-VALAYA-EXCLUSIF-EDP-75':['parfums-de-marly-valaya-exclusif-edp-75','sage','Mandel. Weiße Blüten. Pudrige Facetten.',['Mandel','Weiße Blüten'],'prism'],
 'SC-YSL-MYSLF-LE-PARFUM-100':['yves-saint-laurent-myslf-le-parfum-100','sage','Orangenblüte. Holz und Bourbon-Vanille.',['Orangenblüte','Bourbon-Vanille'],'architecture'],
 'SC-DIOR-SAUVAGE-ELIXIR-100':['dior-sauvage-elixir-100','sage','Lavendel zwischen Gewürzen und Hölzern.',['Lavendel','Gewürze'],'botanical'],
 'SC-INITIO-SIDE-EFFECT-EDP-90':['initio-side-effect-edp-90','amber','Rum und Zimt. Ein warmer Kontrast.',['Rum','Zimt'],'prism'],
 'SC-YSL-LA-NUIT-DE-LHOMME-EDT-100':['yves-saint-laurent-la-nuit-de-lhomme-edt-100','sage','Bergamotte. Lavendel. Zedernholz.',['Lavendel','Zeder'],'architecture'],
 'SC-ARMANI-ACQUA-DI-GIO-PROFONDO-PARFUM-100':['giorgio-armani-acqua-di-gio-profondo-parfum-100','sage','Marine Frische. Harzige Tiefe.',['Marine Noten','Immortelle'],'architecture'],
 'SC-ARMANI-SI-EDP-100':['giorgio-armani-si-edp-100','rose','Johannisbeere. Ein moderner Chypre.',['Cassis','Moschus'],'botanical'],
 'SC-AFNAN-9-PM-POUR-FEMME-EDP-100':['afnan-9-pm-pour-femme-edp-100','rose','Fruchtiger Auftakt. Florales Herz.',['Himbeere','Rose'],'botanical'],
 'SC-DIOR-JADORE-EDP-100':['dior-jadore-edp-100','amber','Ylang-Ylang. Rose. Zwei Jasminfacetten.',['Ylang-Ylang','Jasmin'],'blossom'],
};
let added=0;
for(const row of evidence.products.filter(p=>p.status==='facts_qualified')){
 const fact=qualifiedFact(row,evidence.checked_at),presentation=presentations[row.product_id];
 if(!presentation)throw Error(`Missing curated presentation: ${row.product_id}`);
 const old=manifest.pilots.find(p=>p.product_id===row.product_id);
 if(old){if(old.evidence_sha256!==digest(fact))throw Error('Cannot silently rebind an existing pilot');continue;}
 if(!facts.products.some(p=>p.product_id===row.product_id))facts.products.push(fact);
 const [slug,tone,headline,art_notes,motif]=presentation;
 if(manifest.pilots.some(p=>p.slug===slug))throw Error('duplicate_slug');
 manifest.pilots.push({product_id:row.product_id,slug,tone,headline,art_notes,original_photo_status:'no_asset_specific_reuse_grant',visual:{kind:'dufynd_original_vector_illustration',source:'components/ScentScene.tsx',contains_product_replica:false,third_party_asset_used:false,label:'Duftillustration · kein Produktfoto'},owner_release_approved:false,affiliate_offer_status:'not_included_requires_separate_verified_mapping',expected_variant:Object.fromEntries(['product_id','brand','name','concentration','volume_ml'].map(k=>[k,row[k]])),evidence_sha256:digest(fact),motif,seo:{public_path:`/duft/${slug}`,title:`${row.brand} ${row.name} – ${row.concentration} ${row.volume_ml} ml`,description:row.summary_de}});
 added++;
}
if(process.argv.includes('--apply')){
 for(const [name,value] of [['dufynd_discovery_qualification.json',facts],['dufynd_release_pilots.json',manifest]])writeFileSync(new URL(`../../data/${name}`,import.meta.url),JSON.stringify(value,null,2)+'\n');
}
console.log(JSON.stringify({mode:process.argv.includes('--apply')?'append_only_applied':'dry_run',added,review_pages:manifest.pilots.length,publication_authorized:false}));
