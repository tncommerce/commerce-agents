import assert from "node:assert/strict";
import { mkdir, readFile, writeFile } from "node:fs/promises";
import path from "node:path";
import { pathToFileURL } from "node:url";
import { createHash } from "node:crypto";
import { chooseMeasurement } from "./measurement-choice-qa.mjs";

const photos = JSON.parse(await readFile(new URL("../lib/generated/original-photos.json", import.meta.url), "utf8"));
const unrestrictedPhoto = photos.find(photo => photo.product_id === "SC-LANCOME-LA-VIE-EST-BELLE-EDP-100");
const merchantPhotos = photos.filter(photo => photo.rights_basis_id === "awin_top_parfuemerie_feed_materials_20260928");
const imageFixtures = new Map();
if (process.env.QA_IMAGE_MANIFEST) {
  for (const asset of JSON.parse(await readFile(process.env.QA_IMAGE_MANIFEST, "utf8"))) {
    assert.ok(photos.some(photo => photo.url === asset.url), "image fixtures may only mirror registered source photographs");
    const bytes = await readFile(asset.path);
    assert.equal(createHash("sha256").update(bytes).digest("hex"), asset.sha256, "cached photograph must match its recorded source bytes");
    imageFixtures.set(asset.url, { body: bytes, contentType: asset.content_type });
  }
}

// Merchant permission is contextual, not a blanket license for competing offers.
// This check reads link destinations only; it never follows a merchant link.
export async function verifyHomepageImageScope(page, baseUrl) {
  const internal = page.locator("a[data-dufynd-original-card]");
  assert.equal(await internal.count(), 1, "only the independently licensed photograph enters internal product discovery");
  assert.equal(new URL(await internal.first().getAttribute("href"), baseUrl).pathname,
    "/duft/lancome-la-vie-est-belle", "internal photograph must open its exact product");
  assert.deepEqual(await internal.locator("img").evaluateAll(images => images.map(image => image.getAttribute("src"))),
    [unrestrictedPhoto.url], "internal discovery must use the registered CC-BY-SA original");

  const slots = page.locator("[data-dufynd-partner-photo]");
  assert.equal(await slots.count(), 3, "three TOP originals must remain in their merchant context");
  const shown = [];
  for (const slot of await slots.all()) {
    const detail = await slot.evaluate(element => {
      const anchor = element.closest("a") || element.querySelector("a");
      return {
        href: anchor?.getAttribute("href"),
        rel: anchor?.getAttribute("rel") || "",
        images: [...element.querySelectorAll("img")].map(image => image.getAttribute("src")),
      };
    });
    assert.ok(detail.href, "each merchant photograph needs an explicit merchant destination");
    const destination = new URL(detail.href, baseUrl);
    assert.equal(destination.protocol, "https:");
    assert.ok(["topparfuemerie.de", "www.topparfuemerie.de"].includes(destination.hostname),
      "TOP photographs must not route to a competing merchant or internal offer page");
    assert.ok(!/clickout|awinaffid|awinmid|clickref|utm_|\/cread\.php/i.test(destination.href),
      "partner showcase must not invent an unverified tracking route");
    const rel = new Set(detail.rel.split(/\s+/));
    assert.ok(rel.has("sponsored") && rel.has("noreferrer"), "partner destination is disclosed and suppresses the referrer");
    assert.equal(detail.images.length, 1, "each partner entry has one original photograph");
    assert.ok(merchantPhotos.some(photo => photo.url === detail.images[0]), "merchant photograph is registered to TOP permission");
    shown.push(detail.images[0]);
  }
  assert.equal(new Set(shown).size, 3, "partner showcase must not duplicate one photograph across products");
}

function requireLocalBase(baseUrl) {
  const url = new URL(baseUrl);
  assert.ok(["127.0.0.1", "localhost", "[::1]"].includes(url.hostname),
    "visual reset QA is restricted to a local development or static-export server");
}

