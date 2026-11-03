import assert from 'node:assert/strict';
import { writeFile } from 'node:fs/promises';
import { chromium } from 'playwright';
import { chooseMeasurement } from '../../examples/retail/storefront-web/scripts/measurement-choice-qa.mjs';

const base = 'http://127.0.0.1:3026';
const cases = [
  ['Black Opium EDP 90 ml', 'BlackOpium EDP 90 ml'],
  ['Bois Impérial EDP 100 ml', 'BoisImperial EDP 100 ml'],
  ['La Vie Est Belle EDP 100 ml', 'LaVieEstBelle EDP 100 ml'],
];
const browser = await chromium.launch({headless:true});
const context = await browser.newContext({viewport:{width:390,height:900},serviceWorkers:'block'});
const forbidden = [];
await context.route('**/*', route => {
  const url = new URL(route.request().url());
  if (/\/api\/(analytics|session|clickout)/.test(url.pathname)) forbidden.push(url.pathname);
  if (url.origin === base) return route.continue();
  return route.abort();
});
const page = await context.newPage();
const observations = [];
try {
  for (const route of ['/duft','/start']) {
    for (const [normal, compact] of cases) {
      for (const query of [normal, compact]) {
        await page.goto(`${base}${route}${route==='/duft'?'?q='+encodeURIComponent(query):''}`);
        await chooseMeasurement(page,'denied');
        let results;
        if (route==='/duft') {
          await page.waitForFunction(q=>document.querySelector('input[type="search"]')?.value===q,query);
          results=await page.locator('.dufynd-catalog-card h2').allTextContents();
        } else {
          await page.getByLabel('Duft oder Marke suchen',{exact:true}).fill(query);
          await page.locator('[data-dufynd-social-live-results]').waitFor();
          results=await page.locator('[data-dufynd-social-live-results] a strong').allTextContents();
        }
        observations.push({route,width:390,query,results});
        if (query===normal) assert.equal(results.length,1,`Public profile exists: ${query}`);
        if (query===compact && normal.startsWith('Black')) {
          if(route==='/duft') await page.getByRole('searchbox',{name:'Duft, Marke oder Profil'}).scrollIntoViewIfNeeded();
          else await page.getByLabel('Duft oder Marke suchen',{exact:true}).scrollIntoViewIfNeeded();
          await page.screenshot({path:new URL(`before-${route.slice(1)}-390.png`,import.meta.url).pathname});
        }
      }
    }
  }
  assert.deepEqual(forbidden,[]);
  await writeFile(new URL('before.json',import.meta.url),JSON.stringify({production_sha:'5099ec4564a319c15bca8f8dc1c22a56c333e947',helper_blob:'51fa7b79fc7d830bc68406866a2169f93136f77a',data:'Unchanged public build, external requests blocked',observations,analytics_and_clickout_requests:forbidden},null,2)+'\n');
  console.log(JSON.stringify(observations,null,2));
} finally {await browser.close();}
