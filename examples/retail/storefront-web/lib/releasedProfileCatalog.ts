import released from './generated/released-profiles.json';
import {canonicalBrand} from './brandIdentity';
import type {StaticFragrance} from './fragranceCatalog';
type Released={product_id:string;slug:string;brand:string;name:string;concentration:string;volume_ml:number;summary_de:string;editorial_description_de?:string;target_groups?:string[];notes:Partial<Record<'top'|'heart'|'base'|'key',string[]>>;seo:{title:string;description:string;public_path:string};indexing_approved:boolean};
export const RELEASED_PROFILES=released.profiles as Released[];
export const RELEASED_FRAGRANCES:StaticFragrance[]=RELEASED_PROFILES.map(f=>({
 product_id:f.product_id,slug:f.slug,title:`${f.brand} ${f.name}`,brand:canonicalBrand(f.brand),name:f.name,concentration:f.concentration,volume_ml:f.volume_ml,
 visuals:[],preferred_visual:null,presentation_visual:null,backdrop_visual:null,short_description:f.editorial_description_de||f.summary_de,target_groups:f.target_groups||[],role:null,cluster_id:null,relationships:[],
 notes:{top:f.notes.top||[],heart:f.notes.heart||[],base:f.notes.base||[],key:f.notes.key||[],supporting:[]},
 community:{source:'',rating_10:null,rating_count:0,longevity_10:null,projection_10:null,provisional:false},accords:[],scores:{freshness:null,sweetness:null,woodiness:null,spiciness:null},market:{reference_price_eur:null,checked_at:null}
}));
