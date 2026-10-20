// Explicit local QA replay only. No live APIs, analytics, or merchant navigation.
import assert from 'node:assert/strict';
import { readFile, mkdir, writeFile } from 'node:fs/promises';
import { createHash } from 'node:crypto';
import { chromium } from 'playwright';
import { chooseMeasurement } from './measurement-choice-qa.mjs';

const [baseUrl, fixturePath, outputDir, imageManifest] = process.argv.slice(2);
assert.ok(['127.0.0.1', 'localhost'].includes(new URL(baseUrl).hostname));
const fixture = JSON.parse(await readFile(fixturePath, 'utf8'));
const rows = [
  ['parfums-de-marly-delina', 'SC-PDM-DELINA-EDP-75', 'Delina'],
  ['yves-saint-laurent-black-opium', 'SC-YSL-BLACK-OPIUM-EDP-90', 'Black Opium'],
  ['yves-saint-laurent-libre', 'SC-YSL-LIBRE-EDP-90', 'Libre'],
];
const cached = new Map();
if (imageManifest) for (const row of JSON.parse(await readFile(imageManifest, 'utf8'))) {
  const body = await readFile(row.path);
  assert.equal(createHash('sha256').update(body).digest('hex'), row.sha256);
  cached.set(row.url, body);
}
await mkdir(outputDir, { recursive: true });
const browser = await chromium.launch({ headless: true });
const results = [];
try {
  for (const width of [320, 390, 768, 1440]) {
    const context = await browser.newContext({ viewport: { width, height: 1000 }, hasTouch: width < 768, reducedMotion: 'reduce', serviceWorkers: 'block' });
    const page = await context.newPage();
    const clickouts = [], analytics = [], errors = [];
    let mode = 'available';
    await context.route('**/*', route => {
      const url = new URL(route.request().url());
      if (url.pathname.includes('/clickout/') || /jdoqocy|notino\./.test(url.hostname)) {
        clickouts.push(url.href); return route.abort();
      }
      if (/\/api\/(analytics|session)/.test(url.pathname)) { analytics.push(url.pathname); return route.abort(); }
      if (url.pathname.startsWith('/api/merchant-offers/')) {
        const id = decodeURIComponent(url.pathname.slice('/api/merchant-offers/'.length));
        const payload = fixture.payloads[id];
        assert.ok(payload, `Only the three scoped product requests: ${id}`);
        if (mode === 'error') return route.fulfill({ status: 503, body: 'Synthetic local QA error' });
        return route.fulfill({ json: mode === 'empty' ? { ...payload, offers: [], best_offer_id: null }
          : mode === 'wrong' ? { ...payload, product_id: 'SC-SYNTHETIC-WRONG' } : payload });
      }
      if (cached.has(url.href)) return route.fulfill({ body: cached.get(url.href), contentType: url.pathname.endsWith('.webp') ? 'image/webp' : 'image/png' });
      if (url.origin === new URL(baseUrl).origin) return route.continue();
      return route.abort();
    });
    page.on('pageerror', e => errors.push(String(e)));
    for (const [slug, id, name] of rows) {
      mode = 'available';
      await page.goto(`${baseUrl}/duft/${slug}`);
      await chooseMeasurement(page, 'denied');
      assert.equal(await page.locator('h1').textContent(), name);
      const offer = fixture.payloads[id].offers[0];
      const section = page.locator('[data-merchant-offers][data-offer-state="available"]').first();
      await section.waitFor();
      assert.match(await section.innerText(), new RegExp(offer.variant_label.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')));
      assert.match(await section.innerText(), new RegExp(`${offer.total_price},00`));
      assert.match(await section.locator('[data-offer-breakdown]').innerText(), /Versand\s+0,00/);
      const action = section.getByRole('link', { name: /Bei Notino ansehen/ });
      assert.ok((await action.getAttribute('href')).includes(`/api/clickout/${offer.offer_id}`));
      assert.ok((await action.boundingBox()).height >= 44);
      await action.focus();
      await page.keyboard.press('Shift+Tab');
      await page.keyboard.press('Tab');
      assert.ok(await action.evaluate(el => el === document.activeElement));
      assert.notEqual(await action.evaluate(el => getComputedStyle(el).outlineStyle), 'none');
      assert.ok(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth));
      await section.screenshot({ path: `${outputDir}/${slug}-${width}.png` });
      results.push({ width, product_id: id, offer_id: offer.offer_id, variant: offer.variant_label, price: offer.price, shipping: offer.shipping_cost, total: offer.total_price, status: 'passed' });
      for (const invalid of ['empty', 'error', 'wrong']) {
        mode = invalid;
        await page.reload();
        await page.waitForFunction(() => { const state = document.querySelector('[data-offer-state]')?.getAttribute('data-offer-state'); return state && state !== 'loading'; });
        assert.equal(await page.locator('a[href*="/api/clickout/"]').count(), 0, `${id}: ${invalid} cannot show a purchase action`);
      }
    }
    assert.deepEqual(clickouts, []);
    assert.deepEqual(analytics, []);
    assert.deepEqual(errors, []);
    await context.close();
  }
} finally { await browser.close(); }
await writeFile(`${outputDir}/report.json`, JSON.stringify({ kind: 'local_data_bound_replay_not_production', merchant_offers_sha256: fixture.merchant_offers_sha256, widths: [320,390,768,1440], results, negative_cases: ['empty', 'HTTP_503', 'wrong_product'], analytics_requests: 0, merchant_clickouts: 0 }, null, 2) + '\n');
console.log(`Notino local replay: ${results.length} offer views; 36 negative views; zero analytics/clickouts.`);
