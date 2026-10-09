/* Capture the actual Control Room with an owner-allowlisted DTO supplied on disk.
 * This is a read-only data replay, NOT an authenticated production session.
 * No credentials, provider calls, mutation requests or synthetic workers are used.
 * Usage: node control_room_capture.cjs <snapshot.json> <output-directory>
 * Requires Playwright; optional CONTROL_ROOM_QA_CHROMIUM selects a local binary.
 */
const fs = require("fs");
const path = require("path");
const assert = require("assert/strict");
const crypto = require("crypto");
const { chromium } = require("playwright");
(async () => {
  const snapshot = JSON.parse(fs.readFileSync(process.argv[2], "utf8"));
  assert.equal(snapshot.version, 1);
  assert.equal(snapshot.read_only, true);
  const output = path.resolve(process.argv[3]);
  fs.mkdirSync(output, { recursive: true });
  const source = path.resolve(__dirname, "../../examples/retail/api/control_room");
  const browser = await chromium.launch({
    ...(process.env.CONTROL_ROOM_QA_CHROMIUM ? { executablePath: process.env.CONTROL_ROOM_QA_CHROMIUM } : {}),
    args: ["--no-sandbox", "--disable-dev-shm-usage", "--disable-gpu"],
  });
  const report = {
    mode: "read-only replay of captured owner-allowlisted live data; no production Owner session",
    generated_at: snapshot.generated_at,
    captured_at: new Date().toISOString(),
    template_voice_configuration: "disabled; production voice configuration not observed",
    source_sha256: Object.fromEntries(["index.html", "room.js", "room.css"].map(name => [name, crypto.createHash("sha256").update(fs.readFileSync(path.join(source, name))).digest("hex")])),
    measurements: [], screenshots: [], errors: [],
  };
  for (const width of [320, 390, 430, 768, 1280, 1440, 1920]) {
    const height = width >= 1920 ? 1080 : width >= 1280 ? 900 : 844;
    const page = await browser.newPage({ viewport: { width, height }, reducedMotion: "reduce" });
    page.on("pageerror", error => report.errors.push(error.message));
    await page.route("**/*", route => {
      assert.equal(route.request().method(), "GET", "No mutations during data capture");
      const url = new URL(route.request().url());
      assert.equal(url.host, "dufynd-qa.local", "No external requests");
      if (url.pathname.endsWith("/snapshot")) return route.fulfill({ json: snapshot });
      const name = url.pathname.endsWith("/jarvis") ? "index.html" : url.pathname.split("/").pop();
      assert.ok(["index.html", "room.css", "room.js"].includes(name));
      return route.fulfill({ body: fs.readFileSync(path.join(source, name)), contentType: name.endsWith("css") ? "text/css" : name.endsWith("js") ? "application/javascript" : "text/html" });
    });
    await page.goto("https://dufynd-qa.local/internal/jarvis");
    await page.waitForFunction(() => document.body.dataset.executionMode);
    for (const [view, hash] of [["now", "command"], ["workers", "crew"], ["approvals", "decisions"], ["systems", "system-health"]]) {
      await page.evaluate(hash => { location.hash = hash; }, hash);
      await page.waitForFunction(view => document.body.dataset.cockpitView === (view === "approvals" ? "blockers" : view), view);
      await page.evaluate(() => { document.activeElement?.blur(); window.scrollTo(0, 0); });
      assert.equal(await page.evaluate(() => document.documentElement.scrollWidth > innerWidth), false, `${width}/${view}: horizontal overflow`);
      const dims = await page.evaluate(() => ({ height: document.documentElement.scrollHeight, width: document.documentElement.scrollWidth }));
      const box = async selector => { const b = await page.locator(selector).boundingBox(); return b ? { y: Math.round(b.y), bottom: Math.round(b.y + b.height) } : null; };
      const measure = { width, height, view, document: dims };
      if (view === "now") {
        measure.work = await box("#work");
        measure.output = await box("#v2-last-output");
        measure.money = await box("#pulse-money");
        measure.cost = await box("#pulse-cost");
        measure.next = await box(".next-panel");
        const limit = width >= 1280 ? height : height * 2;
        for (const name of ["output", "money", "cost", "next"]) assert.ok(measure[name].bottom < limit, `${width}: ${name} must fit the acceptance area`);
      }
      report.measurements.push(measure);
      for (const fullPage of [false, true]) {
        const name = `live-data-replay-${width}-${view}-${fullPage ? "full" : "viewport"}.png`;
        await page.screenshot({ path: path.join(output, name), fullPage });
        report.screenshots.push({ name, width, height, view, fullPage, sha256: crypto.createHash("sha256").update(fs.readFileSync(path.join(output, name))).digest("hex") });
      }
      if (width <= 768 && view === "now") {
        await page.evaluate(() => window.scrollTo(0, innerHeight - 80));
        const name = `live-data-replay-${width}-now-second-viewport.png`;
        await page.screenshot({ path: path.join(output, name) });
        report.screenshots.push({ name, width, height, view, sha256: crypto.createHash("sha256").update(fs.readFileSync(path.join(output, name))).digest("hex") });
      }
    }
    await page.close();
  }
  await browser.close();
  assert.deepEqual(report.errors, []);
  fs.writeFileSync(path.join(output, "capture-manifest.json"), JSON.stringify(report, null, 2));
  console.log(JSON.stringify({ screenshots: report.screenshots.length, measurements: report.measurements, errors: report.errors }));
})();
