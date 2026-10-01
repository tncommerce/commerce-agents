import assert from "node:assert/strict";

export async function verifyLibraryReadFeedback(browser, baseUrl) {
  const key = "scentai_fragrance_library_v1";
  const saved = { version: 1, owned: ["SC-XERJOFF-NAXOS-100"], wishlist: ["SC-RABANNE-1-MILLION-EDT-100"] };
  const message = "Deine Duftliste konnte nicht gelesen werden. Deine gespeicherte Auswahl wurde nicht geändert.";
  let cases = 0;
  for (const width of [390, 1440]) {
    for (const mode of ["sammlung", "merkliste"]) {
      for (const failure of ["denied", "invalid-json"]) {
        for (const timing of ["initial", "custom-event", "storage-event"]) {
          const context = await browser.newContext({ viewport: { width, height: 900 } });
          const page = await context.newPage();
          try {
            await context.addInitScript(({ key, saved, failure, timing }) => {
              localStorage.setItem(key, JSON.stringify(saved));
              window.qaFeedbackGet = Storage.prototype.getItem;
              window.qaFeedbackFailure = timing === "initial";
              window.qaFeedbackWrites = 0;
              const set = Storage.prototype.setItem;
              Storage.prototype.setItem = function (k, v) { if (k === key) window.qaFeedbackWrites++; return set.call(this, k, v); };
              Storage.prototype.getItem = function (k) {
                if (k === key && window.qaFeedbackFailure) {
                  if (failure === "invalid-json") return "{invalid";
                  throw new DOMException("Denied", "SecurityError");
                }
                return window.qaFeedbackGet.call(this, k);
              };
            }, { key, saved, failure, timing });
            await page.route("**/api/session", r => r.fulfill({ json: { session_id: "qa-read-feedback", name: "QA" } }));
            const events = [];
            await page.route("**/api/analytics/events", r => { events.push(r.request().postDataJSON()); return r.fulfill({ json: { ok: true } }); });
            await page.goto(`${baseUrl}/${mode}`);
            let buttons;
            if (timing !== "initial") {
              await page.locator(".dufynd-library-card").waitFor();
              await page.waitForFunction(() => [...document.querySelectorAll('.dufynd-library-card button[aria-pressed]')].some(b => b.getAttribute('aria-pressed') === 'true'));
              buttons = await page.locator(".dufynd-library-card button[aria-pressed]").evaluateAll(bs => bs.map(b => b.getAttribute("aria-pressed")));
              await page.evaluate(({ key, timing }) => {
                window.qaFeedbackFailure = true;
                window.dispatchEvent(timing === "storage-event" ? new StorageEvent("storage", { key }) : new CustomEvent("scentai:fragrance-library-changed"));
              }, { key, timing });
            }
            await page.getByRole("alert").getByText(message, { exact: true }).waitFor();
            assert.equal(await page.getByText(mode === "sammlung" ? "Deine Sammlung ist noch leer" : "Noch nichts gemerkt", { exact: true }).count(), 0, "unreadable data must not claim an empty list");
            assert.equal(await page.locator(".dufynd-library-card").count(), timing === "initial" ? 0 : 1, "failed sync preserves known cards");
            if (buttons) assert.deepEqual(await page.locator(".dufynd-library-card button[aria-pressed]").evaluateAll(bs => bs.map(b => b.getAttribute("aria-pressed"))), buttons, "failed sync preserves known save states");
            const retry = page.getByRole("button", { name: "Duftliste erneut laden", exact: true });
            await retry.click();
            await page.getByRole("alert").getByText(message, { exact: true }).waitFor();
            await page.evaluate(() => { window.qaFeedbackFailure = false; });
            await retry.click();
            await page.getByRole("alert").filter({ hasText: message }).waitFor({ state: "detached" });
            await page.locator(".dufynd-library-card").waitFor();
            await page.waitForFunction(() => [...document.querySelectorAll('.dufynd-library-card button[aria-pressed]')].some(b => b.getAttribute('aria-pressed') === 'true'));
            assert.deepEqual(await page.evaluate(key => JSON.parse(localStorage.getItem(key)), key), saved);
            assert.equal(await page.evaluate(() => window.qaFeedbackWrites), 0, "read failure and retries never write storage");
            assert.equal(events.filter(e => /^(collection|wishlist)_/.test(e.event)).length, 0, "read/retry emits no collection mutation events");
            assert.equal(await page.getByText("Deine Duftliste konnte nicht gelesen werden. Bitte versuche es erneut.", { exact: true }).count(), 0, "successful retry clears save-control read errors");
            await page.evaluate(key => { localStorage.removeItem(key); window.dispatchEvent(new StorageEvent("storage", { key })); }, key);
            await page.getByText(mode === "sammlung" ? "Deine Sammlung ist noch leer" : "Noch nichts gemerkt", { exact: true }).waitFor();
            assert.equal(await page.locator(".dufynd-library-card").count(), 0, "a successful empty read still clears the view");
            cases++;
          } finally { await context.close(); }
        }
      }
    }
  }
  return cases;
}
