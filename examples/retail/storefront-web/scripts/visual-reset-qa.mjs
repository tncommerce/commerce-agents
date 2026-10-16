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
async function loadImageFixtures() {
  if (process.env.QA_IMAGE_MANIFEST && !imageFixtures.size) {
    for (const asset of JSON.parse(await readFile(process.env.QA_IMAGE_MANIFEST, "utf8"))) {
      assert.ok(photos.some(photo => photo.url === asset.url), "image fixtures may only mirror registered source photographs");
      const bytes = await readFile(asset.path);
      assert.equal(createHash("sha256").update(bytes).digest("hex"), asset.sha256, "cached photograph must match its recorded source bytes");
      imageFixtures.set(asset.url, { body: bytes, contentType: asset.content_type });
    }
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
    if (request.resourceType() === "script") journal.scriptRequests.push(url.pathname);
    if (request.resourceType() === "font") journal.fontRequests.push(url.pathname);
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
    if (failImages && request.resourceType() === "image" && photos.some(photo => photo.url === url.href)) {
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
  return { fixtureRequests: [], analytics: [], clickouts: [], blockedMutations: [], blockedExternal: [], scriptRequests: [], fontRequests: [] };
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

// These fixtures exercise both actual WebGL and its production device gates on
// software-GPU CI hosts. They never disable a production gate in application code.
async function deviceHints(context, variant = "capable") {
  await context.addInitScript(variant => {
    Object.defineProperty(navigator, "hardwareConcurrency", { configurable: true, get: () => variant === "low-cores" ? 2 : 8 });
    Object.defineProperty(navigator, "deviceMemory", { configurable: true, get: () => variant === "low-memory" ? 2 : 8 });
    const connection = navigator.connection || {};
    Object.defineProperty(connection, "saveData", { configurable: true, get: () => variant === "save-data" });
    if (!navigator.connection) Object.defineProperty(navigator, "connection", { configurable: true, value: connection });
    // CI's renderer remains real software WebGL. Only the capability string is
    // controlled so mesh/shader tests and the software fallback are independent.
    const prototype = window.WebGL2RenderingContext?.prototype;
    if (prototype) {
      const getParameter = prototype.getParameter;
      prototype.getParameter = function (parameter) {
        if (parameter === 0x9246) return variant === "software-renderer"
          ? "ANGLE (Google, Vulkan SwiftShader Device (Subzero), SwiftShader driver)"
          : "QA capable renderer fixture";
        return getParameter.call(this, parameter);
      };
    }
    if (variant === "no-webgl") {
      const getContext = HTMLCanvasElement.prototype.getContext;
      HTMLCanvasElement.prototype.getContext = function (kind, ...args) {
        return /^(webgl2?|experimental-webgl)$/.test(kind) ? null : getContext.call(this, kind, ...args);
      };
    }
  }, variant);
}

async function spatialSnapshot(page) {
  return page.locator("[data-dufynd-spatial-canvas]").evaluate(element => ({
    renders: Number(element.dataset.renderCount), pending: element.dataset.framePending,
    triangles: Number(element.dataset.triangles), draw_calls: Number(element.dataset.drawCalls),
    render_cpu_submission_ms: Number(element.dataset.renderDurationMs),
    parts: Object.fromEntries(["capY", "atomizerY", "liquidY", "glassY"].map(name => [name, Number(element.dataset[name])])),
    canvas_width: element.querySelector("canvas")?.width,
    canvas_height: element.querySelector("canvas")?.height,
  }));
}

async function settledSpatial(page) {
  await page.waitForFunction(() => {
    const host = document.querySelector("[data-dufynd-spatial-canvas]");
    return host?.dataset.framePending === "false" && Number(host.dataset.renderCount) > 0;
  }, null, { timeout: 30_000 });
  return spatialSnapshot(page);
}

async function verifySpatialIdle(page) {
  const before = await settledSpatial(page);
  await page.waitForTimeout(450);
  const after = await spatialSnapshot(page);
  assert.equal(after.renders, before.renders, "resting perfume does not keep rendering frames");
  assert.equal(after.pending, "false", "resting perfume does not keep scheduling a frame");
  return after;
}

async function verifyStaticPoster(page) {
  const poster = page.locator("[data-dufynd-spatial-poster]").first();
  await poster.waitFor({ state: "visible" });
  assert.equal(await poster.evaluate(async image => {
    await image.decode();
    return image.complete && image.naturalWidth > 0 && image.naturalHeight > 0;
  }), true, "fallback shows a decoded rendering of the same original perfume scene");
  assert.equal(await page.locator("[data-dufynd-spatial-canvas] canvas").count(), 0,
    "fallback keeps no live WebGL canvas");
}

async function captureSection(page, outputDir, width, name, locator) {
  await locator.scrollIntoViewIfNeeded();
  await locator.screenshot({ path: path.join(outputDir, `visual-reset-${width}-${name}.png`) });
}

export async function verifyVisualReset(browser, baseUrl, outputDir) {
  requireLocalBase(baseUrl);
  await loadImageFixtures();
  await mkdir(outputDir, { recursive: true });
  const report = { generated_at: new Date().toISOString(), base_url: baseUrl, environment: "local fixture with real software WebGL; capable device hints/renderer name are explicit test fixtures, not a physical GPU or field-performance measurement", cases: [] };
  try {
    for (const width of [320, 390, 768, 1024, 1440]) {
      const context = await browser.newContext({ viewport: { width, height: width < 640 ? 844 : 1000 }, reducedMotion: "no-preference", hasTouch: width < 1024 });
      const requests = journal();
      await deviceHints(context);
      await isolateNetwork(context, baseUrl, requests);
      await context.addInitScript(() => {
        window.__visualResetPerf = { cls: 0, lcp: 0, long_tasks: [] };
        new PerformanceObserver(list => { for (const entry of list.getEntries()) if (!entry.hadRecentInput) window.__visualResetPerf.cls += entry.value; }).observe({ type: "layout-shift", buffered: true });
        new PerformanceObserver(list => { for (const entry of list.getEntries()) window.__visualResetPerf.lcp = entry.startTime; }).observe({ type: "largest-contentful-paint", buffered: true });
        if (PerformanceObserver.supportedEntryTypes.includes("longtask")) new PerformanceObserver(list => { for (const entry of list.getEntries()) window.__visualResetPerf.long_tasks.push({ start_ms: entry.startTime, duration_ms: entry.duration }); }).observe({ type: "longtask", buffered: true });
      });
      const page = await context.newPage();
      const errors = [];
      const graphicsErrors = [];
      page.on("pageerror", error => errors.push(error.message));
      page.on("console", message => {
        if (message.type() === "error" && /THREE|WebGL|GL_INVALID|shader|program/i.test(message.text())) graphicsErrors.push(message.text());
      });
      try {
        const response = await page.goto(baseUrl, { waitUntil: "load" });
        assert.equal(response.status(), 200);
        // Let software-GPU shader initialization settle before the ordinary UI
        // consent action. Real software devices are separately required to skip it.
        await page.waitForFunction(() => document.querySelector("[data-dufynd-bottle]")?.getAttribute("data-spatial-state") === "ready", null, { timeout: 45_000 });
        await settledSpatial(page);
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
        await page.waitForFunction(() => document.querySelector("[data-dufynd-bottle]")?.getAttribute("data-spatial-state") === "ready", null, { timeout: 30_000 });
        const resting = await verifySpatialIdle(page);
        const initialScripts = [...new Set(requests.scriptRequests)];
        const initialFonts = [...new Set(requests.fontRequests)];
        assert.ok(resting.triangles > 100 && resting.draw_calls > 0, "capable device renders real mesh geometry");
        assert.ok(resting.canvas_width > 100 && resting.canvas_height > 100, "spatial canvas has a meaningful drawing buffer");
        const bottleControl = page.locator("[data-dufynd-bottle-control]").first();
        assert.equal(await bottleControl.getAttribute("aria-pressed"), "false", "bottle starts in its complete resting view");
        await page.screenshot({ path: path.join(outputDir, `visual-reset-${width}-first.png`) });
        if (width < 1024) await bottleControl.tap();
        else { await bottleControl.focus(); await bottleControl.press("Enter"); }
        await page.waitForFunction(() => document.querySelector("[data-dufynd-bottle-control]")?.getAttribute("aria-pressed") === "true");
        await page.waitForFunction(closedY => Number(document.querySelector("[data-dufynd-spatial-canvas]")?.dataset.capY) > closedY + .1, resting.parts.capY);
        const explored = await settledSpatial(page);
        assert.ok(explored.parts.capY > resting.parts.capY + .1, "exploring the perfume raises the actual cap mesh");
        assert.ok(explored.parts.atomizerY > resting.parts.atomizerY + .01, "exploded view reveals a separate atomizer mesh");
        assert.ok(explored.renders > resting.renders, "signature interaction renders the changed scene");
        await page.screenshot({ path: path.join(outputDir, `visual-reset-${width}-interaction.png`) });
        await bottleControl.click();
        await page.mouse.move(0, 0);
        await page.waitForFunction(() => document.querySelector("[data-dufynd-bottle-control]")?.getAttribute("aria-pressed") === "false");
        await page.waitForFunction(closedY => Math.abs(Number(document.querySelector("[data-dufynd-spatial-canvas]")?.dataset.capY) - closedY) < .01, resting.parts.capY);
        const restored = await verifySpatialIdle(page);
        for (const part of Object.keys(resting.parts)) assert.ok(Math.abs(restored.parts[part] - resting.parts[part]) < .01, `${part}: closing restores the original composition`);
        await bottleControl.evaluate(element => element.blur());
        const firstScrollProducts = await page.locator("[data-dufynd-partner-photo] img").evaluateAll(images => images.map(image => {
          const rect = image.getBoundingClientRect();
          return { top: rect.top, bottom: rect.bottom, left: rect.left, right: rect.right,
            within_first_scroll: rect.top < innerHeight * 2 && rect.bottom > 0 && rect.left < innerWidth && rect.right > 0 };
        }));
        assert.ok(firstScrollProducts.filter(image => image.within_first_scroll).length >= 2,
          `${width}: first scroll reveals multiple real perfume photographs`);
        const journey = await captureJourney(page, outputDir, width);
        const selection = page.locator(".wow-selection");
        await captureSection(page, outputDir, width, "products", selection);
        await page.locator("#haendlerangebote").scrollIntoViewIfNeeded();
        assert.equal(await page.locator("[data-dufynd-bottle]").evaluate(element => {
          const clip = element.closest(".panel-scroll")?.getBoundingClientRect();
          return element.getBoundingClientRect().bottom <= (clip?.top || 0);
        }), true, "offscreen performance sample actually moves the perfume outside its scroll viewport");
        const offscreen = await settledSpatial(page);
        await page.waitForTimeout(450);
        assert.equal((await spatialSnapshot(page)).renders, offscreen.renders, "offscreen perfume consumes no additional render frames");
        await captureSection(page, outputDir, width, "comparison", page.locator("[data-dufynd-comparison-entry]").locator("xpath=ancestor::section[1]"));
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
        assert.deepEqual(graphicsErrors, [], `${width}: no WebGL shader/program errors`);
        assert.deepEqual(requests.analytics, [], `${width}: denying consent suppresses all analytics requests`);
        assert.deepEqual(requests.clickouts, [], `${width}: no merchant clickout attempted`);
        assert.deepEqual(requests.blockedMutations, [], `${width}: no unmocked mutation attempted`);
        assert.deepEqual(requests.blockedExternal, [], `${width}: no external script/model/service requested`);
        report.cases.push({ width, status: "passed", reduced_motion: false, spatial: { resting, explored, restored, offscreen }, scripts: initialScripts, fonts: initialFonts, search_submission: true, comparison_navigation: true, offer_route: offerUrl.pathname + offerUrl.hash, first_scroll_products: firstScrollProducts, journey, metrics, fixture_requests: requests.fixtureRequests.length, analytics_requests: 0, clickouts: 0 });
      } catch (error) {
        await page.screenshot({ path: path.join(outputDir, `visual-reset-${width}-failure.png`) }).catch(() => {});
        report.cases.push({ width, status: "failed", error: String(error), graphics_errors: graphicsErrors, spatial_state: await page.locator("[data-dufynd-bottle]").first().getAttribute("data-spatial-state").catch(() => null), fallback_reason: await page.locator("[data-dufynd-bottle]").first().getAttribute("data-fallback-reason").catch(() => null), requests });
        throw error;
      } finally { await context.close(); }
    }

    for (const variant of ["reduced-motion", "save-data", "low-memory", "low-cores", "no-webgl", "software-renderer", "context-lost", "motion-preference-change", "motion-during-renderer-load", "font-late", "image-failure", "no-javascript"]) {
      const context = await browser.newContext({ viewport: { width: 390, height: 844 }, hasTouch: true,
        reducedMotion: ["reduced-motion", "font-late", "image-failure"].includes(variant) ? "reduce" : "no-preference",
        javaScriptEnabled: variant !== "no-javascript" });
      const requests = journal();
      await deviceHints(context, variant);
      await isolateNetwork(context, baseUrl, requests, variant === "image-failure");
      let releaseRenderer = () => {};
      let rendererRequested = Promise.resolve();
      if (variant === "motion-during-renderer-load") {
        const defaultScripts = report.cases.find(item => item.width === 390).scripts;
        const reducedScripts = report.cases.find(item => item.variant === "reduced-motion").scripts;
        const rendererScripts = defaultScripts.filter(url => !reducedScripts.includes(url));
        assert.ok(rendererScripts.length > 0, "race fixture identifies the deferred renderer");
        const hold = new Promise(resolve => { releaseRenderer = resolve; });
        let requested;
        rendererRequested = new Promise(resolve => { requested = resolve; });
        await context.route("**/*", async route => {
          if (route.request().resourceType() === "script" && rendererScripts.includes(new URL(route.request().url()).pathname)) {
            requested();
            await hold;
          }
          return route.fallback();
        });
      }
      if (variant === "font-late") {
        await context.route("**/*", async route => {
          if (route.request().resourceType() === "font") await new Promise(resolve => setTimeout(resolve, 1200));
          return route.fallback();
        });
        await context.addInitScript(() => {
          window.__lateFontCLS = 0;
          new PerformanceObserver(list => { for (const entry of list.getEntries()) if (!entry.hadRecentInput) window.__lateFontCLS += entry.value; }).observe({ type: "layout-shift", buffered: true });
        });
      }
      const page = await context.newPage();
      const errors = [];
      page.on("pageerror", error => errors.push(error.message));
      try {
        await page.goto(baseUrl, { waitUntil: "load" });
        if (["context-lost", "motion-preference-change"].includes(variant)) {
          await page.waitForFunction(() => document.querySelector("[data-dufynd-bottle]")?.getAttribute("data-spatial-state") === "ready", null, { timeout: 45_000 });
          await settledSpatial(page);
        }
        if (variant !== "no-javascript") await chooseMeasurement(page, "denied");
        const bottle = page.locator("[data-dufynd-bottle]");
        await bottle.waitFor({ state: "visible" });
        if (variant === "motion-during-renderer-load") {
          let timeout;
          await Promise.race([rendererRequested, new Promise((_, reject) => { timeout = setTimeout(() => reject(new Error("deferred renderer was not requested")), 10_000); })]);
          clearTimeout(timeout);
          await page.emulateMedia({ reducedMotion: "reduce" });
          await page.waitForFunction(() => document.querySelector("[data-dufynd-bottle]")?.getAttribute("data-spatial-state") === "fallback");
          releaseRenderer();
          await page.waitForLoadState("networkidle");
          assert.equal(await bottle.getAttribute("data-spatial-state"), "fallback", "late renderer import cannot undo a newer reduced-motion preference");
        }
        if (variant === "motion-preference-change") {
          await page.waitForFunction(() => document.querySelector("[data-dufynd-bottle]")?.getAttribute("data-spatial-state") === "ready", null, { timeout: 30_000 });
          await settledSpatial(page);
          await page.emulateMedia({ reducedMotion: "reduce" });
        }
        if (variant === "context-lost") {
          await page.waitForFunction(() => document.querySelector("[data-dufynd-bottle]")?.getAttribute("data-spatial-state") === "ready", null, { timeout: 30_000 });
          await settledSpatial(page);
          assert.equal(await page.locator("[data-dufynd-spatial-canvas] canvas").evaluate(canvas => {
            const gl = canvas.getContext("webgl2");
            const extension = gl?.getExtension("WEBGL_lose_context");
            extension?.loseContext();
            return Boolean(extension);
          }), true, "browser exposes real WebGL context-loss simulation");
        }
        if (variant !== "no-javascript") {
          await page.waitForFunction(() => document.querySelector("[data-dufynd-bottle]")?.getAttribute("data-spatial-state") === "fallback");
          const expectedReason = ["image-failure", "font-late", "motion-preference-change", "motion-during-renderer-load"].includes(variant) ? "reduced-motion" : variant;
          assert.equal(await bottle.getAttribute("data-fallback-reason"), expectedReason,
            `${variant}: the expected device/runtime guard chose the poster`);
        }
        await verifyStaticPoster(page);
        if (variant === "no-javascript") {
          assert.equal(await page.locator("[data-dufynd-bottle-control]").isVisible(), false,
            "static bottle fallback does not expose a nonfunctional interaction control");
          assert.deepEqual(requests.scriptRequests, [], "no-JS fallback does not request a renderer bundle");
        } else {
          const control = page.locator("[data-dufynd-bottle-control]").first();
          if (await control.isVisible() && await control.isEnabled()) {
            const before = await page.locator("[data-dufynd-spatial-poster]").first().getAttribute("src");
            await control.tap();
            await page.waitForFunction(previous => document.querySelector("[data-dufynd-spatial-poster]")?.getAttribute("src") !== previous, before);
            await verifyStaticPoster(page);
            const animated = await bottle.evaluate(element => element.getAnimations({ subtree: true }).filter(animation => animation.playState === "running" && Number(animation.effect?.getComputedTiming().duration) > 1).length);
            if (["reduced-motion", "motion-preference-change", "motion-during-renderer-load"].includes(variant)) assert.equal(animated, 0, "reduced-motion exploration changes stills without animated movement");
          }
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
        assert.deepEqual(errors, [], `${variant}: no browser runtime error`);
        assert.deepEqual(requests.analytics, []);
        assert.deepEqual(requests.clickouts, []);
        assert.deepEqual(requests.blockedMutations, []);
        const fallbackReason = await bottle.getAttribute("data-fallback-reason");
        const lateFontCLS = variant === "font-late" ? await page.evaluate(() => window.__lateFontCLS) : null;
        if (variant === "font-late") assert.ok(lateFontCLS < .1, "delayed editorial font must not cause a large layout shift");
        await page.screenshot({ path: path.join(outputDir, `visual-reset-390-${variant}.png`) });
        if (variant === "no-javascript") {
          const nativeSearch = page.getByRole("searchbox", { name: "Duft oder Marke suchen", exact: true });
          await nativeSearch.fill("YSL Libre EDP 90ml");
          await nativeSearch.press("Enter");
          await page.waitForURL(url => url.pathname === "/duft" && url.searchParams.get("q") === "YSL Libre EDP 90ml");
          await page.locator("h1").waitFor({ state: "visible" });
          assert.deepEqual(requests.scriptRequests, [], "native search remains usable without any JavaScript execution");
        }
        report.cases.push({ variant, status: "passed", fallback_reason: fallbackReason,
          scripts: [...new Set(requests.scriptRequests)], fonts: [...new Set(requests.fontRequests)], late_font_cls: lateFontCLS, analytics_requests: 0, clickouts: 0 });
      } catch (error) {
        await page.screenshot({ path: path.join(outputDir, `visual-reset-390-${variant}-failure.png`) }).catch(() => {});
        report.cases.push({ variant, status: "failed", error: String(error), requests });
        throw error;
      } finally { releaseRenderer(); await context.close(); }
    }
    const defaultScripts = new Set(report.cases.find(item => item.width === 390).scripts);
    const reducedScripts = new Set(report.cases.find(item => item.variant === "reduced-motion").scripts);
    const deferredRendererScripts = [...defaultScripts].filter(url => !reducedScripts.has(url));
    assert.ok(deferredRendererScripts.length > 0, "capable devices fetch a genuinely separate renderer chunk");
    for (const variant of ["save-data", "low-memory", "low-cores", "no-webgl", "software-renderer"]) {
      const scripts = report.cases.find(item => item.variant === variant).scripts;
      assert.ok(!scripts.some(url => deferredRendererScripts.includes(url)), `${variant}: static fallback does not fetch the deferred renderer`);
    }
    report.deferred_renderer_scripts = deferredRendererScripts;
    // A lazy import that finishes after scrolling away must not start hidden GPU work.
    {
      const context = await browser.newContext({ viewport: { width: 390, height: 844 }, hasTouch: true, reducedMotion: "no-preference" });
      const requests = journal();
      await deviceHints(context);
      await isolateNetwork(context, baseUrl, requests);
      let release;
      const hold = new Promise(resolve => { release = resolve; });
      let requested;
      const imported = new Promise(resolve => { requested = resolve; });
      await context.route("**/*", async route => {
        if (route.request().resourceType() === "script" && deferredRendererScripts.includes(new URL(route.request().url()).pathname)) {
          requested();
          await hold;
        }
        return route.fallback();
      });
      const page = await context.newPage();
      try {
        await page.goto(baseUrl, { waitUntil: "load" });
        await chooseMeasurement(page, "denied");
        let timer;
        await Promise.race([imported, new Promise((_, reject) => { timer = setTimeout(() => reject(new Error("visibility-race renderer request did not start")), 10_000); })]);
        clearTimeout(timer);
        await page.locator("#haendlerangebote").scrollIntoViewIfNeeded();
        assert.equal(await page.locator("[data-dufynd-bottle]").evaluate(element => element.getBoundingClientRect().bottom < 0), true);
        release();
        await page.waitForLoadState("networkidle");
        assert.equal(await page.locator("[data-dufynd-spatial-canvas] canvas").count(), 0,
          "resolving a lazy renderer after scroll-away must not initialize an offscreen canvas");
        assert.equal(await page.locator("[data-dufynd-spatial-canvas]").getAttribute("data-render-count"), null,
          "no initial GPU frame is submitted while the perfume is offscreen");
        await page.locator("[data-dufynd-bottle]").scrollIntoViewIfNeeded();
        await page.waitForFunction(() => document.querySelector("[data-dufynd-bottle]")?.getAttribute("data-spatial-state") === "ready", null, { timeout: 45_000 });
        const resumed = await verifySpatialIdle(page);
        assert.ok(resumed.renders > 0, "returning to the perfume initializes and renders it normally");
        assert.deepEqual(requests.analytics, []);
        assert.deepEqual(requests.clickouts, []);
        assert.deepEqual(requests.blockedMutations, []);
        report.cases.push({ variant: "scroll-during-renderer-load", status: "passed", no_offscreen_initial_frame: true, resumed });
      } catch (error) {
        report.cases.push({ variant: "scroll-during-renderer-load", status: "failed", error: String(error) });
        throw error;
      } finally { release(); await context.close(); }
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
  const browser = await chromium.launch({ headless: true, args: ["--enable-unsafe-swiftshader"] });
  try {
    const report = await verifyVisualReset(browser, value("--base-url", "http://127.0.0.1:3000"), path.resolve(value("--out", ".visual-reset-qa")));
    console.log(JSON.stringify(report, null, 2));
  } finally { await browser.close(); }
}
