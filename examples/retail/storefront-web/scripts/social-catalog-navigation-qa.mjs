import assert from "node:assert/strict";

export async function verifySocialCatalogNavigation(browser, baseUrl) {
  for (const width of [390, 1440]) {
    for (const denied of [false, true]) {
      for (const surface of ["grid", "spotlight"]) {
        const context = await browser.newContext({ viewport: { width, height: 900 }, reducedMotion: "reduce" });
        const page = await context.newPage();
        const events = [];
        try {
          if (denied) await context.addInitScript(() => {
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
          });
          await page.route("**/api/session", (route) => route.fulfill({ json: { session_id: "qa-catalog-funnel", name: "QA Guest" } }));
          await page.route("**/api/analytics/events", (route) => {
            events.push(route.request().postDataJSON());
            return route.fulfill({ json: { ok: true } });
          });
          await page.goto(`${baseUrl}/start?src=instagram&cmp=nav_qa&content=slide_3`);
          await page.waitForFunction(() => [...document.querySelectorAll("a")].filter((link) => !link.closest("footer") && new URL(link.href).origin === location.origin).every((link) => new URL(link.href).searchParams.get("cmp") === "nav_qa"));
          await page.getByRole("link", { name: "Katalog entdecken", exact: true }).click();
          await page.waitForURL((url) => url.pathname === "/duft");
          assert.equal(new URL(page.url()).searchParams.get("cmp"), "nav_qa");
          await page.waitForFunction(() => [...document.querySelectorAll("a")].filter((link) => new URL(link.href).origin === location.origin && !link.getAttribute("href")?.startsWith("#")).every((link) => new URL(link.href).searchParams.get("cmp") === "nav_qa"));
          if (surface === "grid") {
            const choices = page.getByRole("button", { name: /für Vergleich auswählen/ });
            await choices.nth(0).click();
            await choices.nth(0).click();
            const compare = page.getByRole("link", { name: "Jetzt vergleichen →", exact: true });
            await compare.waitFor();
            await page.waitForFunction(() => [...document.querySelectorAll("a")].some((link) => link.textContent?.trim() === "Jetzt vergleichen →" && new URL(link.href).searchParams.get("cmp") === "nav_qa"));
            const comparisonUrl = new URL(await compare.getAttribute("href"), baseUrl);
            assert.equal(comparisonUrl.searchParams.get("cmp"), "nav_qa", "comparison link must preserve attribution");
            await page.getByRole("searchbox").fill("Naxos");
          }
          const product = page.locator(surface === "grid" ? "article.dufynd-catalog-card a" : ".dufynd-catalog-discovery-bottle").first();
          await page.waitForFunction((selector) => {
            const link = document.querySelector(selector);
            return link && new URL(link.href).searchParams.get("cmp") === "nav_qa";
          }, surface === "grid" ? "article.dufynd-catalog-card a" : ".dufynd-catalog-discovery-bottle");
          const destination = new URL(await product.getAttribute("href"), baseUrl);
          await product.click();
          await page.waitForURL((url) => url.pathname === destination.pathname);
          const target = new URL(page.url());
          assert.equal(target.searchParams.get("src"), "instagram");
          assert.equal(target.searchParams.get("cmp"), "nav_qa");
          assert.equal(target.searchParams.get("content"), "slide_3");
          for (let attempt = 0; attempt < 100 && events.filter((event) => event.event === "page_view").length < 3; attempt++) await page.waitForTimeout(50);
          const views = events.filter((event) => event.event === "page_view");
          assert.equal(views.length, 3, "landing, catalog and detail must each be recorded");
          for (const event of views) {
            assert.equal(event.acquisition_source, "instagram");
            assert.equal(event.campaign_id, "nav_qa");
            assert.equal(event.content_id, "slide_3");
          }
        } finally {
          await context.close();
        }
      }
    }
  }
}
