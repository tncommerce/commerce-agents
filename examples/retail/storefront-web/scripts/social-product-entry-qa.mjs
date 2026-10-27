import assert from "node:assert/strict";
import path from "node:path";
import { writeFile } from "node:fs/promises";
import { createHash } from "node:crypto";
import { readFileSync } from "node:fs";

// Artificial local offer. This is neither a current merchant quote nor revenue.
const productId = "SC-RABANNE-1-MILLION-EDT-100";
const approvedRabanne = JSON.parse(readFileSync(
  new URL("../lib/generated/original-photos.json", import.meta.url), "utf8",
)).find((photo) => photo.product_id === productId);
assert.ok(approvedRabanne &&
  approvedRabanne.url === "https://www.topparfuemerie.de/media/catalog/product/7/0/707368_3349666007921_051.png" &&
  approvedRabanne.volume_ml === 100 &&
  approvedRabanne.rights_basis_id === "awin_top_parfuemerie_feed_materials_20260928",
  "Social entry must use only the originally approved exact bottle");
const offerId = "qa-perfumetrader-social-entry";
const offer = {
  offer_id: offerId, product_id: productId, merchant_id: "perfumetrader",
  merchant_name: "Perfumetrader", price: 90, currency: "EUR", shipping_cost: 5,
  shipping_label: "5,00 € Versand (QA)", total_price: 95, in_stock: true,
  variant_label: "100 ml · Eau de Toilette", affiliate_link: true,
  clickout_path: `/api/clickout/${offerId}`, last_updated_at: "2026-10-12T00:00:00Z",
};

export async function verifySocialProductEntry(browser, baseUrl, outputDir) {
  assert.ok(["localhost", "127.0.0.1"].includes(new URL(baseUrl).hostname), "QA requires a local storefront");
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
        // A positive attribution test must make the same explicit consent
        // choice as a real visitor; qa=1 never grants analytics permission.
        await page.getByRole("button", { name: "Analyse erlauben", exact: true }).click();
        await page.locator('[data-measurement-choice="granted"]').waitFor();
        const merchant = page.getByRole("link", { name: "Bei Perfumetrader ansehen", exact: true });
        await merchant.waitFor();
        await page.evaluate(() => document.fonts.ready);
        const hero = page.locator(".dufynd-fragrance-hero");
        assert.equal(await hero.getAttribute("data-dufynd-photo-status"), "verified",
          "Released exact Rabanne photo must be marked verified");
        assert.equal(await hero.getAttribute("data-dufynd-photo-hold"), null,
          "No stale photo-hold claim after rights-reviewed release");
        const photoCredit = hero.locator('[data-original-photo-source="top-parfuemerie"] a');
        assert.equal(await photoCredit.count(), 1,
          "Public hero must retain source attribution despite isolated image request failure");
        assert.equal(new URL(await photoCredit.getAttribute("href")).hostname, "www.topparfuemerie.de");
        assert.equal(await hero.locator('[data-dufynd-source-honest-notes="rabanne-edt-100"]').count(), 0);
        assert.match(await hero.innerText(), /1 Million/);
        assert.match(await hero.innerText(), /100 ml/);
        assert.doesNotMatch(await page.locator("body").innerText(), /Preisreferenz|67,95/);
        assert.ok((await page.locator("#dufynd-hero-offer-cta").boundingBox()).height >= 44);
        assert.ok((await merchant.boundingBox()).height >= 44);
        const metrics = await page.evaluate(() => {
          const stage = document.querySelector(".dufynd-fragrance-stage-shell")?.getBoundingClientRect();
          const cta = document.querySelector("#dufynd-hero-offer-cta")?.getBoundingClientRect();
          const offers = document.querySelector("#angebote")?.getBoundingClientRect();
          return {
            stage_height: stage?.height ?? null,
            stage_width: stage?.width ?? null,
            cta_bottom: cta?.bottom ?? null,
            offers_top: offers?.top ?? null,
            overflow: document.documentElement.scrollWidth > innerWidth,
          };
        });
        assert.ok(metrics.stage_height > 100 && metrics.stage_width > 0 &&
          metrics.stage_width <= width + 2, JSON.stringify(metrics));
        assert.ok(metrics.cta_bottom > 0 && metrics.offers_top > metrics.cta_bottom,
          'A released image must not cover, overlap or remove the buyer journey');
        assert.equal(metrics.overflow, false, 'Licensed photo must fit the viewport');
        measurements.push({ source, width, ...metrics });
        const section = page.locator("[data-merchant-offers]");
        assert.match(await section.innerText(), /Gesamtpreis inkl. Versand/);
        assert.doesNotMatch(await section.innerText(), /Bester Gesamtpreis|Beste verfügbare Option/i);
        assert.match(await section.innerText(), /Werbung · Partnerlink/);
        const clickout = new URL(await merchant.getAttribute("href"), baseUrl);
        assert.equal(clickout.pathname, `/api/clickout/${offerId}`);
        for (const [key, value] of [["src", source], ["cmp", campaign], ["content", content]]) {
          assert.equal(clickout.searchParams.get(key), value);
        }
        assert.match(clickout.searchParams.get("sid") || "", /^[0-9a-f-]{36}$/i,
          "optional analytics has its own UUID, never the advisor transport session");
        assert.notEqual(clickout.searchParams.get("sid"), session);
        assert.equal(clickout.searchParams.get("measurement"), "granted-v1");
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
          assert.match(await section.innerText(), /Artikelpreis · Versand beim Händler prüfen/);
          offers = [{ ...offer }, { ...offer, offer_id: "qa-second", merchant_name: "QA second", total_price: 100, clickout_path: "/api/clickout/qa-second" }];
          await page.reload();
          await merchant.waitFor();
          assert.match(await section.innerText(), /Bester Gesamtpreis · hier gelistet/i);
        }
      } finally {
        await context.close();
      }
    }
  }
  return measurements;
}

