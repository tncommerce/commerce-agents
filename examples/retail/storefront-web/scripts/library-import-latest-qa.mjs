import assert from "node:assert/strict";

export async function verifyLatestLibraryImport(browser, baseUrl) {
  const older = { version: 1, wishlist: ["SC-XERJOFF-NAXOS-100"], owned: [] };
  const latest = { version: 1, wishlist: [], owned: ["SC-XERJOFF-NAXOS-100"] };
  const scenarios = [
    { oldResult: "valid", phase: "after", latestResult: "success" },
    { oldResult: "invalid", phase: "after", latestResult: "success" },
    { oldResult: "reject", phase: "after", latestResult: "success" },
    { oldResult: "valid", phase: "before", latestResult: "success" },
    { oldResult: "valid", phase: "after", latestResult: "invalid" },
    { oldResult: "valid", phase: "after", latestResult: "cancel" },
  ];
  for (const width of [390, 1440]) {
    const context = await browser.newContext({ viewport: { width, height: 900 } });
    const page = await context.newPage();
    try {
      for (const scenario of scenarios) {
        await page.goto(`${baseUrl}/merkliste`);
        await page.getByRole("button", { name: "Sicherung importieren", exact: true }).waitFor();
        await page.evaluate(({ latestResult, older }) => {
          if (latestResult === "cancel") localStorage.setItem("scentai_fragrance_library_v1", JSON.stringify(older));
          else localStorage.removeItem("scentai_fragrance_library_v1");
          dispatchEvent(new CustomEvent("scentai:fragrance-library-changed"));
          window.importReads = [];
          window.confirmCalls = 0;
          window.importWrites = 0;
          window.confirm = () => { window.confirmCalls += 1; return latestResult !== "cancel"; };
          addEventListener("scentai:fragrance-library-changed", () => { window.importWrites += 1; });
          File.prototype.text = function () {
            return new Promise((resolve, reject) => { window.importReads.push({ resolve, reject }); });
          };
        }, { ...scenario, older });
        const input = page.locator('input[type="file"]');
        for (const name of ["older.json", "latest.json"]) {
          await input.setInputFiles({ name, mimeType: "application/json", buffer: Buffer.from("{}") });
        }
        await page.waitForFunction(() => window.importReads.length === 2);
        const finishOlder = () => page.evaluate(({ oldResult, older }) => {
          if (oldResult === "reject") window.importReads[0].reject(new Error("Read failed"));
          else window.importReads[0].resolve(oldResult === "invalid" ? "{" : JSON.stringify(older));
        }, { ...scenario, older });
        if (scenario.phase === "before") {
          await finishOlder();
          await page.waitForTimeout(150);
          assert.equal(await input.evaluate((element) => element.files?.[0]?.name), "latest.json",
            "an outdated read must not clear the newer pending selection");
          assert.equal(await page.evaluate(() => window.importWrites), 0);
        }
        await page.evaluate(({ latestResult, latest }) => {
          window.importReads[1].resolve(latestResult === "invalid" ? "{" : JSON.stringify(latest));
        }, { ...scenario, latest });
        const status = scenario.latestResult === "success"
          ? "Sicherung geladen: 0 gemerkt, 1 in Sammlung."
          : scenario.latestResult === "cancel"
            ? "Import abgebrochen. Deine aktuelle Auswahl bleibt erhalten."
            : "Import fehlgeschlagen. Bitte wähle eine gültige DUFYND-Sicherungsdatei.";
        await page.getByText(status, { exact: true }).waitFor();
        if (scenario.phase === "after") await finishOlder();
        await page.waitForTimeout(150);
        assert.ok((await page.getByRole("status").allTextContents()).includes(status),
          "an outdated success or failure must not replace the latest import status");
        assert.deepEqual(await page.evaluate(() => JSON.parse(localStorage.getItem("scentai_fragrance_library_v1"))),
          scenario.latestResult === "success" ? latest : scenario.latestResult === "cancel" ? older : null);
        assert.equal(await page.evaluate(() => window.confirmCalls), scenario.latestResult === "cancel" ? 1 : 0,
          "outdated reads must not ask for replacement confirmation");
        assert.equal(await page.evaluate(() => window.importWrites), scenario.latestResult === "success" ? 1 : 0);
        assert.equal(await input.inputValue(), "");
      }
    } finally {
      await context.close();
    }
  }
}
