import assert from "node:assert/strict";

export async function verifyHomeNavigationAttribution(browser, baseUrl) {
  let cases = 0;
  for (const width of [390, 1440]) {
    for (const denied of [false, true]) {
      for (const surface of ["finder", "spotlight", "audience", "profile", "comparison", "selected", "search-enter", "search-button"]) {
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
          await page.route("**/api/session", (route) => route.fulfill({ json: { session_id: "qa-home-navigation", name: "QA Guest" } }));
          await page.route("**/api/products?**", (route) => route.fulfill({ json: { products: [] } }));
          await page.route("**/api/merchant-partners", (route) => route.fulfill({ json: { partners: [] } }));
          await page.route("**/api/analytics/events", (route) => {
            events.push(route.request().postDataJSON());
            return route.fulfill({ json: { ok: true } });
          });
          await page.goto(`${baseUrl}/?src=youtube&cmp=home_qa&content=video_3`);
          await page.waitForFunction(() => {
            const link = document.querySelector("a.dufynd-hero-primary");
            return link && new URL(link.href).searchParams.get("cmp") === "home_qa";
          });
          await page.waitForFunction(() => document.querySelector("#dufynd-home-search"));
          for (let attempt = 0; attempt < 100 && !events.some((event) => event.event === "page_view"); attempt++) await page.waitForTimeout(50);
          assert.ok(events.some((event) => event.event === "page_view"), "home page view must arrive");
          let path;
          if (surface.startsWith("search-")) {
            const input = page.getByRole("searchbox", { name: "Duft oder Marke suchen", exact: true });
            await input.fill("Naxos & Vanille + Duft");
            if (surface === "search-enter") await input.press("Enter");
            else await page.getByRole("button", { name: "Suchen", exact: true }).click();
            path = "/duft";
          } else if (surface === "selected") {
            const card = page.locator(".dufynd-home-selected-card [role=button]:visible").first();
            await card.focus();
            await card.press("Enter");
          } else {
            const selectors = {
              finder: "a.dufynd-hero-primary",
              spotlight: "a.dufynd-hero-product",
              audience: "a[data-dufynd-home-audience-card]",
              profile: "nav[aria-label='Duftwelten im Katalog'] a",
              comparison: "a[href*='/vergleich']",
            };
            const link = page.locator(selectors[surface]).first();
            path = new URL(await link.getAttribute("href"), baseUrl).pathname;
            await link.click();
          }
          await page.waitForURL((url) => path ? url.pathname === path : url.pathname.startsWith("/duft/"));
          const target = new URL(page.url());
          assert.equal(target.searchParams.get("src"), "youtube", `${surface}/${width}/${denied}: source must survive`);
          assert.equal(target.searchParams.get("cmp"), "home_qa");
          assert.equal(target.searchParams.get("content"), "video_3");
          if (surface.startsWith("search-")) assert.equal(target.searchParams.get("q"), "Naxos & Vanille + Duft", "form query encoding must survive");
          if (surface === "audience") assert.equal(target.searchParams.get("zielgruppe"), "women");
          if (surface === "profile") assert.equal(target.searchParams.get("profil"), "freshness");
          const expectedViews = surface === "comparison" ? 1 : 2;
          for (let attempt = 0; attempt < 100 && events.filter((event) => event.event === "page_view").length < expectedViews; attempt++) await page.waitForTimeout(50);
          const views = events.filter((event) => event.event === "page_view");
          assert.equal(views.length, expectedViews, `${surface}/${width}/${denied}: existing page-view behavior must be preserved`);
          for (const event of views) {
            assert.equal(event.acquisition_source, "youtube");
            assert.equal(event.campaign_id, "home_qa");
            assert.equal(event.content_id, "video_3");
          }
          cases++;
        } finally {
          await context.close();
        }
      }
    }
  }
  return cases;
}
