import assert from "node:assert/strict";

export async function verifyLibraryNavigationAttribution(browser, baseUrl) {
  let cases = 0;
  const library = { version: 1, owned: ["SC-XERJOFF-NAXOS-100"], wishlist: ["SC-RABANNE-1-MILLION-EDT-100"] };
  for (const width of [390, 1440]) {
    for (const denied of [false, true]) {
      for (const mode of ["sammlung", "merkliste"]) {
        for (const surface of ["summary", "card", "cross", "catalog", "back", "compare"]) {
          const context = await browser.newContext({ viewport: { width, height: 900 }, reducedMotion: "reduce" });
          const page = await context.newPage();
          const events = [];
          try {
            await context.addInitScript(({ library, denied }) => {
              if (!sessionStorage.getItem("qa_library_seeded")) {
                localStorage.setItem("scentai_fragrance_library_v1", JSON.stringify(library));
                sessionStorage.setItem("qa_library_seeded", "1");
              }
              if (!denied) return;
              const get = Storage.prototype.getItem;
              const set = Storage.prototype.setItem;
              Storage.prototype.getItem = function (key) {
                if (key === "dufynd_acquisition_attribution_v1") throw new DOMException("Denied", "SecurityError");
                return get.call(this, key);
              };
              Storage.prototype.setItem = function (key, value) {
                if (key === "dufynd_acquisition_attribution_v1") throw new DOMException("Denied", "SecurityError");
                return set.call(this, key, value);
              };
            }, { library, denied });
            await page.route("**/api/session", (route) => route.fulfill({ json: { session_id: "qa-library-attribution", name: "QA Guest" } }));
            await page.route("**/api/products?**", (route) => route.fulfill({ json: { products: [] } }));
            await page.route("**/api/merchant-partners", (route) => route.fulfill({ json: { partners: [] } }));
            await page.route("**/api/analytics/events", (route) => {
              events.push(route.request().postDataJSON());
              return route.fulfill({ json: { ok: true } });
            });
            const source = mode === "sammlung" ? "collection_page" : "wishlist_page";
            await page.goto(`${baseUrl}/${surface === "summary" ? "" : mode}?src=instagram&cmp=library_qa&content=slide_4`);
            const link = surface === "summary"
              ? page.getByRole("link", { name: mode === "sammlung" ? "Sammlung öffnen" : "Merkliste öffnen", exact: true })
              : surface === "card"
                ? page.locator(".dufynd-library-card a").first()
                : surface === "compare"
                  ? page.locator('.dufynd-library-card a[href*="/vergleich"]').first()
                  : surface === "back"
                    ? page.getByRole("link", { name: "← Zurück zu DUFYND", exact: true })
                    : surface === "catalog"
                      ? page.getByRole("link", { name: "Düfte entdecken", exact: true })
                      : page.getByRole("link", { name: mode === "sammlung" ? "Merkliste (1)" : "Sammlung (1)", exact: true });
            await link.waitFor();
            await page.waitForFunction(() => [...document.querySelectorAll("a")].filter((a) => a.closest(".dufynd-library-page") && !a.closest("footer")).every((a) => new URL(a.href).searchParams.get("cmp") === "library_qa"));
            for (let n = 0; n < 100 && !events.some((e) => e.event === "page_view"); n++) await page.waitForTimeout(50);
            const first = events.find((e) => e.event === "page_view");
            assert.ok(first, "initial page view must arrive");
            assert.equal(first.acquisition_source, "instagram", `${surface}/${mode}/${width}/${denied}: direct library attribution must initialize`);
            assert.equal(first.campaign_id, "library_qa");
            if (surface !== "summary") {
              assert.equal(first.source, source);
              assert.equal(first.surface, "personal_library_page");
            } else {
              await page.waitForFunction((name) => [...document.querySelectorAll("a")].some((a) => a.textContent?.trim() === name && new URL(a.href).searchParams.get("cmp") === "library_qa"), mode === "sammlung" ? "Sammlung öffnen" : "Merkliste öffnen");
            }
            const destination = new URL(await link.getAttribute("href"), baseUrl);
            await link.click();
            await page.waitForURL((u) => u.pathname === destination.pathname);
            const target = new URL(page.url());
            assert.equal(target.searchParams.get("src"), "instagram");
            assert.equal(target.searchParams.get("cmp"), "library_qa");
            assert.equal(target.searchParams.get("content"), "slide_4");
            if (surface === "compare") assert.equal(target.searchParams.get("left"), library[mode === "sammlung" ? "owned" : "wishlist"][0]);
            const expectedViews = surface === "compare" ? 1 : 2;
            for (let n = 0; n < 100 && events.filter((e) => e.event === "page_view").length < expectedViews; n++) await page.waitForTimeout(50);
            const views = events.filter((e) => e.event === "page_view");
            assert.equal(views.length, expectedViews, "existing page-view count must be preserved");
            for (const event of views) {
              assert.equal(event.acquisition_source, "instagram");
              assert.equal(event.campaign_id, "library_qa");
              assert.equal(event.content_id, "slide_4");
            }
            assert.deepEqual(await page.evaluate(() => JSON.parse(localStorage.getItem("scentai_fragrance_library_v1"))), library, "navigation must preserve saved lists");
            cases++;
          } finally {
            await context.close();
          }
        }
      }
    }
  }
  for (const width of [390, 1440]) {
    for (const mode of ["sammlung", "merkliste"]) {
      for (const invalid of ["src=unsupported&cmp=untrusted", "src=instagram&cmp=%3Cunsafe%3E"]) {
        const context = await browser.newContext({ viewport: { width, height: 900 } });
        const page = await context.newPage();
        const events = [];
        try {
          await page.route("**/api/session", (route) => route.fulfill({ json: { session_id: "qa-library-invalid", name: "QA Guest" } }));
          await page.route("**/api/analytics/events", (route) => {
            events.push(route.request().postDataJSON());
            return route.fulfill({ json: { ok: true } });
          });
          await page.goto(`${baseUrl}/${mode}?${invalid}`);
          for (let n = 0; n < 100 && !events.some((e) => e.event === "page_view"); n++) await page.waitForTimeout(50);
          const event = events.find((e) => e.event === "page_view");
          assert.ok(event);
          assert.equal(event.acquisition_source, invalid.startsWith("src=unsupported") ? "unknown" : "instagram");
          assert.equal(event.campaign_id, undefined, "untrusted campaign IDs must not be recorded");
          assert.equal(events.filter((e) => e.event === "page_view").length, 1, "library page view must not duplicate");
          cases++;
        } finally {
          await context.close();
        }
      }
    }
  }
  return cases;
}
