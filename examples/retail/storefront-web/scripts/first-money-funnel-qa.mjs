import assert from "node:assert/strict";

export async function verifyFirstMoneyFunnel(browser, baseUrl) {
  let cases = 0;
  for (const [slug, productId, offerId, merchant] of [
    ["rabanne-1-million", "SC-RABANNE-1-MILLION-EDT-100", "perfumetrader-rabanne-1-million-edt-100", "Perfumetrader"],
    ["parfums-de-marly-delina", "SC-PDM-DELINA-EDP-75", "notino-pdm-delina-edp-75", "Notino"],
  ]) {
    for (const source of ["instagram", "tiktok"]) {
      const context = await browser.newContext({ viewport: { width: 390, height: 844 } });
      try {
        const page = await context.newPage();
        const session = `qa-first-money-${slug}-${source}-session`;
        const campaign = "qa_first_money_funnel";
        const content = `qa_${slug}_${source}`;
        const events = [];
        let sessionRequests = 0;
        await page.route("**/api/session", (route) => {
          sessionRequests += 1;
          return route.fulfill({ json: { session_id: `${session}-${sessionRequests}` } });
        });
        await page.route("**/api/analytics/events", (route) => {
          assert.equal(route.request().postDataJSON().internal_qa, true);
          events.push({ ...route.request().postDataJSON(), session: route.request().headers()["x-session-id"] });
          return route.fulfill({ json: { ok: true } });
        });
        await page.route("**/api/merchant-offers/**", (route) => route.fulfill({
          json: {
            product_id: productId, best_offer_id: offerId, affiliate_disclosure: "QA fixture only",
            offers: [{
              offer_id: offerId, product_id: productId, merchant_id: merchant.toLowerCase(), merchant_name: merchant,
              price: 99, currency: "EUR", shipping_cost: 0, total_price: 99, in_stock: true,
              affiliate_link: true, clickout_path: `/api/clickout/${offerId}`,
              last_updated_at: "2026-10-04T12:00:00Z",
            }],
          },
        }));
        // First-party navigation only: no network redirect, click or sale is created.
        const response = await page.goto(`${baseUrl}/start?qa=1&src=${source}&cmp=${campaign}&content=${content}`);
        assert.ok(response?.ok());
        await page.waitForFunction(() => sessionStorage.getItem("dufynd_internal_qa_v1") === "1");
        const catalogLink = page.getByRole("link", { name: "Katalog entdecken", exact: true });
        await catalogLink.waitFor();
        const landingHref = new URL(await catalogLink.getAttribute("href"), baseUrl);
        for (const [key, value] of [["src", source], ["cmp", campaign], ["content", content]]) {
          assert.equal(landingHref.searchParams.get(key), value);
        }
        await catalogLink.click();
        await page.waitForURL((url) => url.pathname === "/duft");
        const productLink = page.locator(`a[href*="/duft/${slug}"]`);
        for (let attempt = 0; attempt < 6 && (await productLink.count()) === 0; attempt += 1) {
          const more = page.getByRole("button", { name: /Weitere \d+ Düfte anzeigen/ });
          if ((await more.count()) === 0) break;
          await more.click();
        }
        assert.ok((await productLink.count()) > 0, `${slug} missing from live catalog`);
        await productLink.first().click();
        await page.waitForURL((url) => url.pathname === `/duft/${slug}`);
        const offers = page.locator("[data-merchant-offers]");
        await offers.waitFor({ state: "visible" });
        await offers.scrollIntoViewIfNeeded();
        const link = offers.getByRole("link", { name: `Bei ${merchant} ansehen`, exact: true });
        await link.waitFor({ state: "visible" });
        const clickout = new URL(await link.getAttribute("href"));
        assert.equal(clickout.pathname, `/api/clickout/${offerId}`);
        for (const [key, value] of [["src", source], ["cmp", campaign], ["content", content], ["sid", `${session}-1`]]) {
          assert.equal(clickout.searchParams.get(key), value);
        }
        for (let attempt = 0; attempt < 100 && !events.some((e) => e.event === "offer_section_view"); attempt += 1) {
          await page.waitForTimeout(100);
        }
        for (const event of ["page_view", "fragrance_detail_view", "offer_section_view"]) {
          const row = events.find((e) => e.event === event);
          assert.ok(row, `${slug}/${source} missing ${event}`);
          assert.ok(row.session.startsWith(`${session}-`), "missing valid transport session");
          assert.equal(row.analytics_session_id, `${session}-1`, "navigation split the analytics funnel");
          assert.equal(row.acquisition_source, source);
          assert.equal(row.campaign_id, campaign);
          assert.equal(row.content_id, content);
          if (event !== "page_view") assert.equal(row.product_id, productId);
        }
        // Distinct transport sessions are allowed; the analytics identity must remain stable.
        assert.ok(sessionRequests >= 1);
        cases += 1;
      } finally {
        await context.close();
      }
    }
  }
  return cases;
}
