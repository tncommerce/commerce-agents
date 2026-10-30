import assert from 'node:assert/strict';
import { createHash } from 'node:crypto';
import { mkdir, readFile, writeFile } from 'node:fs/promises';
import path from 'node:path';
import { pathToFileURL } from 'node:url';
import { chooseMeasurement } from './measurement-choice-qa.mjs';
import { emptyOfferFixture } from './merchant-offer-fixture-qa.mjs';

const originalIds = [
  'SC-YSL-LIBRE-EDP-90',
  'SC-PDM-DELINA-EDP-75',
  'SC-YSL-BLACK-OPIUM-EDP-90',
];

// This is isolated UI QA, not evidence of production image delivery or a fresh
// merchant offer. Exact saved original bytes are served locally; every other
// external request is blocked, including analytics, affiliate and API traffic.
export async function verifyCatalogCompletion(browser, baseUrl, outputDir, originalsDir) {
  const origin = new URL(baseUrl).origin;
  assert.ok(['127.0.0.1', 'localhost', '[::1]'].includes(new URL(origin).hostname));
  assert.ok(originalsDir, 'Supply the directory containing the saved original PNGs');
  await mkdir(outputDir, { recursive: true });
  const manifest = JSON.parse(await readFile(new URL('../../data/dufynd_approved_feed_image_candidates.json', import.meta.url)));
  const originalFixtures = new Map();
  const sources = [];
  for (const id of originalIds) {
    const item = manifest.candidates.find(candidate => candidate.product_id === id);
    assert.ok(item?.review_status === 'approved' && item.exact_variant_verified === true);
    assert.equal(item.rights_status, 'verified_for_publisher_service');
    const bytes = await readFile(path.join(originalsDir, `${item.merchant_product_id}.png`));
    const sha256 = createHash('sha256').update(bytes).digest('hex');
    if (item.image_sha256) assert.equal(sha256, item.image_sha256, `${id}: saved original changed`);
    originalFixtures.set(item.image_url, bytes);
    sources.push({ product_id: id, image_url: item.image_url, sha256, source: 'saved-original-byte-fixture' });
  }

  const report = { kind: 'isolated-local-ui-qa', baseUrl, started_at: new Date().toISOString(),
    limitation: 'Local original-byte fixtures and synthetic empty offers; not live image availability or merchant evidence.',
    image_sources: sources, cases: [], screenshots: [], failures: [] };
  const reportPath = path.join(outputDir, 'catalog-completion-qa.json');
  const persist = () => writeFile(reportPath, JSON.stringify(report, null, 2) + '\n');

  for (const width of [320, 390, 768, 1440]) {
    const context = await browser.newContext({ viewport: { width, height: 900 }, hasTouch: width < 768,
      reducedMotion: 'reduce', serviceWorkers: 'block' });
    const forbidden = [], pageErrors = [];
    let failOriginals = false;
    await context.route('**/*', route => {
      const request = route.request(), url = new URL(request.url());
      if (/\/api\/(analytics|clickout)/.test(url.pathname)) {
        forbidden.push(url.pathname);
        return route.abort();
      }
      if (url.pathname === '/api/session') return route.fulfill({ json: { session_id: 'isolated-catalog-qa-session' } });
      if (url.pathname.startsWith('/api/merchant-offers/')) return route.fulfill({ json: emptyOfferFixture(route) });
      if (url.pathname.startsWith('/api/')) return route.fulfill({ status: 503, json: { error: 'Isolated QA: API blocked' } });
      if (originalFixtures.has(url.href)) return failOriginals ? route.abort() :
        route.fulfill({ status: 200, contentType: 'image/png', body: originalFixtures.get(url.href) });
      if (url.origin === origin) return route.continue();
      return route.abort();
    });
    const page = await context.newPage();
    page.setDefaultTimeout(20_000);
    page.on('pageerror', error => pageErrors.push(String(error)));
    const capture = async label => {
      const file = `${label}-${width}.png`, target = path.join(outputDir, file);
      await page.screenshot({ path: target });
      report.screenshots.push({ file, width, sha256: createHash('sha256').update(await readFile(target)).digest('hex') });
    };
    const noOverflow = async () => assert.equal(await page.evaluate(() => document.documentElement.scrollWidth > innerWidth), false, `horizontal overflow at ${width}px`);
    try {
      await page.goto(`${origin}/start`, { waitUntil: 'networkidle' });
      await chooseMeasurement(page, 'denied');
      for (const [query, method] of [['Marwa', 'Enter'], ['YSL', 'button']]) {
        await page.goto(`${origin}/start`, { waitUntil: 'networkidle' });
        const search = page.getByLabel('Duft oder Marke suchen', { exact: true });
        await search.fill(query);
        await page.getByRole('button', { name: 'Treffer ansehen', exact: true }).waitFor();
        assert.equal(await page.locator('[data-dufynd-social-live-results] a').count(), 2);
        if (method === 'Enter') await search.press('Enter');
        else await page.getByRole('button', { name: 'Treffer ansehen', exact: true }).click();
        await page.waitForURL(url => url.pathname === '/duft' && url.searchParams.get('q') === query);
        await page.waitForFunction(q => document.querySelector('input[aria-label="Duft, Marke oder Profil"]')?.value === q || document.querySelector('input[type="search"]')?.value === q, query);
        await page.locator('.dufynd-catalog-card').first().waitFor();
        assert.equal(await page.locator('.dufynd-catalog-card').count(), 2);
        await noOverflow();
        report.cases.push({ width, scenario: 'ambiguous-search', query, method, result: 'catalog-with-two-variants' });
        if (query === 'Marwa') { await page.locator('#catalog-results').scrollIntoViewIfNeeded(); await capture('marwa-variant-choice'); }
      }
      await page.goto(`${origin}/start`, { waitUntil: 'networkidle' });
      await page.getByLabel('Duft oder Marke suchen', { exact: true }).fill('Marwa EDP 100ml');
      await page.getByRole('button', { name: 'Direkt öffnen', exact: true }).waitFor();
      await page.getByLabel('Duft oder Marke suchen', { exact: true }).press('Enter');
      await page.getByRole('heading', { name: 'Marwa', exact: true, level: 1 }).waitFor();
      assert.match(await page.getByLabel('Exakte Duftvariante', { exact: true }).innerText(), /Eau de Parfum[\s\S]*100 ml/);
      assert.ok(await page.locator('[data-dufynd-visual-state="missing"]').count() > 0, 'Missing original is explicit');
      await noOverflow();
      report.cases.push({ width, scenario: 'unique-variant-and-missing-original', result: 'exact-Marwa-EDP-100ml; truthful missing-image state' });
      await capture('marwa-detail');

      for (const route of ['/duftfinder', '/parfum-geschenkberater', '/parfum-alternativen']) {
        await page.goto(`${origin}${route}`, { waitUntil: 'networkidle' });
        const stage = page.locator('.dufynd-acquisition-stage');
        await stage.scrollIntoViewIfNeeded();
        const cards = stage.locator('[data-dufynd-acquisition-slot]');
        assert.equal(await cards.count(), 3);
        for (let index = 0; index < 3; index += 1) {
          const card = cards.nth(index), source = sources[index];
          const productImage = card.locator(`img[src=${JSON.stringify(source.image_url)}]`);
          await productImage.scrollIntoViewIfNeeded();
          await productImage.evaluate(image => image.decode());
          assert.ok(await productImage.evaluate(image => image.complete && image.naturalWidth > 0));
          assert.match(await productImage.getAttribute('alt'), /Eau de Parfum (?:75|90) ml/);
          assert.equal(await card.locator('img[src*="/products/pilot/"]').count(), 0);
        }
        await noOverflow();
        await stage.scrollIntoViewIfNeeded();
        await capture(route.slice(1));
        report.cases.push({ width, scenario: 'approved-original-acquisition', route, images_loaded: 3, generated_bottles: 0 });
      }

      await page.goto(`${origin}/duft?q=Libre`, { waitUntil: 'networkidle' });
      const filterToggle = page.locator('button[aria-controls="catalog-filter-panel"]');
      if (await filterToggle.isVisible() && await filterToggle.getAttribute('aria-expanded') === 'false') await filterToggle.click();
      await page.getByRole('region', { name: 'Duftkatalog filtern' }).getByRole('button', { name: 'Damen', exact: true }).click();
      const cards = page.locator('.dufynd-catalog-card');
      await cards.getByRole('heading', { name: 'Libre', exact: true }).waitFor();
      assert.equal(await cards.count(), 1);
      await cards.getByRole('button', { name: /für Vergleich auswählen/ }).click();
      await page.getByRole('searchbox', { name: 'Duft, Marke oder Profil' }).fill('Black Opium');
      await cards.getByRole('heading', { name: 'Black Opium', exact: true }).waitFor();
      await cards.getByRole('button', { name: /für Vergleich auswählen/ }).click();
      await page.getByRole('complementary', { name: 'Duftvergleich vorbereiten' }).getByRole('link', { name: 'Jetzt vergleichen →', exact: true }).click();
      await page.locator('.dufynd-comparison-live-stage').waitFor();
      assert.equal(await page.getByRole('combobox', { name: 'Duft 1', exact: true }).inputValue(), originalIds[0]);
      assert.equal(await page.getByRole('combobox', { name: 'Duft 2', exact: true }).inputValue(), originalIds[2]);
      await noOverflow();
      await page.locator('.dufynd-comparison-picker').scrollIntoViewIfNeeded();
      await capture('comparison');
      report.cases.push({ width, scenario: 'catalog-filter-comparison', audience: 'women', variants: [originalIds[0], originalIds[2]] });

      failOriginals = true;
      await page.goto(`${origin}/duftfinder`, { waitUntil: 'networkidle' });
      await page.locator('.dufynd-acquisition-stage').scrollIntoViewIfNeeded();
      await page.locator('.dufynd-acquisition-stage [data-dufynd-visual-state="unavailable"]').first().waitFor();
      assert.equal(await page.locator('.dufynd-acquisition-stage [data-dufynd-visual-state="unavailable"]').count(), 3);
      assert.equal(await page.locator('.dufynd-acquisition-stage img').count(), 0);
      await capture('original-source-unavailable');
      report.cases.push({ width, scenario: 'failed-original-not-a-pass', unavailable: 3, loaded: 0 });
      assert.deepEqual(forbidden, [], 'No analytics or affiliate clickout requests');
      assert.deepEqual(pageErrors, [], 'No browser runtime errors');
    } catch (error) {
      report.failures.push({ width, error: String(error), url: page.url(), pageErrors, forbidden });
      await capture('failure').catch(() => {});
      await persist();
      throw error;
    } finally {
      await context.close();
    }
    await persist();
  }
  report.completed_at = new Date().toISOString();
  await persist();
  return report;
}

if (import.meta.url === pathToFileURL(process.argv[1] || '').href) {
  const args = process.argv.slice(2);
  const option = (name, fallback) => args.includes(name) ? args[args.indexOf(name) + 1] : fallback;
  const playwright = await import(process.env.DUFYND_QA_PLAYWRIGHT_MODULE || 'playwright');
  const browser = await playwright.chromium.launch({ headless: true });
  try {
    const report = await verifyCatalogCompletion(browser, option('--base-url', 'http://127.0.0.1:3000'),
      path.resolve(option('--out', '.catalog-completion-qa')), option('--originals-dir', process.env.DUFYND_QA_ORIGINALS_DIR));
    console.log(JSON.stringify({ status: 'passed', cases: report.cases.length, screenshots: report.screenshots.length }));
  } finally { await browser.close(); }
}
