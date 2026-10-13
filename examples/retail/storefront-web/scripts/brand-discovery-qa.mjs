import assert from 'node:assert/strict';

// Adapted from PR #774 brand-pages-qa; only local static export may be exercised.
export async function verifyBrandDiscovery(browser, baseUrl) {
  const origin = new URL(baseUrl).origin;
  assert.ok(['127.0.0.1', 'localhost', '[::1]'].includes(new URL(baseUrl).hostname), 'local QA only');
  const checks = [];
  for (const width of [390, 1440]) {
    const context = await browser.newContext({ viewport: { width, height: 900 }, reducedMotion: 'reduce' });
    await context.route('**/*', async route => {
      const request = route.request(), url = new URL(request.url());
      if (url.origin !== origin) return route.abort();
      if (url.pathname.startsWith('/api/') || request.method() !== 'GET') {
        return route.fulfill({ status: 200, contentType: 'application/json', body: '{}' });
      }
      return route.continue();
    });
    try {
      const page = await context.newPage(), errors = [];
      page.on('pageerror', error => errors.push(error.message));
      await page.goto(`${origin}/duft`);
      await page.getByRole('link', { name: 'Marken A–Z', exact: true }).filter({ visible: true }).click();
      assert.equal(new URL(page.url()).pathname, '/marken');
      const brands = await page.locator('[data-brand-slug]').evaluateAll(nodes => nodes.map(node => ({
        href: node.getAttribute('href'), count: Number(node.querySelector('small').textContent.match(/\d+/)[0]),
      })));
      assert.ok(brands.length > 0);
      assert.equal(new Set(brands.map(b => b.href)).size, brands.length);
      assert.match(await page.locator('meta[name=robots]').getAttribute('content'), /noindex/);
      assert.ok(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth));
      await page.getByRole('searchbox').fill('CHANEL');
      assert.equal(await page.locator('[data-brand-slug]').count(), 1);
      await page.getByRole('searchbox').fill('no-such-brand-fixture');
      assert.equal(await page.locator('[data-brand-slug]').count(), 0);
      await page.getByRole('searchbox').fill('');
      const products = new Set();
      for (const brand of brands) {
        const response = await page.goto(`${origin}${brand.href}`);
        assert.equal(response.status(), 200);
        assert.equal(await page.locator('[data-brand-product]').count(), brand.count);
        assert.equal(new URL(await page.locator('link[rel=canonical]').getAttribute('href')).pathname, brand.href);
        assert.match(await page.locator('meta[name=robots]').getAttribute('content'), /noindex/);
        assert.equal(await page.locator('img, [data-offer-id]').count(), 0);
        assert.ok(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth));
        for (const id of await page.locator('[data-brand-product]').evaluateAll(nodes => nodes.map(n => n.getAttribute('data-brand-product')))) {
          assert.ok(!products.has(id)); products.add(id);
        }
      }
      assert.equal(products.size, brands.reduce((sum, b) => sum + b.count, 0));
      await page.goto(`${origin}/marken/rabanne`);
      const link = page.locator('[data-brand-product="SC-RABANNE-1-MILLION-EDT-100"]');
      const href = await link.getAttribute('href');
      await link.click();
      assert.equal(new URL(page.url()).pathname, href);
      assert.match(await page.locator('h1').innerText(), /1 Million/);
      assert.deepEqual(errors, []);
      checks.push({ label: `brand-discovery-${width}`, status: 'passed', brands: brands.length, products: products.size });
    } finally { await context.close(); }
  }
  return checks;
}
