import assert from "node:assert/strict";
import path from "node:path";

/**
 * Native Playwright QA for the new zero-cost DUFYND Duft-Duell experience.
 * The page is a standalone browser experience; this checks genuine clicks
 * against the built Next.js route, not synthetic screenshots or mocks.
 */
export async function verifyDuftduell(browser, baseUrl, outputDir) {
  const cases = [];
  for (const viewport of [
    { width: 320, height: 780 },
    { width: 390, height: 844 },
    { width: 1440, height: 900 },
  ]) {
    const context = await browser.newContext({ viewport, reducedMotion: "reduce" });
    const page = await context.newPage();
    const errors = [];
    page.on("pageerror", (error) => errors.push(String(error)));
    try {
      const url = `${baseUrl}/duftduell?qa=1&src=instagram&cmp=duftduell_qa&content=profile`;
      const response = await page.goto(url, { waitUntil: "domcontentloaded" });
      assert.ok(response?.ok(), `Duft-Duell page reachable at ${viewport.width}: HTTP ${response?.status() ?? "no-response"} ${response?.url() ?? url}`);
      await page.getByRole("heading", { name: /DUFT.*DUELL/i }).waitFor();
      await page.screenshot({ path: path.join(outputDir, `duftduell-${viewport.width}-intro.png`), fullPage: true });
      assert.equal(await page.locator(".duel-choice").count(), 0, "No premature choices before start");
      await page.getByRole("button", { name: /DUELL STARTEN/i }).click();
      await page.locator(".duel-choice").first().waitFor();
      assert.equal(await page.locator(".duel-choice").count(), 2, "Two options per round");
      await page.screenshot({ path: path.join(outputDir, `duftduell-${viewport.width}-choice.png`), fullPage: true });
      for (const choice of ["a", "a", "b", "b"]) {
        await page.locator(`.duel-choice-${choice}`).click();
      }
      const result = page.locator(".duel-result");
      await result.waitFor();
      assert.ok((await result.innerText()).includes("The Clean Edit"), "Predictable exact style outcome");
      const finder = page.locator(".duel-cta-primary");
      await finder.waitFor();
      await page.waitForFunction(() => {
        const a = document.querySelector(".duel-cta-primary");
        if (!a) return false;
        const url = new URL(a.href);
        return url.searchParams.get("start") === "signature" && url.searchParams.get("src") === "instagram";
      }, null, { timeout: 7000 });
      const attributedLink = await finder.getAttribute("href");
      const link = new URL(attributedLink, baseUrl);
      assert.equal(link.pathname, "/", "Existing guided advisor route");
      assert.equal(link.searchParams.get("qa"), "1", "QA marker preserved across handoff");
      await page.screenshot({ path: path.join(outputDir, `duftduell-${viewport.width}-result.png`), fullPage: true });
      const dimensions = await page.evaluate(() => ({
        documentWidth: document.documentElement.scrollWidth,
        viewportWidth: document.documentElement.clientWidth,
      }));
      assert.ok(
        dimensions.documentWidth <= dimensions.viewportWidth + 1,
        `Horizontal overflow: ${viewport.width}px => ${dimensions.documentWidth}`,
      );
      assert.deepEqual(errors, [], `No client-side JavaScript errors at ${viewport.width}px`);
      cases.push({ width: viewport.width, route: "/duftduell", outcome: "clean", advisor: true, overflow: false });
    } finally {
      await context.close();
    }
  }
  return cases;
}
