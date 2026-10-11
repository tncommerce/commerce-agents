import {readdirSync,readFileSync,existsSync} from 'node:fs';
import path from 'node:path';
import {fileURLToPath} from 'node:url';
const root=fileURLToPath(new URL('../out',import.meta.url));
function walk(dir){return readdirSync(dir,{withFileTypes:true}).flatMap(d=>d.isDirectory()?walk(path.join(dir,d.name)):[path.join(dir,d.name)]);}
for(const file of walk(root).filter(f=>/\.(js|html|txt)$/.test(f))) {
 const text=readFileSync(file,'utf8').replaceAll('\\"','"');
 if(/"source"\s*:\s*"Parfumo"\s*,\s*"rating_10"\s*:\s*\d/.test(text)) throw new Error(`Blocked community data in public export: ${path.relative(root,file)}`);
}
if(process.env.DUFYND_CATALOG_REVIEW!=='1' && existsSync(path.join(root,'review'))) throw new Error('Review routes leaked into normal export');
const pilots=JSON.parse(readFileSync(new URL('../../data/dufynd_release_pilots.json',import.meta.url),'utf8')).pilots;
const released=JSON.parse(readFileSync(new URL('../lib/generated/released-profiles.json',import.meta.url),'utf8')).profiles;
const sitemap=readFileSync(path.join(root,'sitemap.xml'),'utf8');
for(const p of pilots){
 const approved=released.find(r=>r.product_id===p.product_id);
 const exported=existsSync(path.join(root,`duft/${p.slug}.html`))||existsSync(path.join(root,`duft/${p.slug}/index.html`));
 if(Boolean(approved)!==exported)throw Error(`Public route authorization mismatch: ${p.product_id}`);
 if(!approved?.indexing_approved&&sitemap.includes(`/duft/${p.slug}<`))throw Error(`Unauthorized indexing: ${p.product_id}`);
}
console.log('Public export verified: no raw Parfumo rating payload; review-route boundary intact.');
