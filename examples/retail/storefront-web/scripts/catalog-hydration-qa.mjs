import assert from 'node:assert/strict';
import { createHash } from 'node:crypto';
import { mkdir, readFile, writeFile } from 'node:fs/promises';
import path from 'node:path';
import { chooseMeasurement } from './measurement-choice-qa.mjs';
import { emptyOfferFixture } from './merchant-offer-fixture-qa.mjs';

const args = process.argv.slice(2);
const option = (key, fallback) => args.includes(key) ? args[args.indexOf(key) + 1] : fallback;
const origin = new URL(option('--base-url', 'http://127.0.0.1:3000')).origin;
assert.ok(['127.0.0.1', 'localhost', '[::1]'].includes(new URL(origin).hostname));
const outputDir = path.resolve(option('--out', '.catalog-hydration-qa'));
await mkdir(outputDir, { recursive: true });
const report = { kind: 'local-profile-hydration-and-responsive-description', started_at: new Date().toISOString(),
  cases: [], screenshots: [], console_errors: [], page_errors: [], source_hashes: [] };
for (const file of ['../lib/analytics.ts', '../components/FragranceDetailPage.tsx', '../components/FragranceNoteSculpture.tsx', '../lib/generated/public-catalog.json']) {
  report.source_hashes.push({ file, sha256: createHash('sha256').update(await readFile(new URL(file, import.meta.url))).digest('hex') });
}
const playwright = await import(process.env.DUFYND_QA_PLAYWRIGHT_MODULE || 'playwright');
const browser = await playwright.chromium.launch({ headless: true });
try {
  const context = await browser.newContext({ viewport: { width: 390, height: 900 }, reducedMotion: 'reduce', serviceWorkers: 'block' });
  const forbidden = [];
  await context.route('**/*', route => {
    const url = new URL(route.request().url());
    if (/\/api\/(analytics|clickout)/.test(url.pathname)) { forbidden.push(url.pathname); return route.abort(); }
    if (url.pathname === '/api/session') return route.fulfill({ json: { session_id: 'isolated-hydration-qa-session' } });
    if (url.pathname.startsWith('/api/merchant-offers/')) return route.fulfill({ json: emptyOfferFixture(route) });
    if (url.pathname.startsWith('/api/')) return route.fulfill({ status: 503, json: { error: 'Isolated QA: API blocked' } });
    if (url.origin === origin) return route.continue();
    return route.abort();
  });
  const page = await context.newPage();
  page.on('pageerror', error => report.page_errors.push(String(error)));
  page.on('console', message => {
    // External images are deliberately blocked in this helper-only test.
    if (message.type() === 'error' && !message.text().includes('net::ERR_FAILED')) report.console_errors.push(message.text());
  });
  await page.goto(`${origin}/duft/essential-parfums-bois-imperial?q=Rosa%20Pfeffer&src=qa_fixture&sid=old_fixture_identifier`, { waitUntil: 'networkidle' });
  await chooseMeasurement(page, 'denied');
  const clean = new URL(page.url());
  assert.equal(clean.searchParams.get('q'), 'Rosa Pfeffer');
  for (const key of ['sid', 'src', 'measurement']) assert.equal(clean.searchParams.has(key), false);
  await page.reload({ waitUntil: 'networkidle' });
  await page.locator('[data-dufynd-profile-description]').waitFor();
  assert.ok(await page.getByRole('link', { name: 'Weitere Düfte mit Thailändisches Basilikum entdecken', exact: true }).count());
  assert.equal(report.console_errors.filter(value => /hydrat/i.test(value)).length, 0, 'No hydration attribute mismatch after privacy cleanup');
  report.cases.push({ width: 390, scenario: 'functional-note-links-hydrate-and-denial-cleans-optional-fields', passed: true });

  for (const width of [320, 768, 1440]) {
    await page.setViewportSize({ width, height: 900 });
    await page.goto(`${origin}/duft/clive-christian-jump-up-and-kiss-me-hedonistic`, { waitUntil: 'networkidle' });
    const description = page.locator('[data-dufynd-profile-description]');
    assert.match(await description.innerText(), /Jump Up and Kiss Me Hedonistic verbindet schwarze Kirsche/);
    assert.equal(await page.evaluate(() => document.documentElement.scrollWidth > innerWidth), false);
    const file = `profile-clive-description-${width}.png`;
    await page.locator('#duftprofil').screenshot({ path: path.join(outputDir, file) });
    report.screenshots.push({ file, width, sha256: createHash('sha256').update(await readFile(path.join(outputDir, file))).digest('hex') });
    report.cases.push({ width, scenario: 'new-long-profile-description', visible: true, overflow: false });
  }
  assert.deepEqual(forbidden, [], 'No analytics or affiliate clickout requests');
  assert.deepEqual(report.page_errors, []);
  assert.deepEqual(report.console_errors, []);
  report.completed_at = new Date().toISOString();
  await writeFile(path.join(outputDir, 'catalog-hydration-qa.json'), JSON.stringify(report, null, 2) + '\n');
  console.log(JSON.stringify({ status: 'passed', cases: report.cases.length, hydration_warnings: 0, analytics_requests: 0, affiliate_clickouts: 0 }));
} catch (error) {
  report.failure = String(error);
  await writeFile(path.join(outputDir, 'catalog-hydration-qa.json'), JSON.stringify(report, null, 2) + '\n');
  throw error;
} finally { await browser.close(); }
