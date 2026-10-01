import assert from "node:assert/strict";

export async function verifyLibrarySaveRecovery(browser, baseUrl) {
  const key = "scentai_fragrance_library_v1";
  const productId = "SC-XERJOFF-NAXOS-100";
  for (const width of [390, 1440]) {
    const context = await browser.newContext({ viewport: { width, height: 900 } });
    const page = await context.newPage();
    try {
      await page.goto(`${baseUrl}/duft/xerjoff-naxos`);
      const wishlist = page.getByRole("button", { name: /Merken|Gemerkt|Bereits in Sammlung/ });
      const collection = page.getByRole("button", { name: /Meine Sammlung|In meiner Sammlung/ });
      await wishlist.waitFor();
      const error = page.getByRole("status").filter({ hasText: "Änderung konnte nicht gespeichert werden." });
      const stored = () => page.evaluate((key) => JSON.parse(localStorage.getItem(key)) || { version: 1, wishlist: [], owned: [] }, key);
      const blockWrites = () => page.evaluate((key) => {
        window.originalLibrarySet = Storage.prototype.setItem;
        Storage.prototype.setItem = function (requestedKey, value) {
          if (requestedKey === key) throw new DOMException("Storage full", "QuotaExceededError");
          return window.originalLibrarySet.call(this, requestedKey, value);
        };
      }, key);
      const restoreWrites = () => page.evaluate(() => { Storage.prototype.setItem = window.originalLibrarySet; });

      await blockWrites();
      await wishlist.click();
      await error.waitFor();
      assert.equal(await wishlist.getAttribute("aria-pressed"), "false");
      assert.deepEqual((await stored()).wishlist, []);
      await restoreWrites();
      await wishlist.click();
      await page.getByRole("button", { name: "✓ Gemerkt", exact: true }).waitFor();
      assert.equal(await error.count(), 0);
      assert.deepEqual((await stored()).wishlist, [productId]);

      await blockWrites();
      await collection.click();
      await error.waitFor();
      assert.equal(await collection.getAttribute("aria-pressed"), "false");
      assert.deepEqual(await stored(), { version: 1, owned: [], wishlist: [productId] });
      await restoreWrites();
      await collection.click();
      await page.getByRole("button", { name: "✓ In meiner Sammlung", exact: true }).waitFor();
      assert.equal(await error.count(), 0);
      assert.deepEqual(await stored(), { version: 1, owned: [productId], wishlist: [] });
      assert.equal(await wishlist.isDisabled(), true);

      await blockWrites();
      await collection.click();
      await error.waitFor();
      assert.equal(await collection.getAttribute("aria-pressed"), "true");
      assert.deepEqual((await stored()).owned, [productId]);
      await restoreWrites();
      await collection.click();
      await page.getByRole("button", { name: "+ Meine Sammlung", exact: true }).waitFor();
      assert.equal(await error.count(), 0);
      assert.deepEqual((await stored()).owned, []);

      await wishlist.click();
      await page.getByRole("button", { name: "✓ Gemerkt", exact: true }).waitFor();
      await blockWrites();
      await wishlist.click();
      await error.waitFor();
      assert.equal(await wishlist.getAttribute("aria-pressed"), "true");
      assert.deepEqual((await stored()).wishlist, [productId]);
      await restoreWrites();
      await wishlist.click();
      await page.getByRole("button", { name: "♡ Merken", exact: true }).waitFor();
      assert.equal(await error.count(), 0);
      assert.deepEqual((await stored()).wishlist, []);
      await page.reload();
      await page.getByRole("button", { name: "♡ Merken", exact: true }).waitFor();
      assert.equal(await wishlist.getAttribute("aria-pressed"), "false");
      assert.equal(await collection.getAttribute("aria-pressed"), "false");
    } finally {
      await context.close();
    }
  }
}
