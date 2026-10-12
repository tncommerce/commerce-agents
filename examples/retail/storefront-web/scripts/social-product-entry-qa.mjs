import assert from "node:assert/strict";
import path from "node:path";

// Artificial local offer. This is neither a current merchant quote nor revenue.
const productId = "SC-RABANNE-1-MILLION-EDT-100";
const offerId = "qa-perfumetrader-social-entry";
const offer = {
  offer_id: offerId, product_id: productId, merchant_id: "perfumetrader",
  merchant_name: "Perfumetrader", price: 90, currency: "EUR", shipping_cost: 5,
  shipping_label: "5,00 € Versand (QA)", total_price: 95, in_stock: true,
  variant_label: "100 ml · Eau de Toilette", affiliate_link: true,
  clickout_path: `/api/clickout/${offerId}`, last_updated_at: "2026-10-12T00:00:00Z",
};

export async function verifySocialProductEntry(browser, baseUrl, outputDir) {
  const measurements = [];
  for (const width of [390, 1440]) {
    for (const source of ["instagram", "youtube"]) {
      const context = await browser.newContext({
        viewport: { width, height: 900 }, serviceWorkers: "block", reducedMotion: "reduce",
      });
      try {
        const page = await context.newPage();
        const events = [];
        const forbidden = [];
        let offers = [{ ...offer }];
        const session = `qa-social-${source}-${width}`;
        // Default-deny external traffic, all clickouts, and unmocked API routes.
        await context.route("**/*", (route) => {
          const url = new URL(route.request().url());
          if (url.pathname === "/api/session") return route.fulfill({ json: { session_id: session } });
          if (url.pathname === "/api/analytics/events") {
            events.push(route.request().postDataJSON());
            return route.fulfill({ json: { ok: true } });
          }
          if (url.pathname === `/api/merchant-offers/${productId}`) {
            return route.fulfill({ json: { product_id: productId, best_offer_id: offerId, offers, affiliate_disclosure: "QA fixture" } });
          }
          if (url.pathname.startsWith("/api/") || url.origin !== new URL(baseUrl).origin) {
            forbidden.push(url.pathname);
            return route.abort();
          }
          return route.continue();
        });
        const campaign = "qa_social_product_entry";
        const content = `qa_direct_${source}`;
        // Instagram's short keys and the already supported UTM aliases.
        const params = source === "instagram"
          ? `src=${source}&cmp=${campaign}&content=${content}`
          : `utm_source=${source}&utm_campaign=${campaign}&utm_content=${content}`;
        await page.goto(`${baseUrl}/duft/rabanne-1-million?qa=1&${params}`);
        const merchant = page.getByRole("link", { name: "Bei Perfumetrader ansehen", exact: true });
        await merchant.waitFor();
        await page.evaluate(() => document.fonts.ready);
        const hero = page.locator(".dufynd-fragrance-hero");
        assert.equal(await hero.getAttribute("data-dufynd-photo-hold"), "true");
        assert.equal(await hero.locator("img").count(), 0, "no unapproved bottle photo");
        assert.match(await hero.innerText(), /EDT[\s\S]*100 ml/);
        assert.match(await hero.innerText(), /Originalfoto in Prüfung/);
        const metrics = await page.evaluate(() => ({
          stage_height: document.querySelector(".dufynd-fragrance-stage-shell").getBoundingClientRect().height,
          cta_bottom: document.querySelector("#dufynd-hero-offer-cta").getBoundingClientRect().bottom,
          offers_top: document.querySelector("#angebote").getBoundingClientRect().top,
          overflow: document.documentElement.scrollWidth > innerWidth,
        }));
        assert.ok(metrics.stage_height <= (width === 390 ? 64 : 96), JSON.stringify(metrics));
        assert.ok(metrics.cta_bottom < (width === 390 ? 520 : 500), JSON.stringify(metrics));
        assert.ok(metrics.offers_top < (width === 390 ? 780 : 650), JSON.stringify(metrics));
        assert.equal(metrics.overflow, false);
        measurements.push({ source, width, ...metrics });
        const section = page.locator("[data-merchant-offers]");
        assert.match(await section.innerText(), /Gesamtpreis inkl. Versand/);
        assert.doesNotMatch(await section.innerText(), /Bester Gesamtpreis|Beste verfügbare Option/);
        assert.match(await section.innerText(), /Werbung · Partnerlink/);
        const clickout = new URL(await merchant.getAttribute("href"), baseUrl);
        assert.equal(clickout.pathname, `/api/clickout/${offerId}`);
        for (const [key, value] of [["src", source], ["cmp", campaign], ["content", content], ["sid", session]]) {
          assert.equal(clickout.searchParams.get(key), value);
        }
        assert.match(await merchant.getAttribute("rel"), /sponsored/);
        const catalog = page.locator('nav[aria-label="Breadcrumb"] a').filter({ hasText: "Düfte" });
        const href = new URL(await catalog.getAttribute("href"), baseUrl);
        assert.equal(href.pathname, "/duft");
        for (const [key, value] of [["src", source], ["cmp", campaign], ["content", content]]) {
          assert.equal(href.searchParams.get(key), value);
        }
        if (source === "instagram") {
          await page.screenshot({ path: path.join(outputDir, `social-product-fixture-${width}.png`), fullPage: true });
          await page.screenshot({ path: path.join(outputDir, `social-product-fixture-${width}-viewport.png`) });
        }
        await page.locator("#dufynd-hero-offer-cta").click(); // Internal anchor only.
        await page.waitForFunction(() => location.hash === "#angebote");
        for (let attempt = 0; attempt < 40 && !events.some((e) => e.event === "offer_section_open"); attempt += 1) {
          await page.waitForTimeout(50);
        }
        assert.ok(events.some((e) => e.event === "fragrance_detail_view" && e.product_id === productId));
        assert.ok(events.some((e) => e.event === "offer_section_open"));
        for (const event of events) {
          assert.equal(event.internal_qa, true);
          assert.equal(event.acquisition_source, source);
          assert.equal(event.campaign_id, campaign);
          assert.equal(event.content_id, content);
        }
        assert.deepEqual(forbidden.filter((p) => p.startsWith("/api/")), [], "no clickout or unmocked analytics request");
        if (width === 390 && source === "instagram") {
          offers = [{ ...offer, total_price: null, shipping_cost: null, shipping_label: null }];
          await page.reload();
          await merchant.waitFor();
          assert.equal(await page.locator("[data-offer-price-basis]").count(), 0);
          assert.match(await section.innerText(), /zzgl. ggf. Versand/);
          offers = [{ ...offer }, { ...offer, offer_id: "qa-second", merchant_name: "QA second", total_price: 100 }];
          await page.reload();
          await merchant.waitFor();
          assert.match(await section.innerText(), /Bester Gesamtpreis · hier gelistet/);
        }
      } finally {
        await context.close();
      }
    }
  }
  return measurements;
}
