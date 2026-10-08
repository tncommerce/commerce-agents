import assert from "node:assert/strict";

export async function verifyOfferRecovery(browser, baseUrl) {
  let cases = 0;
  for (const width of [320, 390, 1440]) {
    for (const mode of ["empty", "error", "available"]) {
      const context = await browser.newContext({ viewport: { width, height: 844 } });
      try {
        const page = await context.newPage();
        await page.route("**/api/**", (route) => route.fulfill({ json: {} }));
        await page.route("**/api/session", (route) => route.fulfill({ json: { session_id: "qa-offer-recovery-session" } }));
        await page.route("**/api/merchant-offers/**", (route) => mode === "error"
          ? route.fulfill({ status: 503, body: "unavailable" })
          : route.fulfill({ json: {
            product_id: "SC-XERJOFF-NAXOS-100", best_offer_id: "qa-offer",
            offers: mode === "available" ? [{
              offer_id: "qa-offer", merchant_name: "QA Merchant", price: 99, total_price: 99,
              currency: "EUR", in_stock: true, affiliate_link: false,
              clickout_path: "/api/clickout/qa-offer", last_updated_at: "2026-10-08T10:00:00Z",
            }] : [],
          } }));
        await page.goto(`${baseUrl}/duft/xerjoff-naxos?src=instagram&cmp=qa_recovery&content=qa_final`);
        const recovery = page.getByRole("navigation", { name: "Weitere Wege zum passenden Duft" });
        if (mode === "available") {
          await page.locator("[data-merchant-offers]").waitFor();
          assert.equal(await recovery.count(), 0, "available offers must keep the normal purchase flow");
        } else {
          await recovery.waitFor();
          const catalog = recovery.getByRole("link", { name: "Weitere Düfte & Angebote entdecken", exact: true });
          await page.waitForFunction(() => document.querySelector('nav[aria-label="Weitere Wege zum passenden Duft"] a[href*="/duft"]')?.getAttribute("href")?.includes("cmp=qa_recovery"));
          const href = new URL(await catalog.getAttribute("href"), baseUrl);
          for (const [key, value] of [["src", "instagram"], ["cmp", "qa_recovery"], ["content", "qa_final"]]) {
            assert.equal(href.searchParams.get(key), value);
          }
          const alternatives = recovery.getByRole("link", { name: "Ähnliche Düfte entdecken", exact: true });
          assert.equal(await alternatives.getAttribute("href"), "#alternativen");
          await alternatives.click();
          assert.equal(new URL(page.url()).hash, "#alternativen");
          const target = await alternatives.boundingBox();
          assert.ok(target.height >= 44, "recovery actions need a usable mobile tap target");
        }
        assert.ok(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth), "page must not overflow horizontally");
        cases += 1;
      } finally {
        await context.close();
      }
    }
  }
  return cases;
}
