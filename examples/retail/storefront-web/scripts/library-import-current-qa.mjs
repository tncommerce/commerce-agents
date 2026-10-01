import assert from "node:assert/strict";

export async function verifyCurrentLibraryImport(browser, baseUrl) {
  const saved = { version: 1, wishlist: ["SC-XERJOFF-NAXOS-100"], owned: [] };
  const backup = { version: 1, wishlist: [], owned: ["SC-XERJOFF-NAXOS-100"] };
  const scenarios = [
    { initiallySaved: false, currentlySaved: true, allowReplacement: false, confirmations: 1 },
    { initiallySaved: false, currentlySaved: true, allowReplacement: true, confirmations: 1 },
    { initiallySaved: true, currentlySaved: false, allowReplacement: false, confirmations: 0 },
  ];
  for (const width of [390, 1440]) {
    const context = await browser.newContext({ viewport: { width, height: 900 } });
    const page = await context.newPage();
    const otherTab = await context.newPage();
    const route = width === 390 ? "/merkliste" : "/sammlung";
    try {
      await otherTab.goto(`${baseUrl}${route}`);
      for (const scenario of scenarios) {
        await otherTab.evaluate(({ initiallySaved, saved }) => {
          if (initiallySaved) localStorage.setItem("scentai_fragrance_library_v1", JSON.stringify(saved));
          else localStorage.removeItem("scentai_fragrance_library_v1");
        }, { ...scenario, saved });
        await page.goto(`${baseUrl}${route}`);
        await page.getByRole("button", { name: "Sicherung importieren", exact: true }).waitFor();
        await page.evaluate(({ allowReplacement }) => {
          window.confirmCalls = 0;
          window.confirm = () => { window.confirmCalls += 1; return allowReplacement; };
          window.importReadStarted = false;
          File.prototype.text = function () {
            window.importReadStarted = true;
            return new Promise((resolve) => { window.finishImportRead = resolve; });
          };
        }, scenario);
        await page.locator('input[type="file"]').setInputFiles({
          name: "dufynd-backup.json", mimeType: "application/json", buffer: Buffer.from(JSON.stringify(backup)),
        });
        await page.waitForFunction(() => window.importReadStarted);
        await otherTab.evaluate(({ currentlySaved, saved }) => {
          if (currentlySaved) localStorage.setItem("scentai_fragrance_library_v1", JSON.stringify(saved));
          else localStorage.removeItem("scentai_fragrance_library_v1");
        }, { ...scenario, saved });
        await page.getByText(`${scenario.currentlySaved ? 1 : 0} auf Merkliste`, { exact: true }).waitFor();
        await page.evaluate((backup) => window.finishImportRead(JSON.stringify(backup)), backup);
        const cancelled = scenario.currentlySaved && !scenario.allowReplacement;
        await page.getByText(cancelled
          ? "Import abgebrochen. Deine aktuelle Auswahl bleibt erhalten."
          : "Sicherung geladen: 0 gemerkt, 1 in Sammlung.", { exact: true }).waitFor();
        assert.equal(await page.evaluate(() => window.confirmCalls), scenario.confirmations,
          "replacement confirmation must use the library present after the file read");
        assert.deepEqual(await page.evaluate(() => JSON.parse(localStorage.getItem("scentai_fragrance_library_v1"))),
          cancelled ? saved : backup, "cancellation must retain the newly saved list; acceptance restores the backup");
        assert.equal(await page.locator('input[type="file"]').inputValue(), "", "the same file can be selected again");
      }
    } finally {
      await context.close();
    }
  }
}
