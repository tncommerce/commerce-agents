// Actual browser regression for a visitor who decides only after the product
// loaded. No preseeded permission, forced clicks or production merchant traffic.
import assert from 'node:assert/strict';
import { mkdir, writeFile } from 'node:fs/promises';
import path from 'node:path';

const PID = 'SC-RABANNE-1-MILLION-EDT-100';
const OFFER = 'qa-late-grant-rabanne';
const FIELDS = ['sid', 'src', 'cmp', 'content', 'measurement'];
const entry = '/duft/rabanne-1-million?qa=1&src=instagram&cmp=qa_late_grant&content=qa_current_product&measurement=granted-v1&sid=qa_shared_not_permission_123456';
const merchant = page => page.locator(`[data-merchant-offers] a[href*="/api/clickout/${OFFER}"]`).first();
const catalog = page => page.locator('nav[aria-label="Breadcrumb"] a').filter({hasText:'Düfte'});

async function waitForEvent(page, stats, name, count) {
  for (let attempt = 0; attempt < 100; attempt++) {
    if (stats.events.filter(e => e.event === name && e.product_id === PID).length >= count) return;
    await page.waitForTimeout(50);
  }
  assert.fail(`Missing ${name} for the currently consented product (wanted ${count})`);
}
async function settle(page) {
  await page.evaluate(() => new Promise(resolve => requestAnimationFrame(() => requestAnimationFrame(resolve))));
  await page.waitForTimeout(100);
}
async function choose(page, name, choice) {
  await page.getByRole('button', {name, exact:true}).click();
  await page.waitForFunction(value => document.querySelector('[data-measurement-choice]')?.getAttribute('data-measurement-choice') === value, choice);
}
async function rawMerchant(page) {
  // Intentionally no focus/pointer action: these must not be needed to repair hrefs.
  return new URL(await merchant(page).getAttribute('href'), page.url());
}

