import assert from "node:assert/strict";

export async function verifyLatestProductShare(browser, baseUrl) {
  const scenarios = [
    { surface: "clipboard", oldResult: "reject", latest: "success", status: "Link kopiert" },
    { surface: "clipboard", oldResult: "resolve", latest: "failure", status: "Automatisches Kopieren nicht möglich. Kopiere den Link unten." },
    { surface: "native", oldResult: "reject", latest: "success", status: "Geteilt" },
    { surface: "native", oldResult: "resolve", latest: "cancel", status: "" },
  ];
  for (const width of [390, 1440]) {
    const context = await browser.newContext({ viewport: { width, height: 900 } });
    const page = await context.newPage();
    try {
      for (const scenario of scenarios) {
        await page.goto(`${baseUrl}/duft/xerjoff-naxos?src=tiktok&cmp=share_race&sid=private_session#angebote`);
        await page.evaluate(({ surface, latest }) => {
          window.shareAttempts = 0;
          window.clipboardAttempts = 0;
          const attempt = () => {
            window.shareAttempts += 1;
            if (window.shareAttempts === 1) {
              return new Promise((resolve, reject) => {
                window.resolveOldShare = resolve;
                window.rejectOldShare = reject;
              });
            }
            if (latest === "failure") return Promise.reject(new DOMException("Denied", "NotAllowedError"));
            if (latest === "cancel") return Promise.reject(new DOMException("Cancelled", "AbortError"));
            return Promise.resolve();
          };
          Object.defineProperty(navigator, "share", { value: surface === "native" ? attempt : undefined, configurable: true });
          Object.defineProperty(navigator, "clipboard", {
            value: { writeText: () => { window.clipboardAttempts += 1; return surface === "clipboard" ? attempt() : Promise.resolve(); } },
            configurable: true,
          });
        }, scenario);
        const share = page.getByRole("button", { name: /teilen$/ });
        await share.click();
        await page.waitForFunction(() => window.shareAttempts === 1);
        await share.click();
        await page.waitForFunction(() => window.shareAttempts === 2);
        if (scenario.status) await page.getByRole("status").filter({ hasText: scenario.status }).waitFor();
        await page.evaluate((oldResult) => {
          if (oldResult === "resolve") window.resolveOldShare();
          else window.rejectOldShare(new DOMException("Denied late", "NotAllowedError"));
        }, scenario.oldResult);
        await page.waitForTimeout(150);
        const statuses = (await page.getByRole("status").allTextContents()).map((value) => value.trim());
        if (scenario.status) assert.ok(statuses.includes(scenario.status), "an older share result must not replace the latest status");
        else {
          assert.equal(statuses.includes("Geteilt"), false, "a late success must not undo the latest cancellation");
          assert.equal(statuses.includes("Link kopiert"), false);
        }
        const manual = page.getByRole("textbox", { name: "Link zum manuellen Kopieren", exact: true });
        assert.equal(await manual.count(), scenario.latest === "failure" ? 1 : 0);
        if (scenario.latest === "failure") {
          const url = new URL(await manual.inputValue());
          assert.equal(url.searchParams.has("sid"), false);
          assert.equal(url.searchParams.get("cmp"), "share_race");
          assert.equal(url.hash, "#angebote");
        }
        if (scenario.surface === "native") assert.equal(await page.evaluate(() => window.clipboardAttempts), 0,
          "outdated native failures must not start clipboard fallback");
      }
    } finally {
      await context.close();
    }
  }
}
