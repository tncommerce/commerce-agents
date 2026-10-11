import {LIVE_FRAGRANCES} from './fragranceCatalog';
import {brandSlug,canonicalBrand} from './brandIdentity';
const groups=new Map<string,{slug:string;name:string;count:number}>();
for(const f of LIVE_FRAGRANCES){const name=canonicalBrand(f.brand),slug=brandSlug(name);const previous=groups.get(slug);if(previous&&previous.name!==name)throw Error(`Brand slug collision: ${slug}`);groups.set(slug,{slug,name,count:(previous?.count||0)+1});}
export const PUBLIC_BRANDS=[...groups.values()].sort((a,b)=>a.name.localeCompare(b.name,'de'));
export const fragrancesForBrand=(slug:string)=>LIVE_FRAGRANCES.filter(f=>brandSlug(f.brand)===slug);
