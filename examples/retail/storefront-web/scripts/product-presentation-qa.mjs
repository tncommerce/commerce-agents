import assert from "node:assert/strict";
import { mkdir, writeFile, readFile } from "node:fs/promises";
import { createHash } from "node:crypto";
import { chooseMeasurement } from "./measurement-choice-qa.mjs";
import { offerFixtureProductId } from "./merchant-offer-fixture-qa.mjs";

const profiles = [
  ["yves-saint-laurent-libre", "SC-YSL-LIBRE-EDP-90", "Libre", 90],
  ["yves-saint-laurent-black-opium", "SC-YSL-BLACK-OPIUM-EDP-90", "Black Opium", 90],
  ["lancome-la-vie-est-belle", "SC-LANCOME-LA-VIE-EST-BELLE-EDP-100", "La Vie est Belle", 100],
  ["parfums-de-marly-delina", "SC-PDM-DELINA-EDP-75", "Delina", 75],
  ["clive-christian-jump-up-and-kiss-me-hedonistic", "SC-CLIVE-CHRISTIAN-HEDONISTIC-50", "Jump Up and Kiss Me Hedonistic", 50],
];

async function imageGeometry(stage) {
  // Registered source dimensions select the unchanged-original renderer;
  // originals without dimensions still use the legacy product-image renderer.
  const img = stage.locator("[data-dufynd-original-photo] img, img.dufynd-product-image");
  await img.scrollIntoViewIfNeeded();
  await img.evaluate(image => image.decode());
  return img.evaluate(image => {
    const frame = image.closest("[data-dufynd-original-photo], .dufynd-product-stage").getBoundingClientRect();
    const box = image.getBoundingClientRect();
    const css = getComputedStyle(image);
    return { src: image.currentSrc, naturalWidth: image.naturalWidth, naturalHeight: image.naturalHeight,
      complete: image.complete, fit: css.objectFit, transform: css.transform,
      contained: box.x >= frame.x - 1 && box.y >= frame.y - 1 && box.right <= frame.right + 1 && box.bottom <= frame.bottom + 1 };
  });
}

