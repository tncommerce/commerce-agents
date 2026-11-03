import {readdirSync,readFileSync,existsSync} from 'node:fs';
import path from 'node:path';
import {fileURLToPath} from 'node:url';
import {rendererDigest} from './release-gate.mjs';
const root=fileURLToPath(new URL('../out',import.meta.url));
const reviewPhotos=JSON.parse(readFileSync(new URL('../../data/dufynd_photo_integration_review.json',import.meta.url),'utf8')).items;
const publicPhotos=JSON.parse(readFileSync(new URL('../lib/generated/original-photos.json',import.meta.url),'utf8'));
// A reviewed source can later receive an exact public approval. Its private
// review route/file remains forbidden; an approval for another hash or variant
// cannot exempt the original private image from this export boundary.
const privateOnlyPhotos=reviewPhotos.filter(p=>!publicPhotos.some(a=>
 a.product_id===p.product_id && a.url===p.image_url && a.image_sha256===p.image_sha256 &&
 a.volume_ml===p.volume_ml && a.rights_basis_id===p.rights_basis_id
));
const built=JSON.parse(readFileSync(new URL('../lib/generated/review-build-fingerprint.json',import.meta.url),'utf8'));
if(built.renderer_sha256!==rendererDigest())throw new Error('Render sources changed during build');
function walk(dir){return readdirSync(dir,{withFileTypes:true}).flatMap(d=>d.isDirectory()?walk(path.join(dir,d.name)):[path.join(dir,d.name)]);}
for(const file of walk(root).filter(f=>/\.(js|html|txt)$/.test(f))) {
 const text=readFileSync(file,'utf8').replaceAll('\\"','"');
 if(process.env.DUFYND_CATALOG_REVIEW!=='1' && privateOnlyPhotos.some(p=>text.includes(p.image_sha256)||text.includes(p.image_url))) throw Error(`Private merchant photo leaked into normal export: ${path.relative(root,file)}`);
 if(/"source"\s*:\s*"Parfumo"\s*,\s*"rating_10"\s*:\s*\d/.test(text)) throw new Error(`Blocked community data in public export: ${path.relative(root,file)}`);
}
if(process.env.DUFYND_CATALOG_REVIEW!=='1' && existsSync(path.join(root,'review'))) throw new Error('Review routes leaked into normal export');
if(process.env.DUFYND_CATALOG_REVIEW!=='1' && existsSync(path.join(root,'__review-photos'))) throw new Error('Merchant review photos leaked into normal export');
const pilots=JSON.parse(readFileSync(new URL('../../data/dufynd_release_pilots.json',import.meta.url),'utf8')).pilots;
const released=JSON.parse(readFileSync(new URL('../lib/generated/released-profiles.json',import.meta.url),'utf8')).profiles;
const sitemap=readFileSync(path.join(root,'sitemap.xml'),'utf8');
for(const p of pilots){
 const approved=released.find(r=>r.product_id===p.product_id);
 const exported=existsSync(path.join(root,`duft/${p.slug}.html`))||existsSync(path.join(root,`duft/${p.slug}/index.html`));
 if(Boolean(approved)!==exported)throw Error(`Public route authorization mismatch: ${p.product_id}`);
 if(!approved?.indexing_approved&&sitemap.includes(`/duft/${p.slug}<`))throw Error(`Unauthorized indexing: ${p.product_id}`);
}

// WORK50: evidence-based buying guide must be server-rendered on the one
// intended product URL. Keep canonical paths, other profiles and offer CTAs.
function productHtml(slug) {
  for (const candidate of [
    path.join(root, 'duft', `${slug}.html`),
    path.join(root, 'duft', slug, 'index.html'),
  ]) {
    if (existsSync(candidate)) return readFileSync(candidate, 'utf8');
  }
  throw new Error(`Missing public fragrance page: ${slug}`);
}
const libre = productHtml('yves-saint-laurent-libre');
const rabanne = productHtml('rabanne-1-million');
if (
  !libre.includes('data-dufynd-libre-refill-guide') ||
  !libre.includes('id="libre-nachfuellbar"') ||
  !libre.includes('href="#angebote"') ||
  !libre.includes('nachfüllbarer Flakon') ||
  !libre.includes('kein vollständiger Flakon')
) {
  throw new Error('Libre buying guide is not present or incomplete in static HTML export');
}
if (rabanne.includes('data-dufynd-libre-refill-guide')) {
  throw new Error('Libre buyer guide leaked onto the Rabanne product page');
}
console.log('Libre EDP 90ml buyer guide: static export, internal offer CTA and product isolation PASS');

console.log('Public export verified: no raw Parfumo rating payload; review-route boundary intact.');