// One read-only GET of the existing public API, never the merchant/redirect.
// Network availability is evidence, not a dependency of the deterministic tests.
export async function verifyFirstMoneyLandingStates(browser, baseUrl, outputDir) {
  assert.ok(["localhost", "127.0.0.1"].includes(new URL(baseUrl).hostname), "QA requires a local storefront");
  const sourceUrl = `https://scentai-api-kxhe.onrender.com/api/merchant-offers/${productId}`;
  const evidence = { source_url: sourceUrl, read_at: null, status: "UNKNOWN", http_status: null, sha256: null };
  let attempted = false;
  let liveBody = null;
  const cases = [];
  for (const width of [390, 1440]) {
    const context = await browser.newContext({ viewport: { width, height: 900 }, serviceWorkers: "block", reducedMotion: "reduce" });
    try {
      const page = await context.newPage();
      let mode = "live";
      const forbidden = [];
      const events = [];
      await context.route("**/*", async (route) => {
        const url = new URL(route.request().url());
        if (url.pathname === "/api/session") return route.fulfill({ json: { session_id: "qa-landing-final-session" } });
        if (url.pathname === "/api/analytics/events") {
          events.push(route.request().postDataJSON());
          return route.fulfill({ json: { ok: true } });
        }
        if (url.pathname === `/api/merchant-offers/${productId}`) {
          if (mode === "error") return route.fulfill({ status: 503, body: "isolated unavailable fixture" });
          if (mode === "empty") return route.fulfill({ json: { product_id: productId, offers: [], best_offer_id: null, affiliate_disclosure: "QA fixture" } });
          if (mode === "recovery") return route.fulfill({ json: { product_id: productId, offers: [offer], best_offer_id: offerId, affiliate_disclosure: "QA fixture" } });
          if (!attempted) {
            attempted = true;
            evidence.read_at = new Date().toISOString();
            try {
              assert.equal(route.request().method(), "GET");
              const response = await route.fetch({ url: sourceUrl, headers: { accept: "application/json" }, maxRedirects: 0, maxRetries: 0, timeout: 7_000 });
              evidence.http_status = response.status();
              const text = await response.text();
              if (response.ok()) {
                const data = JSON.parse(text);
                assert.equal(data.product_id, productId);
                assert.ok(Array.isArray(data.offers));
                assert.ok(data.offers.every((o) => o.product_id === productId));
                liveBody = text;
                evidence.sha256 = createHash("sha256").update(text).digest("hex");
                evidence.status = data.offers.length ? "AVAILABLE" : "NO_ELIGIBLE_OFFER";
              } else evidence.status = "API_UNAVAILABLE";
            } catch { evidence.status = "API_UNAVAILABLE_OR_INVALID"; }
          }
          return liveBody
            ? route.fulfill({ contentType: "application/json", body: liveBody })
            : route.fulfill({ status: 503, body: "read-only public offer capture unavailable" });
        }
        if (url.origin !== new URL(baseUrl).origin || url.pathname.startsWith("/api/")) {
          forbidden.push(url.pathname);
          return route.abort();
        }
        return route.continue();
      });
      await page.goto(`${baseUrl}/duft/rabanne-1-million?qa=1&src=instagram&cmp=qa_landing_final&content=qa_state_review`);
      await page.getByRole("button", { name: "Analyse erlauben", exact: true }).click();
      await page.locator('[data-measurement-choice="granted"]').waitFor();
      await page.locator('[data-offer-state]:not([data-offer-state="loading"])').waitFor();
      await page.evaluate(() => document.fonts.ready);
      assert.doesNotMatch(await page.locator("body").innerText(), /Preisreferenz|67,95/);
      const live = liveBody ? JSON.parse(liveBody) : null;
      if (live?.offers.length) {
        const offerSection = page.locator("[data-merchant-offers]");
        await offerSection.locator('a[href*="/api/clickout/"]').first().waitFor();
        const perfumetrader = live.offers.find((o) => o.offer_id === "perfumetrader-rabanne-1-million-edt-100");
        evidence.perfumetrader_present = Boolean(perfumetrader);
        if (perfumetrader) {
          assert.equal(perfumetrader.affiliate_link, true);
          assert.match(perfumetrader.variant_label, /100 ml/);
          assert.match(perfumetrader.variant_label, /Eau de Toilette/);
          const text = await offerSection.innerText();
          for (const amount of [perfumetrader.price, perfumetrader.shipping_cost, perfumetrader.total_price]) {
            if (amount == null) continue;
            assert.ok(text.includes(amount.toLocaleString("de-DE", { minimumFractionDigits: 2, maximumFractionDigits: 2 })));
          }
          assert.match(text, /Werbung · Partnerlink/i);
          evidence.offer = perfumetrader;
        }
      }
      await page.screenshot({ path: path.join(outputDir, `landing-live-offer-${width}.png`), fullPage: true });
      await page.locator("[data-offer-state]").screenshot({ path: path.join(outputDir, `landing-live-offer-${width}-section.png`) });
      for (const state of ["error", "empty"]) {
        mode = state;
        await page.reload();
        const section = page.locator(`[data-offer-state="${state}"]`);
        await section.waitFor();
        assert.doesNotMatch(await page.locator("body").innerText(), /Preisreferenz|67,95|76,89|71,90|95,00/);
        assert.equal(await section.locator('a[href*="/api/clickout/"],a[target="_blank"]').count(), 0);
        assert.equal(await page.locator("[data-merchant-offers]").count(), 0);
        assert.match(await section.innerText(), state === "error" ? /Angebote gerade nicht erreichbar/ : /Zurzeit kein aktuelles Angebot/);
        assert.ok(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth));
        await page.evaluate(() => window.scrollTo(0, 0));
        await page.waitForTimeout(100);
        await page.screenshot({ path: path.join(outputDir, `landing-${state}-${width}.png`), fullPage: true });
        if (state === "error") {
          const retry = section.getByRole("button", { name: "Angebote erneut prüfen", exact: true });
          assert.ok((await retry.boundingBox()).height >= 44);
          mode = "recovery"; // Explicit synthetic recovery test; no further live GET.
          await retry.click();
          const recovered = page.getByRole("link", { name: "Bei Perfumetrader ansehen", exact: true });
          await recovered.waitFor();
          const href = new URL(await recovered.getAttribute("href"), baseUrl);
          for (const [key, value] of [["src", "instagram"], ["cmp", "qa_landing_final"], ["content", "qa_state_review"]]) assert.equal(href.searchParams.get(key), value);
          assert.equal(await page.locator('[data-offer-state="error"]').count(), 0);
        }
        cases.push({ width, state, status: "passed" });
      }
      for (const event of events) assert.equal(event.internal_qa, true);
      assert.deepEqual(forbidden.filter((p) => p.startsWith("/api/")), []);
    } finally { await context.close(); }
  }
  await writeFile(path.join(outputDir, "landing-live-offer-evidence.json"), JSON.stringify({ ...evidence, body: liveBody ? JSON.parse(liveBody) : null, second_width: "same captured API response", real_clickouts: 0, production_analytics: 0 }, null, 2));
  return { cases, live_evidence: evidence };
}
