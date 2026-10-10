import assert from "node:assert/strict";

export async function verifyNoteSculpture(browser, baseUrl, outputDir) {
  let cases = 0;
  for (const scenario of [
    "reduced-motion",
    "no-webgl",
    "low-memory",
    "software-webgl",
  ]) {
    const context = await browser.newContext({
      viewport: { width: 390, height: 844 },
      reducedMotion: scenario === "reduced-motion" ? "reduce" : "no-preference",
    });
    await context.route("**/api/**", (route) => route.fulfill({ json: {} }));
    await context.route("**/api/session", (route) =>
      route.fulfill({ json: { session_id: "qa-notes" } }),
    );
    await context.route("**/api/merchant-offers/**", (route) =>
      route.fulfill({ json: { offers: [], best_offer_id: null } }),
    );
    await context.addInitScript((scenario) => {
      Object.defineProperty(navigator, "hardwareConcurrency", { get: () => 8 });
      Object.defineProperty(navigator, "deviceMemory", {
        get: () => (scenario === "low-memory" ? 2 : 8),
      });
      window.__noteDraws = 0;
      const get = HTMLCanvasElement.prototype.getContext;
      HTMLCanvasElement.prototype.getContext = function (kind, options) {
        if (kind === "webgl") {
          if (scenario === "no-webgl") return null;
          // CI's software GPU exercises shaders; production still rejects major performance caveats.
          return get.call(this, kind, {
            ...options,
            preserveDrawingBuffer: true,
            failIfMajorPerformanceCaveat: false,
          });
        }
        return get.call(this, kind, options);
      };
      const draw = WebGLRenderingContext.prototype.drawArrays;
      WebGLRenderingContext.prototype.drawArrays = function (...args) {
        window.__noteDraws++;
        return draw.apply(this, args);
      };
    }, scenario);
    const page = await context.newPage();
    try {
      await page.goto(`${baseUrl}/duft/xerjoff-naxos?qa=1`);
      const studio = page.locator("[data-note-sculpture]");
      const heart = studio.getByRole("button", { name: "Herz", exact: true });
      await heart.click();
      assert.equal(await heart.getAttribute("aria-pressed"), "true");
      assert.ok(
        await studio.locator("li").count(),
        "all modes retain actual note content",
      );
      const open = studio.getByRole("button", { name: "Raumansicht öffnen" });
      if (["reduced-motion", "low-memory"].includes(scenario)) {
        assert.equal(await open.count(), 0);
        assert.equal(await studio.locator("canvas").count(), 0);
      } else {
        await open.click();
        if (scenario === "no-webgl") {
          await studio
            .getByText("Statische Ansicht · 3D nicht verfügbar")
            .waitFor();
          assert.equal(await studio.locator("canvas").count(), 0);
        } else {
          await page.waitForFunction(() => window.__noteDraws > 0);
          const canvas = studio.locator("canvas");
          const before = await canvas.evaluate((element) =>
            element.toDataURL(),
          );
          await studio
            .getByRole("button", { name: "Noten nach rechts drehen" })
            .click();
          await page.waitForFunction(
            (before) =>
              document
                .querySelector("[data-note-sculpture] canvas")
                .toDataURL() !== before,
            before,
          );
          const draws = await page.evaluate(() => window.__noteDraws);
          await page.waitForTimeout(250);
          assert.equal(
            await page.evaluate(() => window.__noteDraws),
            draws,
            "no idle animation loop",
          );
          assert.equal(
            await canvas.evaluate(
              (element) => getComputedStyle(element).touchAction,
            ),
            "pan-y",
          );
          if (outputDir) {
            await page.setViewportSize({ width: 390, height: 1100 });
            await studio.evaluate((element) => element.scrollIntoView({ block: "center" }));
            await studio.screenshot({ path: `${outputDir}/note-sculpture-390.png` });
            await page.setViewportSize({ width: 390, height: 844 });
          }
          await canvas.evaluate((element) =>
            element.dispatchEvent(
              new Event("webglcontextlost", { cancelable: true }),
            ),
          );
          await studio
            .getByText("Statische Ansicht · 3D nicht verfügbar")
            .waitFor();
          assert.equal(
            await studio.locator("canvas").count(),
            0,
            "context loss keeps the notes usable",
          );
          await page.reload();
          await studio
            .getByRole("button", { name: "Raumansicht öffnen" })
            .click();
          await page.waitForFunction(() => window.__noteDraws > 0);
          await page.emulateMedia({ reducedMotion: "reduce" });
          await page.waitForFunction(
            () =>
              document.querySelector("[data-note-sculpture]").dataset
                .noteView === "static",
          );
          assert.equal(await studio.locator("canvas").count(), 0);
        }
      }
      assert.equal(
        await page.evaluate(
          () => document.documentElement.scrollWidth > innerWidth,
        ),
        false,
      );
      if (scenario === "reduced-motion") {
        await page.goto(`${baseUrl}/duft/yves-saint-laurent-libre?qa=1`);
        await page
          .locator("[data-note-sculpture]")
          .getByRole("button", { name: "Schlüsselnoten", exact: true })
          .waitFor();
        assert.equal(
          await page
            .locator("[data-note-sculpture]")
            .getByRole("button", { name: "Herz", exact: true })
            .count(),
          0,
          "do not infer a pyramid from key notes",
        );
      }
      cases++;
    } finally {
      await context.close();
    }
  }
  return cases;
}
