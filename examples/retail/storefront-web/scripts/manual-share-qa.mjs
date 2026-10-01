import assert from "node:assert/strict";

export async function verifyManualShareFallback(browser, baseUrl) {
  for (const [mode, width] of [["missing", 390], ["denied", 1440]]) {
    const context = await browser.newContext({ viewport: { width, height: 900 } });
    const page = await context.newPage();
    try {
      await page.addInitScript((mode) => {
        Object.defineProperty(navigator, "share", { value: undefined, configurable: true });
        Object.defineProperty(navigator, "clipboard", {
          value: mode === "missing" ? undefined : { writeText: async () => { throw new DOMException("Denied", "NotAllowedError"); } },
          configurable: true,
        });
      }, mode);
      const query = "src=tiktok&cmp=manual_qa&content=video_02&sid=private_session&sid=another_session";
      const field = page.getByRole("textbox", { name: "Link zum manuellen Kopieren", exact: true });
      const deferClipboard = () => page.evaluate(() => {
        window.clipboardPending = false;
        Object.defineProperty(navigator, "clipboard", {
          value: { writeText: () => new Promise((resolve, reject) => {
            window.clipboardPending = true;
            window.rejectClipboard = reject;
          }) }, configurable: true,
        });
      });
      const denyLate = async () => {
        await page.evaluate(() => window.rejectClipboard(new DOMException("Denied late", "NotAllowedError")));
        await page.waitForTimeout(150);
        assert.equal(await field.count(), 0, "late clipboard failure must not restore a stale selection URL");
      };
      const assertManual = async (pathname, hash) => {
        await field.waitFor();
        const value = await field.inputValue();
        const url = new URL(value);
        assert.equal(url.pathname, pathname);
        assert.equal(url.hash, hash);
        assert.equal(url.searchParams.has("sid"), false);
        assert.equal(url.searchParams.get("src"), "tiktok");
        assert.equal(url.searchParams.get("cmp"), "manual_qa");
        assert.equal(url.searchParams.get("content"), "video_02");
        assert.equal(await field.getAttribute("readonly"), "");
        await field.focus();
        assert.deepEqual(await field.evaluate((input) => [input.selectionStart, input.selectionEnd]), [0, value.length]);
        assert.equal(new URL(page.url()).searchParams.has("sid"), true);
        assert.equal(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth + 1), true,
          "manual URL must not overflow the viewport");
        return url;
      };

      await page.goto(`${baseUrl}/duft/xerjoff-naxos?${query}#angebote`);
      const share = page.getByRole("button", { name: /teilen$/ });
      await share.click();
      await assertManual("/duft/xerjoff-naxos", "#angebote");
      await page.evaluate(() => Object.defineProperty(navigator, "share", {
        value: async () => { throw new DOMException("Cancelled", "AbortError"); }, configurable: true,
      }));
      await share.click();
      await field.waitFor({ state: "hidden" });
      await page.evaluate(() => {
        Object.defineProperty(navigator, "share", { value: undefined, configurable: true });
        Object.defineProperty(navigator, "clipboard", { value: { writeText: async () => {} }, configurable: true });
      });
      await share.click();
      await page.getByRole("status").filter({ hasText: "Link kopiert" }).waitFor();
      assert.equal(await field.count(), 0);

      await page.goto(`${baseUrl}/duft?${query}&q=Naxos&zielgruppe=unisex#katalog`);
      const catalogCopy = page.getByRole("button", { name: "Filterlink kopieren", exact: true });
      await catalogCopy.click();
      const catalog = await assertManual("/duft", "#katalog");
      assert.equal(catalog.searchParams.get("q"), "Naxos");
      assert.equal(catalog.searchParams.get("zielgruppe"), "unisex");
      await page.getByRole("searchbox").fill("Libre");
      await field.waitFor({ state: "hidden" });
      await catalogCopy.click();
      assert.equal((await assertManual("/duft", "#katalog")).searchParams.get("q"), "Libre");
      await deferClipboard();
      await catalogCopy.click();
      await page.waitForFunction(() => window.clipboardPending);
      await page.getByRole("searchbox").fill("Imagination");
      await denyLate();

      await page.goto(`${baseUrl}/vergleich?${query}#vergleich`);
      const left = page.getByRole("combobox", { name: /^Duft 1/ });
      const right = page.getByRole("combobox", { name: /^Duft 2/ });
      await left.selectOption({ index: 1 });
      await right.selectOption({ index: 2 });
      const comparisonCopy = page.getByRole("button", { name: "Vergleichslink kopieren", exact: true });
      await comparisonCopy.click();
      const comparison = await assertManual("/vergleich", "#vergleich");
      assert.equal(comparison.searchParams.get("left"), await left.inputValue());
      assert.equal(comparison.searchParams.get("right"), await right.inputValue());
      await left.selectOption({ index: 3 });
      await field.waitFor({ state: "hidden" });
      await comparisonCopy.click();
      assert.equal((await assertManual("/vergleich", "#vergleich")).searchParams.get("left"), await left.inputValue());
      await deferClipboard();
      await comparisonCopy.click();
      await page.waitForFunction(() => window.clipboardPending);
      await right.selectOption({ index: 4 });
      await denyLate();
    } finally {
      await context.close();
    }
  }
}
