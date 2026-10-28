import { chooseMeasurement } from "./measurement-choice-qa.mjs";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";

// Entirely local, default-deny QA. Artificial quotes never enter public data.
const approvedPhotoById = new Map(JSON.parse(readFileSync(
  new URL("../lib/generated/original-photos.json", import.meta.url), "utf8",
)).map((photo) => [photo.product_id, photo]));

export async function verifySite13Funnel(browser, baseUrl) {
  const origin = new URL(baseUrl).origin;
  assert.ok(["localhost", "127.0.0.1"].includes(new URL(baseUrl).hostname));
  const productId = "SC-RABANNE-1-MILLION-EDT-100";
  const results = [];
  for (const width of [320, 390, 1440]) {
    for (const denied of [false, true]) {
      for (const source of ["tiktok", "youtube"]) {
        const context = await browser.newContext({ viewport: { width, height: 844 }, reducedMotion: "reduce", serviceWorkers: "block" });
        try {
          if (denied) await context.addInitScript(() => {
            Object.defineProperty(window, "sessionStorage", { get() { throw new DOMException("Denied", "SecurityError"); } });
          });
          const page = await context.newPage();
          const events = [], forbidden = [];
          let sessionRequests = 0, state = "available";
          const offer = { offer_id: "qa-site13-offer", product_id: productId, merchant_name: "Perfumetrader", merchant_id: "perfumetrader", price: 90, currency: "EUR", shipping_cost: 5, total_price: 95, in_stock: true, variant_label: "100 ml · Eau de Toilette", affiliate_link: true, clickout_path: "/api/clickout/qa-site13-offer", last_updated_at: "2026-10-14T00:00:00Z" };
          await context.route("**/*", async (route) => {
            const url = new URL(route.request().url());
            if (url.pathname === "/api/session") {
              // The initial internal-link effect runs before transport settles.
              await new Promise((resolve) => setTimeout(resolve, 180));
              return route.fulfill({ json: { session_id: `qa-site13-transport-${++sessionRequests}-12345` } });
            }
            if (url.pathname === "/api/analytics/events") {
              events.push(route.request().postDataJSON());
              return route.fulfill({ json: { ok: true } });
            }
            if (url.pathname === `/api/merchant-offers/${productId}`) {
              if (state === "error") return route.fulfill({ status: 503, json: {} });
              return route.fulfill({ json: { product_id: productId, best_offer_id: state === "empty" ? null : offer.offer_id, offers: state === "empty" ? [] : [offer], affiliate_disclosure: "Isolated QA fixture" } });
            }
            if (url.pathname.startsWith("/api/") || url.origin !== origin) {
              if (url.pathname.startsWith("/api/")) forbidden.push(url.pathname);
              return route.abort();
            }
            return route.continue();
          });
          const query = source === "tiktok" ? "src=tiktok&cmp=qa_site13&content=qa_profile" : "utm_source=youtube&utm_campaign=qa_site13&utm_content=qa_profile";
          assert.ok((await page.goto(`${baseUrl}/duft?qa=1&${query}`))?.ok());
          await chooseMeasurement(page, "granted");
          await page.waitForFunction(() => Boolean(document.querySelector("[data-social-product-entry]")?.href.includes("qa_site13")));
          await assertEventually(() => events.some((e) => e.event === "page_view"));
          const measurementSession = events.find((e) => e.event === "page_view")?.analytics_session_id;
          assert.match(measurementSession || "", /^[0-9a-f-]{36}$/i);
          assert.notEqual(measurementSession, "qa-site13-transport-1-12345");
          const entry = page.locator("[data-social-product-entry]");
          assert.match(await entry.innerText(), /1 Million|1Million/);
          assert.match(await entry.innerText(), /Eau de Toilette.*100 ml/);
          const bounds = await entry.boundingBox();
          assert.ok(bounds.y + bounds.height < 844, "direct product entry visible without scrolling");
          // Keyboard activation also refreshes the settled funnel identifier.
          await entry.focus();
          await page.keyboard.press("Enter");
          await page.waitForURL((u) => u.pathname === "/duft/rabanne-1-million", { waitUntil: "domcontentloaded" });
          const merchant = page.getByRole("link", { name: "Bei Perfumetrader ansehen", exact: true });
          await merchant.waitFor();
          await page.locator("#dufynd-hero-offer-cta").click();
          await assertEventually(() => events.some((e) => e.event === "offer_section_view"));
          const url = new URL(await merchant.getAttribute("href"));
          for (const [key, value] of [["src", source], ["cmp", "qa_site13"], ["content", "qa_profile"], ["qa", "1"], ["sid", measurementSession], ["measurement", "granted-v1"]]) assert.equal(url.searchParams.get(key), value);
          assert.equal(url.pathname, "/api/clickout/qa-site13-offer");
          assert.ok(sessionRequests >= 2, "document navigation must use a fresh API transport");
          for (const type of ["page_view", "fragrance_detail_view", "offer_section_view"]) {
            const row = events.find((e) => e.event === type);
            assert.ok(row, type);
            assert.equal(row.analytics_session_id, measurementSession, `${type}: split independent measurement identity at ${width}/${denied}/${source}`);
            assert.equal(row.acquisition_source, source);
            assert.equal(row.campaign_id, "qa_site13");
            assert.equal(row.content_id, "qa_profile");
            assert.equal(row.internal_qa, true);
          }
          assert.ok((await merchant.boundingBox()).height >= 44);
          assert.equal(await page.evaluate(() => document.documentElement.scrollWidth > innerWidth), false);
          const approved = approvedPhotoById.get(productId);
          assert.ok(approved && approved.url.startsWith('https://www.topparfuemerie.de/media/catalog/product/'),
            'First-money test must use the exact approved released image, not a fabricated bottle');
          const photoHero = page.locator('.dufynd-fragrance-hero');
          assert.equal(await photoHero.getAttribute('data-dufynd-photo-status'), 'verified');
          assert.equal(await photoHero.getAttribute('data-dufynd-photo-hold'), null);
          assert.equal(await photoHero.locator('[data-original-photo-source="top-parfuemerie"]').count(), 1,
            'Released merchant photo requires its visible source disclosure');
          // The QA browser may block the off-origin photo request. The neutral
          // network fallback must not be misclassified as missing usage rights.
          await page.getByText("Merken, teilen & vergleichen", { exact: true }).click();
          await page.getByRole("button", { name: /Merken/ }).first().waitFor();
          if (source === "tiktok" && !denied) {
            state = "empty"; await page.reload();
            await page.locator('[data-offer-state="empty"]').waitFor();
            assert.equal(await merchant.count(), 0);
            state = "error"; await page.reload();
            await page.locator('[data-offer-state="error"]').waitFor();
            assert.equal(await merchant.count(), 0);
            state = "available";
            await page.getByRole("button", { name: "Angebote erneut prüfen" }).click();
            await merchant.waitFor();
            assert.equal(new URL(await merchant.getAttribute("href")).searchParams.get("cmp"), "qa_site13");
            assert.equal(await page.locator('[data-offer-state="error"]').count(), 0);
          }
          assert.deepEqual(forbidden, [], "no clickout or unmocked API calls");
          results.push({ width, denied, source, status: "passed" });
        } finally { await context.close(); }
      }
    }
  }
  return results;
}

async function assertEventually(predicate) {
  for (let attempt = 0; attempt < 100; attempt++) {
    if (predicate()) return;
    await new Promise((resolve) => setTimeout(resolve, 50));
  }
  assert.ok(predicate(), "expected isolated analytics event");
}
