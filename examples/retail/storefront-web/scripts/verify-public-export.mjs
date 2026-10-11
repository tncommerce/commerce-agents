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
console.log('Public export verified: no raw Parfumo rating payload; review-route boundary intact.');
