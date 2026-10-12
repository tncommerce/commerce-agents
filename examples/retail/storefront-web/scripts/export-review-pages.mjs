import { existsSync, mkdirSync, copyFileSync, rmSync, readFileSync } from 'node:fs';
const destination = new URL('../out/review', import.meta.url);
// A normal build actively clears review routes, including stale preview exports.
rmSync(destination, {recursive:true,force:true});
if (process.env.DUFYND_CATALOG_REVIEW === '1') {
  const {pilots} = JSON.parse(readFileSync(new URL('../../data/dufynd_release_pilots.json',import.meta.url),'utf8'));
  mkdirSync(new URL('duft/',destination.href+'/'),{recursive:true});
  for (const p of pilots) {
    const source = new URL(`../.next/server/app/review/duft/${p.slug}.html`,import.meta.url);
    if (!existsSync(source)) throw new Error(`Missing rendered pilot: ${p.slug}`);
    const html = readFileSync(source,'utf8');
    if (!html.includes('Designprüfung') || !html.includes('noindex')) throw new Error('Invalid review page');
    copyFileSync(source,new URL(`duft/${p.slug}.html`,destination.href+'/'));
  }
  console.log(`${pilots.length} noindex review pages exported for local owner QA only.`);
  const {items}=JSON.parse(readFileSync(new URL('../../data/dufynd_photo_integration_review.json',import.meta.url),'utf8'));
  // Resolve the existing canonical slugs from the generated static params output,
  // without introducing a second slug rule here.
  const {readdirSync}=await import('node:fs');
  const photoSource=new URL('../.next/server/app/review/photos/',import.meta.url);
  const pages=readdirSync(photoSource).filter(name=>name.endsWith('.html')&&name!=='disabled.html');
  if(pages.length!==items.length)throw Error('Private photo page count mismatch');
  mkdirSync(new URL('photos/',destination.href+'/'),{recursive:true});
  for(const name of pages){
    const source=new URL(name,photoSource);
    const html=readFileSync(source,'utf8');
    if(!html.includes('data-photo-review-boundary')||!html.includes('noindex'))throw Error('Invalid merchant photo review page');
    copyFileSync(source,new URL(`photos/${name}`,destination.href+'/'));
  }
  copyFileSync(new URL('../.next/server/app/review/photos.html',import.meta.url),new URL('photos.html',destination.href+'/'));
}
