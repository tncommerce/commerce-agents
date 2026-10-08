import assert from 'node:assert/strict';

export async function verifyCatalogRecovery(browser, baseUrl) {
  let cases = 0;
  for (const width of [320, 390, 1440]) {
    const page = await browser.newPage({ viewport: { width, height: 900 } });
    try {
      await page.goto(`${baseUrl}/duft?q=Delina&marke=Dior`);
      await page.getByRole('heading', { name: 'Keine passenden Düfte gefunden' }).waitFor();
      const recovery = page.getByRole('button', { name: /Filter lösen.*Treffer für/ });
      await recovery.waitFor();
      const product = page.getByRole('link', { name: /Parfums de Marly.*Delina/i });
      assert.ok(await product.count() > 0, 'Existing product has a direct recovery link');
      assert.ok((await product.first().getAttribute('href')).includes('/duft/'));
      assert.ok(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth), 'No horizontal overflow');
      await recovery.click();
      await page.getByRole('heading', { name: 'Keine passenden Düfte gefunden' }).waitFor({ state: 'hidden' });
      assert.ok((await page.locator('input[type=search]').inputValue()).includes('Delina'), 'Search preserved');
      cases++;
      await page.goto(`${baseUrl}/duft?q=Delina+zzzzunknown`);
      const relaxed = page.getByRole('button', { name: /Suche lockern: „Delina“.*Treffer/ });
      await relaxed.waitFor();
      await relaxed.click();
      await page.getByRole('heading', { name: 'Keine passenden Düfte gefunden' }).waitFor({ state: 'hidden' });
      cases++;
      await page.goto(`${baseUrl}/duft?q=zzzzunknown`);
      await page.getByRole('heading', { name: 'Keine passenden Düfte gefunden' }).waitFor();
      assert.equal(await page.getByRole('button', { name: /Suche lockern:/ }).count(), 0, 'No invented suggestion');
      cases++;
    } finally { await page.close(); }
  }
  return cases;
}