/** Native interactions on built pages; optional measurement and all clickouts blocked. */
export async function verifyProductPresentation(browser, baseUrl, outputDir) {
  const out = `${outputDir}/product-presentation`;
  await mkdir(out, { recursive: true });
  const results = [];
  for (const width of [320, 390, 768, 1440]) {
    const context = await browser.newContext({ viewport: { width, height: 900 }, hasTouch: width < 768, reducedMotion: "reduce" });
    const page = await context.newPage();
    const errors = [], measurements = [], clickouts = [];
    let offerMode = "empty";
    await context.route("**/api/**", route => {
      const url = new URL(route.request().url());
      if (url.pathname.includes("/clickout/")) { clickouts.push(url.pathname); return route.abort(); }
      if (/\/api\/(analytics|session)/.test(url.pathname)) measurements.push(url.pathname);
      if (!url.pathname.startsWith("/api/merchant-offers/")) return route.fulfill({ json: {} });
      if (offerMode === "error") return route.fulfill({ status: 503, body: "Synthetic QA failure" });
      const productId = offerFixtureProductId(route);
      return route.fulfill({ json: { product_id: offerMode === "wrong" ? "SC-SYNTHETIC-WRONG" : productId,
        offers: offerMode === "available" ? [{ offer_id: "synthetic-presentation", product_id: productId,
          merchant_id: "synthetic-qa", merchant_name: "Synthetisches QA-Angebot", currency: "EUR",
          price: 99, total_price: 99, in_stock: true, affiliate_link: false,
          clickout_path: "/api/clickout/synthetic-presentation", last_updated_at: new Date().toISOString() }] : [],
        best_offer_id: offerMode === "available" ? "synthetic-presentation" : null,
        affiliate_disclosure: "Synthetische QA-Testdaten. Kein reales Kaufangebot." } });
    });
    page.on("pageerror", error => errors.push(String(error)));
    const images = [];
    try {
      for (const [slug, id, name, volume] of profiles) {
        await page.goto(`${baseUrl}/duft/${slug}`);
        await chooseMeasurement(page, "denied");
        const hero = page.locator("[data-dufynd-product-presentation]");
        await hero.waitFor();
        assert.equal(await hero.getAttribute("data-product-id"), id);
        assert.equal(await hero.locator("h1").textContent(), name);
        assert.match(await hero.locator(".dufynd-product-variant").textContent(), new RegExp(`${volume} ml`));
        assert.equal(await page.locator("#duftnoten").count(), 1, "One composition, not duplicated");
        assert.ok(await page.locator("#duftnoten").evaluate(el => Boolean(el.compareDocumentPosition(document.querySelector("#angebote")) & Node.DOCUMENT_POSITION_FOLLOWING)), "Composition precedes offers");
        if (id.includes("HEDONISTIC")) {
          assert.equal(await hero.locator("img").count(), 0);
          assert.equal(await hero.locator('[data-dufynd-visual-state="missing"]').count(), 1);
        } else {
          const geometry = await imageGeometry(hero);
          assert.ok(geometry.complete && geometry.naturalWidth > 0 && geometry.naturalHeight > 0, `Loaded original: ${id}`);
          assert.equal(geometry.fit, "contain");
          assert.equal(geometry.transform, "none");
          assert.ok(geometry.contained, `Whole source stays in frame: ${id} at ${width}`);
          images.push({ productId: id, ...geometry });
        }
        assert.ok(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth), `${name}: no horizontal overflow`);
        for (const target of await hero.locator("button,a").all()) {
          if (await target.isVisible() && !(await target.getAttribute("href"))?.startsWith("http")) {
            assert.ok((await target.boundingBox()).height >= 44, `44px action: ${await target.textContent()}`);
          }
        }
        await hero.screenshot({ path: `${out}/${slug}-${width}.png` });
      }
      await page.goto(`${baseUrl}/vergleich?left=SC-YSL-LIBRE-EDP-90&right=SC-YSL-BLACK-OPIUM-EDP-90`);
      const evidence = page.locator("[data-dufynd-comparison-evidence]");
      await evidence.waitFor();
      assert.deepEqual(await evidence.getByRole("list", { name: "Dokumentierte gemeinsame Duftakkorde", exact: true }).locator("li").allTextContents(), ["Blumig", "Süß"]);
      assert.deepEqual(await evidence.getByRole("list", { name: "Dokumentierte gemeinsame Duftnoten", exact: true }).locator("li").allTextContents(), ["Vanille"]);
      assert.match(await evidence.getByRole("list", { name: "Zusätzlich für Libre dokumentierte Noten" }).textContent(), /Französischer Lavendel/);
      assert.match(await evidence.getByRole("list", { name: "Zusätzlich für Black Opium dokumentierte Noten" }).textContent(), /Kaffee/);
      assert.ok(await evidence.evaluate(el => Boolean(el.compareDocumentPosition(document.querySelector('[role="table"]')) & Node.DOCUMENT_POSITION_FOLLOWING)));
      const sides = page.locator("[data-dufynd-comparison-side]");
      const boxes = await sides.evaluateAll(xs => xs.map(x => { const r = x.getBoundingClientRect(); return { x:r.x,y:r.y,right:r.right }; }));
      assert.ok(Math.abs(boxes[0].y - boxes[1].y) < 2 && boxes[0].right < boxes[1].x, "Two exact variants remain side by side");
      for (const side of await sides.all()) await imageGeometry(side);
      await page.locator(".dufynd-comparison-live-stage").screenshot({ path: `${out}/comparison-${width}.png` });
      await evidence.screenshot({ path: `${out}/evidence-${width}.png` });
      const summary = evidence.locator("summary");
      await summary.focus();
      assert.notEqual(await summary.evaluate(el => getComputedStyle(el).outlineStyle), "none", "Visible keyboard focus");
      await page.keyboard.press("Enter");
      assert.equal(await evidence.locator("details").getAttribute("open"), "");
      assert.match(await evidence.locator("details").innerText(), /nicht, dass eine Note bei der Alternative fehlt/);
      await page.keyboard.press("Enter");
      if (width < 768) {
        await summary.tap();
        assert.equal(await evidence.locator("details").getAttribute("open"), "", "Native touch opens method disclosure");
        await summary.tap();
        assert.equal(await evidence.locator("details").getAttribute("open"), null);
      }
      // Exact data can be insufficient; do not manufacture an overlap or a percentage.
      await page.getByRole("combobox", { name: "Duft 2", exact: true }).selectOption("SC-CLIVE-CHRISTIAN-HEDONISTIC-50");
      assert.equal(await page.locator('[data-dufynd-comparison-side="right"] img').count(), 0);
      assert.ok(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth));
      for (const mode of ["empty", "error", "wrong", "available"]) {
        offerMode = mode;
        await page.goto(`${baseUrl}/duft/lancome-la-vie-est-belle`);
        const offers = page.locator("[data-offer-state]").first();
        await page.waitForFunction(() => { const state=document.querySelector('[data-offer-state]')?.getAttribute('data-offer-state');return state && state !== 'loading'; });
        if (mode === "available") {
          await page.getByText("Synthetisches QA-Angebot", { exact:true }).first().waitFor();
          assert.ok(await page.locator('a[href*="/api/clickout/"]').count() > 0);
        } else assert.equal(await page.locator('a[href*="/api/clickout/"]').count(), 0, `${mode}: no claimed purchase availability`);
        await offers.screenshot({ path: `${out}/offer-${mode}-${width}.png` });
      }
      // Distinguish an image that is still loading from a failed one.
      let releasePhoto;
      const pending = new Promise(resolve => { releasePhoto = resolve; });
      await context.route("**/3605533286555.webp", async route => { await pending; await route.abort(); });
      await page.goto(`${baseUrl}/duft/lancome-la-vie-est-belle`, { waitUntil:"domcontentloaded" });
      await page.locator('[data-dufynd-photo-state="loading"]').waitFor();
      await page.locator(".dufynd-fragrance-hero").screenshot({ path:`${out}/image-loading-${width}.png` });
      releasePhoto();
      await page.locator('[data-dufynd-visual-state="unavailable"]').waitFor();
      await page.locator(".dufynd-fragrance-hero").screenshot({ path:`${out}/image-error-${width}.png` });
      assert.deepEqual(errors, []);
      assert.deepEqual(measurements, [], "Denied consent sends no session or analytics events");
      assert.deepEqual(clickouts, [], "No merchant clickout even for synthetic positive offers");
      results.push({ width, profiles: profiles.length, images, status: "passed", nativeTouch:width < 768, measurementRequests:0, clickouts:0 });
    } finally { await context.close(); }
  }
  const sourcePaths = ["scripts/product-presentation-qa.mjs", "scripts/test-comparison-trust.mjs", "app/product-presentation.css", "components/FragranceVisual.tsx", "components/FragranceVariant.tsx", "components/FragranceCatalogBrowser.tsx", "components/FragranceDetailPage.tsx", "components/FragranceComparisonPicker.tsx", "components/FragranceComparisonEvidence.tsx", "lib/generated/public-fragrances.json"];
  const sources = Object.fromEntries(await Promise.all(sourcePaths.map(async file => [file, createHash("sha256").update(await readFile(new URL(`../${file}`, import.meta.url))).digest("hex")])));
  await writeFile(`${out}/report.json`, JSON.stringify({ commit:process.env.GITHUB_SHA || null, sources, results }, null, 2));
  return results;
}