async function isolateNetwork(context, baseUrl, journal, failImages = false) {
  const localOrigin = new URL(baseUrl).origin;
  await context.route("**/*", async route => {
    const request = route.request();
    const url = new URL(request.url());
    if (/\/clickout(?:\/|$)|\/cread\.php|click-\d+-\d+/i.test(url.href)) {
      journal.clickouts.push(url.pathname);
      return route.abort("blockedbyclient");
    }
    if (url.pathname.startsWith("/api/")) {
      journal.fixtureRequests.push({ method: request.method(), path: url.pathname });
      if (url.pathname === "/api/session") return route.fulfill({ json: { session_id: "visual-reset-local-fixture", name: "Local QA" } });
      if (url.pathname === "/api/products") return route.fulfill({ json: { products: [] } });
      if (url.pathname === "/api/merchant-partners") return route.fulfill({ json: { partners: [] } });
      if (url.pathname === "/api/analytics/events") {
        journal.analytics.push(request.postDataJSON());
        return route.fulfill({ json: { ok: true } });
      }
      return route.fulfill({ status: 503, json: { detail: "Isolated unavailable fixture" } });
    }
    if (failImages && request.resourceType() === "image" && !url.pathname.endsWith("/icon.svg")) {
      return route.abort("failed");
    }
    if (imageFixtures.has(url.href)) return route.fulfill(imageFixtures.get(url.href));
    if (request.method() !== "GET" && request.method() !== "HEAD") {
      journal.blockedMutations.push({ method: request.method(), path: url.pathname });
      return route.abort("blockedbyclient");
    }
    if (url.origin !== localOrigin && !["image", "font"].includes(request.resourceType())) {
      journal.blockedExternal.push({ host: url.hostname, path: url.pathname });
      return route.abort("blockedbyclient");
    }
    return route.continue();
  });
}

function journal() {
  return { fixtureRequests: [], analytics: [], clickouts: [], blockedMutations: [], blockedExternal: [] };
}

async function overflow(page) {
  return page.evaluate(() => Math.max(document.documentElement.scrollWidth - innerWidth,
    ...[...document.querySelectorAll(".panel-scroll")].map(element => element.scrollWidth - element.clientWidth)));
}

async function settleImages(page) {
  return page.locator("[data-dufynd-visual-reset] img").evaluateAll(async images => {
    await Promise.all(images.map(async image => {
      image.loading = "eager";
      await Promise.race([image.decode().catch(() => {}), new Promise(resolve => setTimeout(resolve, 8000))]);
    }));
    return images.filter(image => !image.complete || !image.naturalWidth).map(image => image.src);
  });
}

async function captureJourney(page, out, width) {
  const scroller = page.locator(".panel-scroll").filter({ has: page.locator("[data-dufynd-visual-reset]") });
  if (await scroller.count() === 1) {
    const extent = await scroller.evaluate(element => ({ height: element.scrollHeight, viewport: element.clientHeight }));
    const end = Math.max(0, extent.height - extent.viewport);
    let frame = 0;
    for (let y = 0; ; y = Math.min(end, y + Math.max(250, Math.floor(extent.viewport * .8)))) {
      await scroller.evaluate((element, top) => { element.scrollTop = top; }, y);
      await page.screenshot({ path: path.join(out, `visual-reset-${width}-journey-${String(frame++).padStart(2, "0")}.png`) });
      if (y === end) break;
    }
    await scroller.evaluate(element => { element.scrollTop = 0; });
    return { ...extent, frames: frame };
  }
  await page.screenshot({ path: path.join(out, `visual-reset-${width}-full.png`), fullPage: true });
  return { height: await page.evaluate(() => document.documentElement.scrollHeight), frames: 1 };
}

