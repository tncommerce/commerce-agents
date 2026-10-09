/* Isolated V2 acceptance replay. All requests are fulfilled locally; no provider calls.
 * NODE_PATH=<playwright parent> CONTROL_ROOM_QA_CHROMIUM=<binary> node ... <fixture.json>
 * Optional CONTROL_ROOM_QA_OUTPUT: screenshot directory, defaults to OS temp. */
const fs = require("fs");
const path = require("path");
const os = require("os");
const assert = require("assert/strict");
const { chromium } = require("playwright");
(async () => {
  const browser = await chromium.launch({
    headless: true,
    ...(process.env.CONTROL_ROOM_QA_CHROMIUM
      ? { executablePath: process.env.CONTROL_ROOM_QA_CHROMIUM }
      : {}),
    args: ["--no-sandbox", "--disable-dev-shm-usage", "--disable-gpu"],
  });
  const fixture = JSON.parse(fs.readFileSync(process.argv[2], "utf8"));
  const source = path.resolve(
    __dirname,
    "../../examples/retail/api/control_room",
  );
  const output =
    process.env.CONTROL_ROOM_QA_OUTPUT ||
    path.join(os.tmpdir(), "dufynd-cockpit-v2-qa");
  fs.mkdirSync(output, { recursive: true });
  const errors = [],
    writes = [],
    measurements = [];
  for (const width of [320, 390, 430, 768, 1280, 1440, 1920]) {
    let snapshot = structuredClone(fixture._qa_scenarios.active),
      unavailable = false;
    const page = await browser.newPage({
      viewport: { width, height: 844 },
      reducedMotion: "reduce",
    });
    page.on("pageerror", (error) => errors.push(error.message));
    await page.route("**/*", (route) => {
      if (route.request().method() !== "GET")
        writes.push(route.request().url());
      const pathname = new URL(route.request().url()).pathname;
      if (pathname.endsWith("/snapshot"))
        return unavailable
          ? route.fulfill({ status: 503, body: "Unavailable" })
          : route.fulfill({ json: snapshot });
      const name = pathname.endsWith("/jarvis")
        ? "index.html"
        : pathname.split("/").pop();
      assert.ok(
        ["index.html", "room.js", "room.css"].includes(name),
        "Unexpected network request",
      );
      return route.fulfill({
        contentType: name.endsWith("css")
          ? "text/css"
          : name.endsWith("js")
            ? "application/javascript"
            : "text/html",
        body: fs.readFileSync(path.join(source, name)),
      });
    });
    const refresh = async () => {
      const response = page.waitForResponse((r) =>
        r.url().endsWith("/snapshot"),
      );
      await page.locator("#refresh").click();
      await response;
      await page.evaluate(() => new Promise(requestAnimationFrame));
    };
    const go = async (hash, view) => {
      await page.evaluate((hash) => {
        location.hash = hash;
      }, hash);
      await page.waitForFunction(
        (view) => document.body.dataset.cockpitView === view,
        view,
      );
    };
    const fits = async () =>
      assert.equal(
        await page.evaluate(
          () => document.documentElement.scrollWidth > innerWidth,
        ),
        false,
        `${width}px horizontal overflow`,
      );
    await page.goto("https://dufynd-qa.local/internal/jarvis");
    await page.waitForFunction(
      () => document.body.dataset.executionMode === "working",
    );
    assert.equal(await page.locator("#crew").isVisible(), false);
    assert.equal(await page.locator("#work").isVisible(), true);
    assert.equal(await page.locator("#decisions").isVisible(), false);
    const ids = await page
      .locator("[id]")
      .evaluateAll((nodes) => nodes.map((n) => n.id));
    assert.equal(new Set(ids).size, ids.length);
    const nav = width <= 768 ? ".mobile-nav" : ".sidebar nav";
    await page.locator(`${nav} [data-view="workers"]`).focus();
    await page.keyboard.press("Enter");
    await page.waitForFunction(
      () => document.body.dataset.cockpitView === "workers",
    );
    assert.equal(await page.locator("#crew").isVisible(), true);
    assert.equal(await page.locator("#work").isVisible(), false);
    assert.equal(
      await page
        .locator("#crew")
        .evaluate((el) => el === document.activeElement),
      true,
    );
    await refresh();
    assert.equal(
      await page.locator("body").getAttribute("data-cockpit-view"),
      "workers",
    );
    await fits();
    await page.screenshot({
      path: path.join(output, `v2-${width}-workers.png`),
      fullPage: true,
    });
    await go("system-health", "systems");
    assert.equal(await page.locator("#system-health").isVisible(), true);
    assert.equal(
      await page
        .locator("#system-health")
        .evaluate((el) =>
          el.parentElement.classList.contains("cockpit-center"),
        ),
      true,
    );
    const health = page.locator(".health-evidence").first();
    await health.locator("summary").click();
    await health.locator("summary").focus();
    // A timer-style refresh must retain the disclosure and focus.
    await page.evaluate(() => document.querySelector("#refresh").click());
    await page.waitForFunction(
      () => !document.querySelector("#refresh").disabled,
    );
    assert.equal(await health.getAttribute("open"), "");
    assert.equal(
      await health
        .locator("summary")
        .evaluate((el) => el === document.activeElement),
      true,
    );
    await fits();
    await page.screenshot({
      path: path.join(output, `v2-${width}-systems.png`),
      fullPage: true,
    });
    for (const name of [
      "active",
      "healthy",
      "warning",
      "gate",
      "critical",
      "old",
    ]) {
      snapshot = structuredClone(fixture._qa_scenarios[name]);
      await go("command", "now");
      await refresh();
      await fits();
      if (name === "old")
        assert.match(
          await page.locator("#risk-level").innerText(),
          /BEOBACHTEN/,
        );
      if (name === "gate") {
        assert.equal(await page.locator("#approval-alert").isVisible(), true);
        await go("decisions", "blockers");
        assert.equal(await page.locator("#decisions").isVisible(), true);
        const actionBox = await page.locator("#decisions").boundingBox();
        assert.ok(actionBox.y >= 0 && actionBox.y + Math.min(actionBox.height, 300) < 844, "Owner destination is brought into view");
        await fits();
        await page.screenshot({
          path: path.join(output, `v2-${width}-blockers.png`),
          fullPage: true,
        });
        await go("command", "now");
      }
      if (name === "active") {
        const bounds = await page.locator("#work").boundingBox();
        const last = await page.locator("#v2-last-output").boundingBox();
        assert.ok(bounds.y < 844, "Working task begins in first viewport");
        assert.ok(
          last.y + last.height < 844 * 2,
          "Output summary within two viewports",
        );
        measurements.push({
          width,
          workY: Math.round(bounds.y),
          outputY: Math.round(last.y),
        });
      }
      await page.screenshot({
        path: path.join(output, `v2-${width}-${name}.png`),
        fullPage: true,
      });
    }
    snapshot = structuredClone(fixture._qa_scenarios.active);
    await refresh();
    unavailable = true;
    await refresh();
    assert.equal(await page.locator("#active-workers").innerText(), "—");
    assert.equal(await page.locator("#working-count").innerText(), "—");
    assert.match(
      await page.locator("#risk-title").innerText(),
      /NICHT BESTÄTIGT/,
    );
    assert.equal(
      await page.locator("#overview-system-health .health-green").count(),
      0,
    );
    await go("crew", "workers");
    assert.equal(
      await page.locator('.crew-node[data-active="true"]').count(),
      0,
    );
    assert.match(
      await page.locator("#crew-live-now").innerText(),
      /LETZTER STAND/,
    );
    await fits();
    await page.screenshot({
      path: path.join(output, `v2-${width}-unavailable.png`),
      fullPage: true,
    });
    unavailable = false;
    await refresh();
    assert.equal(await page.locator("#active-workers").innerText(), "2");
    assert.equal(await page.locator("#crew-live-now [data-stale]").count(), 0);
    await go("revenue", "revenue");
    assert.equal(await page.locator("#revenue").isVisible(), true);
    await fits();
    await go("missions", "details");
    assert.equal(await page.locator("#missions").isVisible(), true);
    assert.equal(
      await page.locator("#toggle-details").getAttribute("aria-expanded"),
      "true",
    );
    await fits();
    await page.close();
    console.log(
      `${width}px V2 navigation, keyboard, freshness, density and states PASS`,
    );
  }
  assert.deepEqual(errors, []);
  assert.deepEqual(writes, []);
  fs.writeFileSync(
    path.join(output, "measurements.json"),
    JSON.stringify(measurements, null, 2),
  );
  await browser.close();
})();
