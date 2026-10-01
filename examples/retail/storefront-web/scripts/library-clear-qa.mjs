import assert from "node:assert/strict";

const storageKey = "scentai_fragrance_library_v1";
const libraryEvent = "scentai:fragrance-library-changed";

export async function verifyLibraryClearRecovery(browser, baseUrl) {
  for (const [route, width, emptyTitle] of [
    ["merkliste", 390, "Noch nichts gemerkt"],
    ["sammlung", 1440, "Deine Sammlung ist noch leer"],
  ]) {
    const context = await browser.newContext({ viewport: { width, height: 900 } });
    const page = await context.newPage();
    const initial = { version: 1, wishlist: ["SC-XERJOFF-NAXOS-100"], owned: ["SC-LV-IMAGINATION-100"] };
    try {
      await page.goto(`${baseUrl}/${route}`);
      await page.evaluate(({ key, event, initial }) => {
        localStorage.setItem(key, JSON.stringify(initial));
        window.dispatchEvent(new CustomEvent(event));
      }, { key: storageKey, event: libraryEvent, initial });
      const cards = page.locator(".dufynd-library-card");
      await cards.first().waitFor();
      const clear = page.getByRole("button", { name: "Persönliche Duftdaten auf diesem Gerät löschen", exact: true });
      const persisted = () => page.evaluate((key) => JSON.parse(localStorage.getItem(key)), storageKey);

      page.once("dialog", (dialog) => dialog.dismiss());
      await clear.click();
      assert.equal(await cards.count(), 1, "cancelled deletion must retain the visible list");
      assert.deepEqual(await persisted(), initial);

      await page.evaluate(({ key, event }) => {
        window.libraryClearEvents = 0;
        window.addEventListener(event, () => { window.libraryClearEvents += 1; });
        window.originalStorageRemove = Storage.prototype.removeItem;
        Storage.prototype.removeItem = function (requestedKey) {
          if (requestedKey === key) throw new DOMException("Storage blocked", "SecurityError");
          return window.originalStorageRemove.call(this, requestedKey);
        };
      }, { key: storageKey, event: libraryEvent });
      for (let attempt = 0; attempt < 2; attempt += 1) {
        page.once("dialog", (dialog) => dialog.accept());
        await clear.click();
        await page.getByRole("status").filter({ hasText: "Löschen fehlgeschlagen." }).waitFor();
        assert.equal(await cards.count(), 1, "failed deletion must retain the visible list");
        assert.deepEqual(await persisted(), initial);
        assert.equal(await page.evaluate(() => window.libraryClearEvents), 0,
          "failed deletion must not broadcast a successful change");
      }

      await page.evaluate(() => { Storage.prototype.removeItem = window.originalStorageRemove; });
      page.once("dialog", (dialog) => dialog.accept());
      await clear.click();
      await page.getByRole("heading", { name: emptyTitle, exact: true }).waitFor();
      await page.getByRole("status").filter({ hasText: "Persönliche Duftdaten auf diesem Gerät gelöscht." }).waitFor();
      assert.equal(await persisted(), null, "successful retry must remove both lists from storage");
      assert.equal(await page.evaluate(() => window.libraryClearEvents), 1);
      await page.reload();
      await page.getByRole("heading", { name: emptyTitle, exact: true }).waitFor();
      assert.equal(await cards.count(), 0, "successful deletion must survive reload");
    } finally {
      await context.close();
    }
  }
}
