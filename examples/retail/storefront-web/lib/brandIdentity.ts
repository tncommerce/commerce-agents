/** Stable display identities; case/spacing aliases never create extra A–Z buckets. */
const aliases:Record<string,string> = {'chanel':'Chanel','ysl':'Yves Saint Laurent','yves saint laurent':'Yves Saint Laurent','hugo boss':'Hugo Boss','boss':'Hugo Boss','maison margiela':'Maison Margiela','parfums de marly':'Parfums de Marly','chloe':'Chloé'};
export function brandKey(value:string):string {return value.normalize('NFKD').replace(/[\u0300-\u036f]/g,'').trim().replace(/\s+/g,' ').toLocaleLowerCase('de');}
export function canonicalBrand(value:string):string {const clean=value.trim().replace(/\s+/g,' ');return aliases[brandKey(clean)]||clean;}