export async function verifyLateMeasurementGrant(browser, baseUrl, outputDir) {
  const origin = new URL(baseUrl).origin;
  assert.ok(['127.0.0.1', 'localhost', '[::1]'].includes(new URL(baseUrl).hostname));
  const out = path.join(outputDir, 'consent26-late-grant');
  await mkdir(out, {recursive:true});
  const results = [];
  for (const width of [320, 390, 768, 1440]) {
    const context = await browser.newContext({viewport:{width, height:900}, serviceWorkers:'block', reducedMotion:'reduce'});
    const stats = {events:[], sessions:0, offers:0, clickouts:0, unexpected:[]};
    try {
      await context.route('**/*', async route => {
        const request = route.request(), url = new URL(request.url());
        if (url.pathname === '/api/session') {
          stats.sessions++;
          return route.fulfill({json:{session_id:`qa-functional-late-${stats.sessions}-123456`}});
        }
        if (url.pathname === '/api/analytics/events') {
          assert.equal(url.searchParams.get('measurement'), 'granted-v1');
          stats.events.push(request.postDataJSON());
          return route.fulfill({json:{ok:true}});
        }
        if (url.pathname === `/api/merchant-offers/${PID}`) {
          stats.offers++;
          return route.fulfill({json:{product_id:PID, best_offer_id:OFFER, offers:[{
            offer_id:OFFER, product_id:PID, merchant_id:'perfumetrader', merchant_name:'Perfumetrader',
            price:99, shipping_cost:0, total_price:99, currency:'EUR', in_stock:true, affiliate_link:true,
            variant_label:'100 ml · Eau de Toilette', clickout_path:`/api/clickout/${OFFER}`,
            last_updated_at:new Date().toISOString(),
          }], affiliate_disclosure:'Synthetic local QA offer'}});
        }
        if (url.pathname.includes('/clickout/') || /\/merchant-partners\/[^/]+\/clickout$/.test(url.pathname)) {
          stats.clickouts++;
          return route.abort('blockedbyclient');
        }
        if (url.pathname === '/api/products') return route.fulfill({json:{products:[]}});
        if (url.pathname === '/api/merchant-partners') return route.fulfill({json:{partners:[]}});
        if (url.origin === origin && !url.pathname.startsWith('/api/')) return route.continue();
        stats.unexpected.push(`${url.origin}${url.pathname}`);
        return route.abort('blockedbyclient');
      });
      const page = await context.newPage();
      await page.goto(baseUrl + entry, {waitUntil:'domcontentloaded'});
      await page.locator('[data-measurement-panel]').waitFor();
      await merchant(page).waitFor();
      await settle(page);
      assert.equal(stats.events.length, 0, 'Mounted product must not measure before explicit choice');
      const before = await rawMerchant(page);
      for (const field of FIELDS) assert.equal(before.searchParams.has(field), false);
      const offersBefore = stats.offers;
      assert.ok(offersBefore > 0, 'Functional offers already loaded without optional analytics');

      await choose(page, 'Analyse erlauben', 'granted');
      await page.waitForFunction(offer => {
        const a = document.querySelector(`[data-merchant-offers] a[href*="/api/clickout/${offer}"]`);
        return a && new URL(a.href).searchParams.get('measurement') === 'granted-v1';
      }, OFFER);
      await waitForEvent(page, stats, 'fragrance_detail_view', 1);
      const allowed = await rawMerchant(page), sid = allowed.searchParams.get('sid');
      assert.match(sid || '', /^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i);
      assert.equal(allowed.searchParams.get('src'), 'instagram');
      assert.equal(allowed.searchParams.get('cmp'), 'qa_late_grant');
      assert.equal(allowed.searchParams.get('content'), 'qa_current_product');
      assert.ok(!sid.startsWith('qa-functional-'));
      assert.equal(stats.offers, offersBefore, 'Changing consent must not reload functional merchant offers');

      await page.waitForFunction(() => {
        const a = [...document.querySelectorAll('nav[aria-label="Breadcrumb"] a')].find(a => new URL(a.href).pathname === '/duft');
        return a && new URL(a.href).searchParams.get('cmp') === 'qa_late_grant';
      });
      assert.equal(new URL(await catalog(page).getAttribute('href'), page.url()).searchParams.get('sid'), sid);
      await page.locator('[data-merchant-offers]').scrollIntoViewIfNeeded();
      await waitForEvent(page, stats, 'offer_section_view', 1);
      await settle(page);
      for (const type of ['fragrance_detail_view', 'offer_section_view']) {
        const rows = stats.events.filter(e => e.event === type && e.product_id === PID);
        assert.equal(rows.length, 1, 'One current view, no replay of earlier interactions');
        assert.equal(rows[0].analytics_session_id, sid);
      }

      // Reaffirming the same enabled choice must not double count the product.
      await page.getByRole('button', {name:'Datenschutz-Einstellungen', exact:true}).click();
      await choose(page, 'Analyse erlauben', 'granted');
      await merchant(page).waitFor();
      await settle(page);
      for (const type of ['fragrance_detail_view', 'offer_section_view']) {
        assert.equal(stats.events.filter(e => e.event === type && e.product_id === PID).length, 1);
      }
      await choose(page, 'Analyse widerrufen', 'denied');
      await merchant(page).waitFor();
      await settle(page);
      const denied = await rawMerchant(page);
      const deniedCatalog = new URL(await catalog(page).getAttribute('href'), page.url());
      for (const field of FIELDS) {
        assert.equal(denied.searchParams.has(field), false);
        assert.equal(deniedCatalog.searchParams.has(field), false);
      }
      const eventsAtWithdrawal = stats.events.length;
      await page.locator('[data-merchant-offers]').scrollIntoViewIfNeeded();
      await settle(page);
      assert.equal(stats.events.length, eventsAtWithdrawal, 'Visible offers remain unmeasured after withdrawal');
      assert.equal(stats.offers, offersBefore);
      await page.screenshot({path:path.join(out, `withdrawn-${width}.png`)});

      await page.getByRole('button', {name:'Datenschutz-Einstellungen', exact:true}).click();
      await choose(page, 'Analyse erlauben', 'granted');
      await waitForEvent(page, stats, 'fragrance_detail_view', 2);
      await page.waitForFunction(offer => {
        const a = document.querySelector(`[data-merchant-offers] a[href*="/api/clickout/${offer}"]`);
        return a && new URL(a.href).searchParams.get('measurement') === 'granted-v1';
      }, OFFER);
      const regranted = await rawMerchant(page);
      assert.notEqual(regranted.searchParams.get('sid'), sid, 'Fresh grant cannot resurrect the withdrawn identity');
      assert.equal(regranted.searchParams.has('cmp'), false, 'Withdrawn campaign state is not replayed');
      assert.equal(stats.offers, offersBefore);
      assert.equal(stats.clickouts, 0);
      assert.deepEqual(stats.unexpected, []);
      results.push({width, case:'late-grant-current-product', passed:true, noOfferRefetch:true, noImplicitGrant:true, realMerchantClicks:0});
    } finally {
      await context.close();
    }
  }
  await writeFile(path.join(out, 'report.json'), JSON.stringify({status:'PASS', cases:results.length, results, realMerchantClicks:0, externalRequests:0}, null, 2));
  return results;
}