export async function verifyVisualReset(browser, baseUrl, outputDir) {
  requireLocalBase(baseUrl);
  await mkdir(outputDir, { recursive: true });
  const report = { generated_at: new Date().toISOString(), base_url: baseUrl, environment: "local fixture; not a field-performance measurement", cases: [] };
  try {
    for (const width of [320, 390, 768, 1024, 1440]) {
      const context = await browser.newContext({ viewport: { width, height: width < 640 ? 844 : 1000 }, reducedMotion: "reduce", hasTouch: width < 1024 });
      const requests = journal();
      await isolateNetwork(context, baseUrl, requests);
      await context.addInitScript(() => {
        window.__visualResetPerf = { cls: 0, lcp: 0 };
        new PerformanceObserver(list => { for (const entry of list.getEntries()) if (!entry.hadRecentInput) window.__visualResetPerf.cls += entry.value; }).observe({ type: "layout-shift", buffered: true });
        new PerformanceObserver(list => { for (const entry of list.getEntries()) window.__visualResetPerf.lcp = entry.startTime; }).observe({ type: "largest-contentful-paint", buffered: true });
      });
      const page = await context.newPage();
      const errors = [];
      page.on("pageerror", error => errors.push(error.message));
      try {
        const response = await page.goto(baseUrl, { waitUntil: "load" });
        assert.equal(response.status(), 200);
        await chooseMeasurement(page, "denied");
        assert.equal(await page.locator("main").count(), 1, "homepage retains one main landmark");
        assert.equal(await page.locator("h1").count(), 1, "homepage has one primary heading");
        assert.match(await page.locator("h1").innerText(), /Parfum/);
        await page.locator("[data-dufynd-bottle]").waitFor({ state: "visible" });
        const search = page.getByRole("searchbox", { name: "Duft oder Marke suchen", exact: true });
        await search.waitFor({ state: "visible" });
        const searchBounds = await search.boundingBox();
        assert.ok(searchBounds.y + searchBounds.height < 740, `${width}: search remains reachable in the first viewport`);
        assert.equal(await page.locator("a[data-dufynd-home-audience-card]").count(), 3);
        assert.equal(await page.locator("nav[aria-label='Duftwelten im Katalog'] a").count() > 0, true);
        await verifyHomepageImageScope(page, baseUrl);
        assert.deepEqual(await settleImages(page), [], `${width}: baseline photographs must decode`);
        assert.ok(await overflow(page) <= 1, `${width}: no horizontal overflow`);
        const running = await page.locator("[data-dufynd-bottle]").evaluate(element => element.getAnimations({ subtree: true }).filter(animation => animation.playState === "running" && Number(animation.effect?.getComputedTiming().duration) > 1).length);
        assert.equal(running, 0, "reduced motion disables bottle animation");
        const bottleControl = page.locator("[data-dufynd-bottle-control]").first();
        const bottleState = await bottleControl.getAttribute("aria-pressed");
        assert.equal(bottleState, "false", "bottle starts in its complete resting view");
        if (width < 1024) await bottleControl.tap();
        else { await bottleControl.focus(); await bottleControl.press("Enter"); }
        await page.waitForFunction(() => document.querySelector("[data-dufynd-bottle-control]")?.getAttribute("aria-pressed") === "true");
        assert.equal(await page.locator("[data-dufynd-bottle]").evaluate(element => element.getAnimations({ subtree: true }).filter(animation => animation.playState === "running" && Number(animation.effect?.getComputedTiming().duration) > 1).length), 0,
          "reduced motion keeps the interaction usable without animated movement");
        await bottleControl.click();
        await page.waitForFunction(() => document.querySelector("[data-dufynd-bottle-control]")?.getAttribute("aria-pressed") === "false");
        await bottleControl.evaluate(element => element.blur());
        await page.screenshot({ path: path.join(outputDir, `visual-reset-${width}-first.png`) });
        const journey = await captureJourney(page, outputDir, width);
        const metrics = await page.evaluate(() => ({ ...window.__visualResetPerf,
          dom_content_loaded_ms: performance.getEntriesByType("navigation")[0]?.domContentLoadedEventEnd,
          transferred_bytes: performance.getEntriesByType("resource").reduce((sum, resource) => sum + (resource.transferSize || 0), 0),
        }));
        assert.ok(metrics.cls < .1, `${width}: layout must remain stable`);
        const comparison = page.locator("a[data-dufynd-comparison-entry], [data-dufynd-comparison-entry] a").first();
        const comparisonUrl = new URL(await comparison.getAttribute("href"), baseUrl);
        assert.equal(comparisonUrl.pathname, "/vergleich");
        assert.equal(comparisonUrl.searchParams.get("left"), "SC-YSL-LIBRE-EDP-90");
        assert.equal(comparisonUrl.searchParams.get("right"), "SC-YSL-BLACK-OPIUM-EDP-90");
        const offer = page.locator("a[data-dufynd-offer-entry], [data-dufynd-offer-entry] a").first();
        const offerUrl = new URL(await offer.getAttribute("href"), baseUrl);
        assert.equal(offerUrl.origin, new URL(baseUrl).origin);
        assert.equal(offerUrl.pathname, "/duft/rabanne-1-million");
        assert.ok(!offerUrl.pathname.includes("clickout"));
        await comparison.focus();
        await comparison.press("Enter");
        await page.waitForURL(url => url.pathname === "/vergleich");
        await page.locator("h1").waitFor({ state: "visible" });
        await page.goto(baseUrl, { waitUntil: "load" });
        await search.fill("YSL Libre EDP 90ml");
        await search.press("Enter");
        await page.waitForURL(url => url.pathname === "/duft" && url.searchParams.get("q") === "YSL Libre EDP 90ml");
        await page.locator("h1").waitFor({ state: "visible" });
        assert.deepEqual(errors, [], `${width}: no browser runtime errors`);
        assert.deepEqual(requests.analytics, [], `${width}: denying consent suppresses all analytics requests`);
        assert.deepEqual(requests.clickouts, [], `${width}: no merchant clickout attempted`);
        assert.deepEqual(requests.blockedMutations, [], `${width}: no unmocked mutation attempted`);
        report.cases.push({ width, status: "passed", reduced_motion: true, search_submission: true, comparison_navigation: true, offer_route: offerUrl.pathname + offerUrl.hash, journey, metrics, fixture_requests: requests.fixtureRequests.length, analytics_requests: 0, clickouts: 0 });
      } catch (error) {
        await page.screenshot({ path: path.join(outputDir, `visual-reset-${width}-failure.png`) }).catch(() => {});
        report.cases.push({ width, status: "failed", error: String(error), requests });
        throw error;
      } finally { await context.close(); }
    }

    for (const variant of ["motion", "image-failure", "no-javascript"]) {
      const context = await browser.newContext({ viewport: { width: 390, height: 844 }, reducedMotion: variant === "motion" ? "no-preference" : "reduce", javaScriptEnabled: variant !== "no-javascript" });
      const requests = journal();
      await isolateNetwork(context, baseUrl, requests, variant === "image-failure");
      const page = await context.newPage();
      try {
        await page.goto(baseUrl, { waitUntil: "load" });
        if (variant !== "no-javascript") await chooseMeasurement(page, "denied");
        await page.locator("[data-dufynd-bottle]").waitFor({ state: "visible" });
        if (variant === "no-javascript") {
          assert.equal(await page.locator("[data-dufynd-bottle-control]").isVisible(), false,
            "static bottle fallback does not expose a nonfunctional interaction control");
        }
        if (variant === "motion") {
          const control = page.locator("[data-dufynd-bottle-control]").first();
          const attribute = await control.getAttribute("aria-pressed") !== null ? "aria-pressed" : "aria-expanded";
          const before = await control.getAttribute(attribute);
          assert.ok(["true", "false"].includes(before), "bottle interaction exposes its state accessibly");
          await control.focus();
          await control.press("Enter");
          await page.waitForFunction(({ attribute, before }) => document.querySelector("[data-dufynd-bottle-control]")?.getAttribute(attribute) !== before, { attribute, before });
        }
        if (variant === "image-failure") {
          const original = page.locator("a[data-dufynd-original-card]");
          await original.scrollIntoViewIfNeeded();
          await original.locator("[data-dufynd-visual-state='unavailable']").waitFor({ state: "visible" });
          assert.match(await original.innerText(), /La Vie est Belle/);
          assert.equal(new URL(await original.getAttribute("href"), baseUrl).pathname, "/duft/lancome-la-vie-est-belle");
          assert.equal(await original.locator("img").count(), 0, "failed image is replaced by honest text, not a broken bitmap");
        }
        assert.ok(await overflow(page) <= 1);
        assert.deepEqual(requests.analytics, []);
        assert.deepEqual(requests.clickouts, []);
        await page.screenshot({ path: path.join(outputDir, `visual-reset-390-${variant}.png`) });
        report.cases.push({ variant, status: "passed", analytics_requests: 0, clickouts: 0 });
      } finally { await context.close(); }
    }
    return report;
  } finally {
    await writeFile(path.join(outputDir, "visual-reset-report.json"), JSON.stringify(report, null, 2) + "\n");
  }
}

if (process.argv[1] && import.meta.url === pathToFileURL(path.resolve(process.argv[1])).href) {
  const args = process.argv.slice(2);
  const value = (flag, fallback) => args.includes(flag) ? args[args.indexOf(flag) + 1] : fallback;
  const { chromium } = await import("playwright");
  const browser = await chromium.launch({ headless: true });
  try {
    const report = await verifyVisualReset(browser, value("--base-url", "http://127.0.0.1:3000"), path.resolve(value("--out", ".visual-reset-qa")));
    console.log(JSON.stringify(report, null, 2));
  } finally { await browser.close(); }
}
