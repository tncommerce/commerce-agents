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
  for (const width of [320, 390, 768, 1440]) {
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
      await page.goto(`${baseUrl}/duft?qa=1&q=Yves%20Saint%20Laurent`);
      await chooseMeasurement(page, "denied");
      const search = page.getByRole("searchbox", { name: "Duft, Marke oder Profil" });
      await search.fill("Yves Saint Laurent");
      if (width < 1024) {
        const toggle = page.locator('button[aria-controls="catalog-filter-panel"]');
        const panel = page.locator("#catalog-filter-panel");
        assert.equal(await toggle.isVisible(), true, "mobile and tablet visitors can open advanced filters");
        assert.equal(await panel.isVisible(), false, "advanced filters start closed below desktop");
        await toggle.click();
        assert.equal(await panel.isVisible(), true, "filter disclosure expands on demand");
      } else {
        assert.equal(await page.locator("#catalog-filter-panel").isVisible(), true, "desktop keeps advanced filters visible");
      }
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
      if (width < 1024) assert.equal(await page.locator("#catalog-filter-panel").isVisible(), false, "Enter focuses matching results and closes advanced filters");
      const cards = page.locator(".dufynd-catalog-card");
      assert.equal(await cards.count(), 2);
      await cards.nth(0).getByRole("button", { name: /für Vergleich auswählen/ }).click();
      assert.equal(await cards.nth(0).getByRole("button", { name: /Vergleich/ }).getAttribute("aria-pressed"), "true", "first comparison click survives results-heading blur");
      await cards.nth(1).getByRole("button", { name: /für Vergleich auswählen/ }).click();
      assert.equal(await cards.nth(1).getByRole("button", { name: /Vergleich/ }).getAttribute("aria-pressed"), "true", "second comparison click is retained");
      await cards.nth(1).evaluate(el => el.scrollIntoView({ block: "start" }));
      const tray = page.getByRole("complementary", { name: "Duftvergleich vorbereiten" });
      const rect = await tray.boundingBox();
      assert.ok(rect.y >= 0 && rect.y + rect.height <= 900, `comparison controls stay in viewport at ${width}`);
      assert.match(await tray.textContent(), /Eau de Parfum · 90\sml/);
      await page.screenshot({ path: path.join(outputDir, `mobile-discovery-selection-${width}.png`) });
      const productLink = cards.nth(1).locator("a.group");
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
      assert.equal(await page.locator(".dufynd-catalog-card").count(), 2, "failed images retain usable exact product cards");
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
      results.push({ width, cases: 13, attributionWithContext: width === 390, comparisonTray: rect, offerStates: ["empty", "error", "wrong-product", "synthetic-available"] });
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
