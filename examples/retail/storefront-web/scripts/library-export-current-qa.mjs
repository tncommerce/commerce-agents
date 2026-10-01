import assert from "node:assert/strict";

export async function verifyLibraryExportCurrent(browser, baseUrl) {
  const key = "scentai_fragrance_library_v1";
  const initial = { version: 1, owned: ["SC-XERJOFF-NAXOS-100"], wishlist: ["SC-RABANNE-1-MILLION-EDT-100"] };
  const latest = { version: 1, owned: ["SC-RABANNE-1-MILLION-EDT-100"], wishlist: [] };
  const empty = { version: 1, owned: [], wishlist: [] };
  let cases = 0;
  for (const width of [390, 1440]) {
    for (const mode of ["sammlung", "merkliste"]) {
      for (const scenario of ["changed", "cleared", "denied", "invalid-json"]) {
        const context = await browser.newContext({ viewport: { width, height: 900 } });
        const page = await context.newPage();
        try {
          await context.addInitScript(({ key, initial }) => localStorage.setItem(key, JSON.stringify(initial)), { key, initial });
          await page.route("**/api/session", r => r.fulfill({ json: { session_id: "qa-export-current", name: "QA" } }));
          await page.route("**/api/analytics/events", r => r.fulfill({ json: { ok: true } }));
          await page.goto(`${baseUrl}/${mode}`);
          const button = page.getByRole("button", { name: "Duftliste sichern", exact: true });
          await button.waitFor();
          await page.evaluate(({ key, latest, scenario }) => {
            if (scenario === "changed") localStorage.setItem(key, JSON.stringify(latest));
            if (scenario === "cleared") localStorage.removeItem(key);
            window.qaExportGet = Storage.prototype.getItem;
            Storage.prototype.getItem = function (k) {
              if (k === key && scenario === "denied") throw new DOMException("Denied", "SecurityError");
              if (k === key && scenario === "invalid-json") return "{invalid";
              return window.qaExportGet.call(this, k);
            };
            window.qaExportBlobs = [];
            URL.createObjectURL = blob => { window.qaExportBlobs.push(blob); return "blob:qa-export-current"; };
            URL.revokeObjectURL = () => {};
            HTMLAnchorElement.prototype.click = function () {};
          }, { key, latest, scenario });
          await button.click();
          if (scenario === "denied" || scenario === "invalid-json") {
            await page.getByRole("status").getByText("Sicherung fehlgeschlagen. Deine Duftliste konnte nicht gelesen werden. Bitte versuche es erneut.", { exact: true }).waitFor();
            assert.equal(await page.evaluate(() => window.qaExportBlobs.length), 0, "failed read must not download cached or empty data");
            assert.deepEqual(await page.evaluate(key => JSON.parse(window.qaExportGet.call(localStorage, key)), key), initial, "failed export leaves saved lists unchanged");
            await page.evaluate(() => { Storage.prototype.getItem = window.qaExportGet; });
            await button.click();
          }
          await page.getByText("Sicherung heruntergeladen. Bewahre die Datei selbst sicher auf.", { exact: true }).waitFor();
          assert.equal(await page.evaluate(() => window.qaExportBlobs.length), 1, "one export after success or retry");
          const exported = await page.evaluate(async () => JSON.parse(await window.qaExportBlobs[0].text()));
          assert.deepEqual(exported, scenario === "changed" ? latest : scenario === "cleared" ? empty : initial, "backup reflects current persisted data");
          assert.equal(await page.evaluate(key => window.qaExportGet.call(localStorage, key), key), scenario === "cleared" ? null : JSON.stringify(scenario === "changed" ? latest : initial), "export does not write storage");
          cases++;
        } finally {
          await context.close();
        }
      }
    }
  }
  return cases;
}
