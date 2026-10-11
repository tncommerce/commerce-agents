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
  console.log('Three noindex review pages exported for local owner QA only.');
}
