import assert from 'node:assert/strict';
import { createHash } from 'node:crypto';
import { mkdir, readFile, writeFile } from 'node:fs/promises';
import path from 'node:path';
import { chooseMeasurement } from './measurement-choice-qa.mjs';
import { emptyOfferFixture } from './merchant-offer-fixture-qa.mjs';

const args = process.argv.slice(2);
const option = (name, fallback) => args.includes(name) ? args[args.indexOf(name) + 1] : fallback;
const baseUrl = option('--base-url', 'http://127.0.0.1:3000');
const origin = new URL(baseUrl).origin;
assert.ok(['127.0.0.1', 'localhost', '[::1]'].includes(new URL(origin).hostname));
const outputDir = path.resolve(option('--out', '.catalog-profile-qa'));
const originalsDir = option('--originals-dir', process.env.DUFYND_QA_ORIGINALS_DIR);
assert.ok(originalsDir);
await mkdir(outputDir, { recursive: true });
const readJson = async file => JSON.parse(await readFile(new URL(file, import.meta.url)));
const source = await readJson('../lib/generated/public-fragrances.json');
const catalog = await readJson('../lib/generated/public-catalog.json');
const originals = await readJson('../lib/generated/original-photos.json');
const candidates = await readJson('../../data/dufynd_approved_feed_image_candidates.json');
const publicProducts = catalog.products.filter(row => row.product_id.startsWith('SC-') && row.category === 'fragrance' && row.in_stock !== false &&
  !source.products.find(item => item.product_id === row.product_id)?.validation?.blockers?.some(Boolean));
assert.equal(publicProducts.length, 37, 'This acceptance covers the existing public catalog, not additional staging products');
const sourceById = new Map(source.products.map(item => [item.product_id, item]));
const byName = new Map(publicProducts.map(item => [item.attributes?.canonical_name || sourceById.get(item.product_id).name, item]));
assert.equal(byName.size, publicProducts.length, 'Expected names must be unambiguous');
const fixtures = new Map();
const imageSources = [];
for (const candidate of candidates.candidates) {
  if (!originals.some(item => item.product_id === candidate.product_id && item.url === candidate.image_url)) continue;
  try {
    const bytes = await readFile(path.join(originalsDir, `${candidate.merchant_product_id}.png`));
    const sha256 = createHash('sha256').update(bytes).digest('hex');
    assert.equal(sha256, candidate.image_sha256, 'Only hash-bound saved source bytes enter this local image test');
    fixtures.set(candidate.image_url, bytes);
    imageSources.push({ product_id: candidate.product_id, url: candidate.image_url, sha256 });
  } catch (error) {
    if (error.code !== 'ENOENT') throw error;
  }
}
const report = { kind: 'all-public-profile-local-ui-acceptance', started_at: new Date().toISOString(), width: 390,
  limitation: 'Saved original bytes are replayed locally. Image rights, public release and live image availability require their separate evidence.',
  image_sources: imageSources, cases: [], screenshots: [], failures: [], source_hashes: [] };
