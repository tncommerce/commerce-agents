// Targeted combined #840 + #823 check. Local static export only; no real offers.
import assert from 'node:assert/strict';
import { mkdir, writeFile } from 'node:fs/promises';
import path from 'node:path';
import { verifyConversionSearch } from '../../examples/retail/storefront-web/scripts/conversion-search-qa.mjs';
import { verifyLateMeasurementGrant } from '../../examples/retail/storefront-web/scripts/measurement-late-grant-qa.mjs';

const baseUrl = process.argv[2];
const outputDir = path.resolve(process.argv[3] || '/tmp/dufynd-combined-browser');
assert.ok(baseUrl, 'Pass a running local static-export URL');
const origin = new URL(baseUrl).origin;
assert.ok(['127.0.0.1', 'localhost', '[::1]'].includes(new URL(baseUrl).hostname));
const { chromium } = await import(process.env.DUFYND_PLAYWRIGHT_MODULE || 'playwright');
await mkdir(outputDir, { recursive: true });
const browser = await chromium.launch({ headless: true, args: ['--no-sandbox'] });
const stats = { externalRequestsBlocked: 0, externalRequestsSent: 0, clickoutAttempts: 0, pageErrors: [] };
const guardedBrowser = {
  async newContext(options = {}) {
    const context = await browser.newContext({ ...options, serviceWorkers: 'block' });
    await context.route('**/*', route => {
      const url = new URL(route.request().url());
      if (/\/clickout(?:\/|$)/.test(url.pathname)) {
        stats.clickoutAttempts++;
        return route.abort('blockedbyclient');
      }
      if (url.origin !== origin) {
        stats.externalRequestsBlocked++;
        return route.abort('blockedbyclient');
      }
      return route.continue();
    });
    context.on('page', page => page.on('pageerror', error => stats.pageErrors.push(error.message)));
    return context;
  },
};

async function verifyNoObserver() {
  const results = [];
  for (const width of [320, 1440]) {
    const context = await guardedBrowser.newContext({ viewport: { width, height: 900 }, reducedMotion: 'reduce' });
    const events = [];
    let offers = 0;
    await context.addInitScript(() => { Object.defineProperty(window, 'IntersectionObserver', { configurable: true, value: undefined }); });
    await context.route('**/api/**', route => {
      const request = route.request(), url = new URL(request.url());
      if (url.pathname.includes('/clickout/')) {
        stats.clickoutAttempts++;
        return route.abort('blockedbyclient');
      }
      if (url.pathname === '/api/analytics/events') {
        events.push(request.postDataJSON());
        return route.fulfill({ json: { ok: true } });
      }
      if (url.pathname === '/api/session') return route.fulfill({ json: { session_id: 'qa-local-functional-no-observer' } });
      if (url.pathname === '/api/merchant-offers/SC-RABANNE-1-MILLION-EDT-100') {
        offers++;
        return route.fulfill({ json: {
          product_id: 'SC-RABANNE-1-MILLION-EDT-100', best_offer_id: 'qa-local-no-observer',
          offers: [{ offer_id: 'qa-local-no-observer', product_id: 'SC-RABANNE-1-MILLION-EDT-100',
            merchant_id: 'perfumetrader', merchant_name: 'Perfumetrader', price: 99, shipping_cost: 0,
            total_price: 99, currency: 'EUR', in_stock: true, affiliate_link: true,
            variant_label: '100 ml · Eau de Toilette', clickout_path: '/api/clickout/qa-local-no-observer',
            last_updated_at: new Date().toISOString() }], affiliate_disclosure: 'Synthetic local QA only',
        } });
      }
      return route.fulfill({ status: 503, json: { detail: 'Unneeded local QA API' } });
    });
    try {
      const page = await context.newPage();
      await page.goto(baseUrl + '/duft/rabanne-1-million?qa=1', { waitUntil: 'domcontentloaded' });
      const cta = page.locator('[data-merchant-offers] a[href*="/api/clickout/qa-local-no-observer"]').first();
      await cta.waitFor({ state: 'attached' });
      assert.deepEqual(events, [], 'No consent means no measurement');
      await page.getByRole('button', { name: 'Analyse erlauben', exact: true }).click();
      await page.waitForFunction(() => document.querySelector('[data-measurement-choice]')?.getAttribute('data-measurement-choice') === 'granted');
      await page.locator('[data-merchant-offers]').scrollIntoViewIfNeeded();
      await cta.waitFor({ state: 'visible' });
      for (let attempt = 0; attempt < 60 && !events.some(e => e.event === 'fragrance_detail_view'); attempt++) await page.waitForTimeout(50);
      await page.waitForTimeout(400);
      assert.equal(await page.evaluate(() => typeof IntersectionObserver), 'undefined');
      assert.ok(offers > 0, 'Functional offer was loaded');
      assert.ok(events.some(e => e.event === 'fragrance_detail_view'), 'Consent actually activated product measurement');
      assert.equal(events.filter(e => e.event === 'offer_section_view').length, 0, 'Missing observer cannot fabricate visibility');
      assert.match(await cta.getAttribute('href'), /\/api\/clickout\/qa-local-no-observer/);
      results.push({ width, noObserver: true, functionalCtaVisible: true, unprovedOfferViews: 0, syntheticFixture: true });
    } finally { await context.close(); }
  }
  return results;
}

let report;
try {
  const lateGrant = await verifyLateMeasurementGrant(guardedBrowser, baseUrl, outputDir);
  console.log(JSON.stringify({ suite: 'combined-late-grant', cases: lateGrant.length, status: 'PASS' }));
  const noObserver = await verifyNoObserver();
  console.log(JSON.stringify({ suite: 'combined-no-observer-real-browser', cases: noObserver.length, status: 'PASS' }));
  const conversion = await verifyConversionSearch(guardedBrowser, baseUrl, outputDir);
  console.log(JSON.stringify({ suite: 'combined-conversion-search', cases: conversion.length, status: 'PASS' }));
  assert.equal(stats.clickoutAttempts, 0);
  assert.deepEqual(stats.pageErrors, []);
  report = { status: 'PASS', browser: browser.version(), cases: lateGrant.length + noObserver.length + conversion.length,
    lateGrant, noObserver, conversion, ...stats, realMerchantClicks: 0,
    note: 'Combined dependency/privacy tree; local synthetic API fixtures; merchant images aborted, not visually recertified.' };
} catch (error) {
  report = { status: 'FAIL', error: error.stack, ...stats };
  throw error;
} finally {
  await writeFile(path.join(outputDir, 'report.json'), JSON.stringify(report, null, 2) + '\n');
  await browser.close();
}
console.log(JSON.stringify({ status: report.status, cases: report.cases, realMerchantClicks: 0, externalRequestsSent: 0 }));
