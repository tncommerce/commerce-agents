import assert from "node:assert/strict";
import path from "node:path";
import { mkdir, readFile, writeFile } from "node:fs/promises";
import { createHash } from "node:crypto";
import { chooseMeasurement } from "./measurement-choice-qa.mjs";
import { offerFixtureProductId } from "./merchant-offer-fixture-qa.mjs";

// Native browser interactions against the built site. All API replies here are
// synthetic; no merchant request, clickout or production analytics is sent.
export async function verifyMobileDiscovery(browser, baseUrl, outputDir) {
  const results = [];
  await mkdir(outputDir, { recursive: true });
  for (const width of [320, 390, 768, 1023, 1024, 1440]) {
    const context = await browser.newContext({ viewport: { width, height: 900 }, reducedMotion: "reduce" });
    const page = await context.newPage();
    const errors = [];
    const measurementRequests = [];
    let mode = "empty";
    page.on("pageerror", error => errors.push(String(error)));
    await context.route("**/api/**", async route => {
      const url = new URL(route.request().url());
      assert.ok(!url.pathname.includes("/clickout/"), "QA never performs merchant clickouts");
      if (/\/api\/(analytics|session)/.test(url.pathname)) measurementRequests.push(url.pathname);
      if (!url.pathname.startsWith("/api/merchant-offers/")) return route.fulfill({ json: url.pathname === "/api/session" ? { session_id: "synthetic-mobile-session" } : {} });
      if (mode === "error") return route.fulfill({ status: 503, body: "Synthetic QA failure" });
      const productId = offerFixtureProductId(route);
      return route.fulfill({ json: {
        product_id: mode === "wrong-product" ? "SC-SYNTHETIC-WRONG" : productId,
        offers: mode === "available" ? [{
          offer_id: "synthetic-mobile-qa", product_id: productId,
          merchant_id: "synthetic-qa", merchant_name: "Synthetisches QA-Angebot",
          price: 99, total_price: 99, currency: "EUR", in_stock: true,
          affiliate_link: false, clickout_path: "/api/clickout/synthetic-mobile-qa",
          last_updated_at: new Date().toISOString(),
        }] : [],
        best_offer_id: mode === "available" ? "synthetic-mobile-qa" : null,
        affiliate_disclosure: "Synthetische QA-Testdaten. Kein reales Kaufangebot.",
      } });
    });
    try {
      // A visible bottle alone is not usable discovery: the first exact product
      // identity and variant must also fit in the first viewport.
      const firstFoldHeight = width < 640 ? 844 : 1000;
      await page.setViewportSize({ width, height: firstFoldHeight });
      await page.goto(`${baseUrl}/duft?qa=1`);
      await chooseMeasurement(page, "denied");
      await page.evaluate(() => document.fonts.ready);
      const firstOriginal = page.locator('.dufynd-catalog-card[data-original-photo="true"]').first();
      const firstName = await firstOriginal.locator("h2").boundingBox();
      const firstVariant = await firstOriginal.locator(".dufynd-product-variant").boundingBox();
      assert.ok(firstName && firstName.y + firstName.height <= firstFoldHeight, `first exact fragrance name visible at ${width}`);
      assert.ok(firstVariant && firstVariant.y + firstVariant.height <= firstFoldHeight, `first exact variant visible at ${width}`);
      if (width >= 390) {
        const firstCta = firstOriginal.locator(".dufynd-catalog-card-cta");
        const ctaBounds = await firstCta.boundingBox();
        assert.ok(ctaBounds && ctaBounds.y + ctaBounds.height <= firstFoldHeight - 16, `complete first profile CTA has breathing room at ${width}`);
        assert.equal(await firstCta.evaluate(element => {
          const box = element.getBoundingClientRect();
          const target = document.elementFromPoint(box.x + box.width / 2, box.y + box.height / 2);
          return element.closest("a")?.contains(target) ?? false;
        }), true, `first profile CTA is not covered at ${width}`);
      }
      await page.setViewportSize({ width, height: 900 });
      await page.goto(`${baseUrl}/duft?qa=1&q=Yves%20Saint%20Laurent`);
      await chooseMeasurement(page, "denied");
      const search = page.getByRole("searchbox", { name: "Duft, Marke oder Profil" });
      await search.fill("Yves Saint Laurent");
      const toggle = page.locator('button[aria-controls="catalog-filter-panel"]');
      const panel = page.locator("#catalog-filter-panel");
      assert.equal(await toggle.isVisible(), true, "every width exposes the filter disclosure");
      assert.equal(await panel.isVisible(), false, "advanced filters start closed at every width");
      await toggle.click();
      assert.equal(await panel.isVisible(), true, "filter disclosure expands on demand");
      const filters = page.getByRole("region", { name: "Duftkatalog filtern" });
      await filters.evaluate(el => el.scrollIntoView({ block: "start" }));
      for (const target of await filters.locator("button").all()) {
        if (await target.isVisible()) assert.ok((await target.boundingBox()).height >= 44, `44px filter target: ${await target.textContent()} at ${width}`);
      }
      await page.screenshot({ path: path.join(outputDir, `mobile-discovery-filters-${width}.png`) });
      await search.focus();
      await search.press("Enter");
      await page.waitForFunction(() => document.activeElement?.id === "catalog-results");
      assert.equal(await page.locator("#catalog-results").evaluate(el => el === document.activeElement), true, "search key moves focus to results");
      assert.ok((await page.locator("#catalog-results").boundingBox()).height >= 24, "keyboard results focus has a visible heading");
      assert.equal(await page.locator("#catalog-filter-panel").isVisible(), false, "Enter focuses matching results and closes advanced filters");
      const cards = page.locator(".dufynd-catalog-card");
      // After the explicitly approved 20-profile wave, YSL Y EDP 100 ml is
      // a genuine third result. Preserve the Libre/Black Opium comparison
      // without accidentally selecting a different product by list order.
      assert.equal(await cards.count(), 3, "two original YSL profiles and approved Y EDP 100 ml");
      const libreCard = cards.filter({
        has: page.getByRole("heading", { name: "Libre", exact: true }),
      });
      const blackOpiumCard = cards.filter({
        has: page.getByRole("heading", { name: "Black Opium", exact: true }),
      });
      const yCard = cards.filter({
        has: page.getByRole("heading", { name: "Y", exact: true }),
      });
      for (const target of [libreCard, blackOpiumCard, yCard]) {
        assert.equal(await target.count(), 1, "exactly one card per documented YSL variant");
      }
      assert.equal(
        new URL(await yCard.locator("a.group").getAttribute("href"), baseUrl).pathname,
        "/duft/ysl-y-edp-100",
        "third result links only to the approved 100 ml Y profile",
      );
      await libreCard.getByRole("button", { name: /für Vergleich auswählen/ }).click();
      assert.equal(await libreCard.getByRole("button", { name: /Vergleich/ }).getAttribute("aria-pressed"), "true", "Libre selection survives results-heading blur");
      await blackOpiumCard.getByRole("button", { name: /für Vergleich auswählen/ }).click();
      assert.equal(await blackOpiumCard.getByRole("button", { name: /Vergleich/ }).getAttribute("aria-pressed"), "true", "Black Opium selection is retained");
      await blackOpiumCard.evaluate(el => el.scrollIntoView({ block: "start" });
      const tray = page.getByRole("complementary", { name: "Duftvergleich vorbereiten" });
      const rect = await tray.boundingBox();
      assert.ok(rect.y >= 0 && rect.y + rect.height <= 900, `comparison controls stay in viewport at ${width}`);
      assert.match(await tray.textContent(), /Eau de Parfum · 90\sml/);
      await page.screenshot({ path: path.join(outputDir, `mobile-discovery-selection-${width}.png`) });
      const productLink = blackOpiumCard.locator("a.group");
      const detailUrl = new URL(await productLink.getAttribute("href"), baseUrl).href;
      const nested = new URLSearchParams(new URL(detailUrl).searchParams.get("catalog"));
      assert.equal(nested.get("q"), "Yves Saint Laurent");
      assert.equal(nested.get("compare").split(",").length, 2);
      for (const forbidden of ["sid", "qa", "src", "cmp", "content", "catalog"]) assert.equal(nested.has(forbidden), false);
      await productLink.click();
      await page.locator('[data-offer-state="empty"]').waitFor();
      const recovery = page.getByRole("navigation", { name: "Weitere Wege zum passenden Duft" });
      const back = recovery.getByRole("link", { name: "← Zurück zu deiner Auswahl", exact: true });
      await back.waitFor();
      const backUrl = new URL(await back.getAttribute("href"), baseUrl);
      assert.equal(backUrl.searchParams.get("q"), "Yves Saint Laurent");
      assert.equal(await page.locator('a[href*="/api/clickout/"]').count(), 0);
      await recovery.evaluate(el => el.scrollIntoView({ block: "center" }));
      await page.screenshot({ path: path.join(outputDir, `mobile-discovery-empty-${width}.png`) });
      // Native back must preserve the search AND selected variants.
      await page.goBack();
      await search.waitFor();
      await page.waitForFunction(() => document.querySelector('input[type="search"]')?.value === "Yves Saint Laurent");
      assert.equal(await search.inputValue(), "Yves Saint Laurent");
      await tray.getByRole("link", { name: "Jetzt vergleichen →", exact: true }).click();
      await page.locator(".dufynd-comparison-live-stage").waitFor();
      for (const name of ["Duft 1", "Duft 2"]) {
        const select = page.getByRole("combobox", { name, exact: true });
        assert.match(await select.locator("option:checked").textContent(), /Eau de Parfum · 90 ml/);
      }
      await page.locator(".dufynd-comparison-picker").evaluate(el => el.scrollIntoView({ block: "start" }));
      await page.screenshot({ path: path.join(outputDir, `mobile-discovery-comparison-${width}.png`) });
      const compareProduct = page.locator('[data-dufynd-comparison-side="left"]');
      assert.equal(new URL(await compareProduct.getAttribute("href"), baseUrl).searchParams.get("catalog"), nested.toString());
      await page.locator("header").getByRole("link", { name: "← Zurück zu deiner Auswahl", exact: true }).click();
      await search.waitFor();
      await page.waitForFunction(() => document.querySelector('input[type="search"]')?.value === "Yves Saint Laurent");
      assert.equal(await search.inputValue(), "Yves Saint Laurent");
      await tray.getByRole("button", { name: /Libre.*aus Vergleich entfernen/ }).focus();
      await page.keyboard.press("Enter");
      assert.equal(await tray.getByRole("link", { name: "Jetzt vergleichen →" }).count(), 0);
      await page.waitForFunction(() => new URLSearchParams(location.search).get("compare") === "SC-YSL-BLACK-OPIUM-EDP-90");
      await page.reload();
      await tray.getByText("1 von 2 Düften ausgewählt").waitFor();
      for (const nextMode of ["error", "wrong-product", "available"]) {
        mode = nextMode;
        await page.goto(detailUrl);
        await page.locator(`[data-offer-state="${mode === "available" ? "available" : "error"}"]`).waitFor();
        assert.equal(await page.locator('a[href*="/api/clickout/"]').count(), mode === "available" ? 1 : 0);
        if (mode !== "available") await page.getByRole("navigation", { name: "Weitere Wege zum passenden Duft" }).getByRole("link", { name: "← Zurück zu deiner Auswahl", exact: true }).waitFor();
      }
      mode = "empty";
      await page.goto(`${baseUrl}/duft?q=Hedonistic`);
      await page.getByRole("heading", { name: "Jump Up and Kiss Me Hedonistic", exact: true }).waitFor();
      assert.equal(await page.locator('[data-dufynd-visual-state="missing"]').count(), 1, "unapproved imagery stays absent");
      await page.locator(".dufynd-catalog-card").getByRole("button", { name: /für Vergleich auswählen/ }).click();
      assert.match(await tray.textContent(), /Jump Up and Kiss Me Hedonistic/);
      assert.ok(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth), "long identity does not overflow");
      await page.locator(".dufynd-catalog-card").evaluate(el => el.scrollIntoView({ block: "start" }));
      await page.screenshot({ path: path.join(outputDir, `mobile-discovery-long-name-${width}.png`) });
      await page.route("**/media/catalog/product/**", route => route.abort());
      await page.goto(`${baseUrl}/duft?q=Yves%20Saint%20Laurent`);
      await page.locator('[data-dufynd-visual-state="unavailable"]').first().waitFor();
      assert.equal(await page.locator(".dufynd-catalog-card").count(), 3, "failed images retain both original variants and the approved new Y profile");
      assert.ok(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth));
      assert.deepEqual(measurementRequests, [], "denied measurement creates no analytics/session requests");
      if (width === 390) {
        const contextual = new URL(`/vergleich?left=SC-YSL-LIBRE-EDP-90&right=SC-YSL-BLACK-OPIUM-EDP-90&src=instagram&cmp=synthetic_mobile&content=qa`, baseUrl);
        contextual.searchParams.set("catalog", `${nested}&sid=must-not-nest&cmp=must-not-nest`);
        // Consent is granted before a new attributed entry. A previous denial
        // must never be retroactively converted into acquisition consent.
        await chooseMeasurement(page, "granted");
        await page.goto(contextual.href);
        const returnLink = page.locator("header").getByRole("link", { name: "← Zurück zu deiner Auswahl", exact: true });
        await page.waitForFunction(() => document.querySelector('header a[href*="/duft?"]')?.getAttribute("href")?.includes("cmp=synthetic_mobile"));
        const attributed = new URL(await returnLink.getAttribute("href"), baseUrl);
        assert.equal(attributed.searchParams.get("cmp"), "synthetic_mobile");
        assert.equal(attributed.searchParams.get("q"), "Yves Saint Laurent");
        const detail = page.locator('[data-dufynd-comparison-side="left"]');
        const target = new URL(await detail.getAttribute("href"), baseUrl);
        assert.equal(target.searchParams.get("cmp"), "synthetic_mobile");
        assert.equal(new URLSearchParams(target.searchParams.get("catalog")).has("sid"), false);
        assert.equal(new URLSearchParams(target.searchParams.get("catalog")).has("cmp"), false);
        await detail.click();
        await page.locator('[data-offer-state="empty"]').waitFor();
        const recoveryLink = page.getByRole("navigation", { name: "Weitere Wege zum passenden Duft" }).getByRole("link", { name: "← Zurück zu deiner Auswahl", exact: true });
        await page.waitForFunction(() => document.querySelector('nav[aria-label="Weitere Wege zum passenden Duft"] a')?.getAttribute("href")?.includes("cmp=synthetic_mobile"));
        assert.equal(new URL(await recoveryLink.getAttribute("href"), baseUrl).searchParams.get("cmp"), "synthetic_mobile");
        await chooseMeasurement(page, "denied");
        await page.waitForFunction(() => !document.querySelector('nav[aria-label="Weitere Wege zum passenden Duft"] a')?.getAttribute("href")?.includes("cmp="));
        assert.equal(new URL(await recoveryLink.getAttribute("href"), baseUrl).searchParams.get("q"), "Yves Saint Laurent");
      }
      assert.deepEqual(errors, []);
      results.push({ width, cases: 14, firstName, firstVariant, attributionWithContext: width === 390, comparisonTray: rect, offerStates: ["empty", "error", "wrong-product", "synthetic-available"] });
    } finally { await context.close(); }
  }
  const event = process.env.GITHUB_EVENT_PATH
    ? JSON.parse(await readFile(process.env.GITHUB_EVENT_PATH, "utf8")) : null;
  const sources = [];
  for (const file of ["../components/FragranceCatalogBrowser.tsx", "../components/CatalogJourney.module.css", "../components/CatalogReturnLink.tsx", "../components/FragranceComparisonPicker.tsx", "../components/FragranceDetailPage.tsx", "../components/FragranceOffers.tsx", "../lib/catalogJourney.ts", "mobile-discovery-qa.mjs"]) {
    const bytes = await readFile(new URL(file, import.meta.url));
    sources.push({ file, sha256: createHash("sha256").update(bytes).digest("hex") });
  }
  const screenshots = [];
  for (const { width } of results) {
    for (const view of ["filters", "selection", "empty", "comparison", "long-name"]) {
      const file = `mobile-discovery-${view}-${width}.png`;
      screenshots.push({ file, width, sha256: createHash("sha256").update(await readFile(path.join(outputDir, file))).digest("hex") });
    }
  }
  await writeFile(path.join(outputDir, "mobile-discovery-evidence.json"), JSON.stringify({
    feature_sha: event?.pull_request?.head?.sha || process.env.QA_SOURCE_SHA || process.env.GITHUB_SHA || null,
    checkout_sha: process.env.GITHUB_SHA || process.env.QA_SOURCE_SHA || null,
    run_id: process.env.GITHUB_RUN_ID || null,
    data: "Existing public catalog; synthetic QA offers only; no merchant clickouts",
    sources, screenshots, results,
  }, null, 2));
  return results;
}