for (const file of ['../components/FragranceDetailPage.tsx', '../lib/generated/public-catalog.json', '../lib/generated/public-fragrances.json', '../lib/generated/original-photos.json']) {
  report.source_hashes.push({ file, sha256: createHash('sha256').update(await readFile(new URL(file, import.meta.url))).digest('hex') });
}
const persist = () => writeFile(path.join(outputDir, 'catalog-profile-qa.json'), JSON.stringify(report, null, 2) + '\n');
const playwright = await import(process.env.DUFYND_QA_PLAYWRIGHT_MODULE || 'playwright');
const browser = await playwright.chromium.launch({ headless: true });
const context = await browser.newContext({ viewport: { width: 390, height: 900 }, hasTouch: true, reducedMotion: 'reduce', serviceWorkers: 'block' });
const forbidden = [], errors = [];
await context.route('**/*', route => {
  const url = new URL(route.request().url());
  if (/\/api\/(analytics|clickout)/.test(url.pathname)) { forbidden.push(url.pathname); return route.abort(); }
  if (url.pathname === '/api/session') return route.fulfill({ json: { session_id: 'isolated-profile-qa-session' } });
  if (url.pathname.startsWith('/api/merchant-offers/')) return route.fulfill({ json: emptyOfferFixture(route) });
  if (url.pathname.startsWith('/api/')) return route.fulfill({ status: 503, json: { error: 'Isolated QA: API blocked' } });
  if (fixtures.has(url.href)) return route.fulfill({ contentType: 'image/png', body: fixtures.get(url.href) });
  if (url.origin === origin) return route.continue();
  return route.abort();
});
const page = await context.newPage();
page.setDefaultTimeout(20_000);
page.on('pageerror', error => errors.push(String(error)));
try {
  await page.goto(`${origin}/duft`, { waitUntil: 'networkidle' });
  await chooseMeasurement(page, 'denied');
  const more = page.getByRole('button', { name: /^Weitere \d+ Düfte anzeigen$/ });
  while (await more.count()) await more.click();
  const links = await page.locator('.dufynd-catalog-card').evaluateAll(cards => cards.map(card => ({
    name: card.querySelector('h2').textContent.trim(), href: card.querySelector('a.group').getAttribute('href'),
  })));
  assert.equal(links.length, publicProducts.length);
  assert.equal(new Set(links.map(item => item.href)).size, 37);
  for (const link of links) {
    const row = byName.get(link.name), product = row && sourceById.get(row.product_id);
    assert.ok(product, `Unexpected public card: ${link.name}`);
    await page.goto(new URL(link.href, origin).href, { waitUntil: 'networkidle' });
    await page.getByRole('heading', { name: link.name, exact: true, level: 1 }).waitFor();
    const identityText = await page.locator('.dufynd-fragrance-identity').innerText();
    assert.ok(identityText.includes(product.concentration), product.product_id);
    assert.ok(identityText.includes(`${product.volume_ml} ml`), product.product_id);
    assert.equal(await page.locator('[data-dufynd-profile-description]').innerText(), row.short_description);
    assert.equal(await page.evaluate(() => document.documentElement.scrollWidth > innerWidth), false, `${product.product_id}: horizontal overflow`);
    const original = originals.find(item => item.product_id === product.product_id);
    let imageStatus;
    const hero = page.locator('.dufynd-fragrance-hero');
    if (!original) {
      assert.equal(await hero.locator('[data-dufynd-visual-state="missing"]').count(), 1);
      assert.equal(await hero.locator('img').count(), 0);
      imageStatus = 'BLOCKED_NO_APPROVED_ORIGINAL';
    } else if (fixtures.has(original.url)) {
      const image = hero.locator(`img[src=${JSON.stringify(original.url)}]`);
      await image.evaluate(image => image.decode());
      assert.ok(await image.evaluate(image => image.complete && image.naturalWidth > 0));
      imageStatus = 'SAVED_ORIGINAL_BYTES_DECODED_LOCAL_ONLY';
    } else {
      imageStatus = 'REGISTERED_ORIGINAL_NO_LOCAL_BYTE_FIXTURE_NOT_TESTED';
    }
    const screenshot = `profile-${product.product_id.toLowerCase()}-390.png`;
    await page.locator('#duftprofil').screenshot({ path: path.join(outputDir, screenshot) });
    report.screenshots.push({ file: screenshot, product_id: product.product_id, sha256: createHash('sha256').update(await readFile(path.join(outputDir, screenshot))).digest('hex') });
    report.cases.push({ product_id: product.product_id, route: new URL(page.url()).pathname, name: link.name,
      concentration: product.concentration, volume_ml: product.volume_ml, visible_description: row.short_description,
      identity_passed: true, description_passed: true, overflow: false, image_status: imageStatus });
    await persist();
  }
  assert.deepEqual(forbidden, [], 'No analytics or affiliate clickout requests');
  assert.deepEqual(errors, [], 'No browser runtime errors');
  report.completed_at = new Date().toISOString();
  report.counts = { profiles_passed: report.cases.length, original_byte_fixtures_decoded: report.cases.filter(item => item.image_status === 'SAVED_ORIGINAL_BYTES_DECODED_LOCAL_ONLY').length,
    missing_originals_blocked: report.cases.filter(item => item.image_status === 'BLOCKED_NO_APPROVED_ORIGINAL').length,
    originals_not_locally_tested: report.cases.filter(item => item.image_status === 'REGISTERED_ORIGINAL_NO_LOCAL_BYTE_FIXTURE_NOT_TESTED').length };
  await persist();
  console.log(JSON.stringify({ status: 'passed', ...report.counts }));
} catch (error) {
  report.failures.push({ error: String(error), url: page.url(), forbidden, errors });
  await persist();
  throw error;
} finally { await browser.close(); }
