import assert from "node:assert/strict";

export async function verifySocialSearchDismissal(browser, baseUrl) {
  for (const width of [390, 1440]) {
    const context = await browser.newContext({ viewport: { width, height: 900 } });
    const page = await context.newPage();
    try {
      await page.goto(`${baseUrl}/start`);
      const input = page.getByRole("searchbox", { name: "Duft oder Marke suchen", exact: true });
      const results = page.locator("[data-dufynd-social-live-results]");
      await input.fill("Naxos");
      await results.getByRole("link").first().focus();
      await page.keyboard.press("Escape");
      assert.equal(await results.count(), 0, "Escape must dismiss results when a result link has focus");
      assert.equal(await input.inputValue(), "Naxos", "dismissal must preserve the typed query");
      assert.equal(await input.evaluate((element) => element === document.activeElement), true);
      await page.keyboard.press("Tab");
      assert.equal(await page.evaluate(() => Boolean(document.activeElement?.closest("[data-dufynd-social-live-results]"))), false);
      await input.focus();
      await results.waitFor();
      await page.keyboard.press("Escape");
      assert.equal(await results.count(), 0, "Escape from the search field must dismiss without clearing it");
      assert.equal(await input.inputValue(), "Naxos");
      await input.fill("zzzz-no-fragrance");
      await results.waitFor();
      await page.keyboard.press("Escape");
      assert.equal(await results.count(), 0, "no-match results must also be dismissible");
      await input.fill("Naxos");
      await results.waitFor();
      await page.getByRole("link", { name: "Impressum", exact: true }).first().focus();
      assert.equal(await results.count(), 0, "moving focus outside search must dismiss the overlay");
      await input.focus();
      await results.waitFor();
      await results.getByRole("link").first().click();
      await page.waitForURL((url) => url.pathname === "/duft/xerjoff-naxos");
      await page.goto(`${baseUrl}/start`);
      await input.fill("Naxos");
      await page.keyboard.press("Escape");
      await page.keyboard.press("Enter");
      await page.waitForURL((url) => url.pathname === "/duft/xerjoff-naxos");
    } finally {
      await context.close();
    }
  }
}
