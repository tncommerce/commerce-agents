import assert from "node:assert/strict";

export async function verifySocialSearchAttribution(browser, baseUrl) {
  for (const width of [390, 1440]) {
    for (const storage of ["available", "denied"]) {
      for (const action of ["click", "enter", "catalog", "direct"]) {
        const context = await browser.newContext({ viewport: { width, height: 900 } });
        const page = await context.newPage();
        const events = [];
        try {
          if (storage === "denied") await context.addInitScript(() => {
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
          await page.route("**/api/session", (route) => route.fulfill({ json: { session_id: "qa-social-attribution", name: "QA Guest" } }));
          await page.route("**/api/analytics/events", (route) => {
            events.push(route.request().postDataJSON());
            return route.fulfill({ json: { ok: true } });
          });
          await page.goto(`${baseUrl}/start?src=instagram&cmp=carousel_qa&content=slide_2`);
          for (let attempt = 0; attempt < 100 && !events.some((event) => event.event === "page_view"); attempt++) await page.waitForTimeout(50);
          assert.ok(events.some((event) => event.event === "page_view"), "wait for landing attribution initialization");
          const input = page.getByRole("searchbox", { name: "Duft oder Marke suchen", exact: true });
          const query = action === "catalog" ? "zzzz-test & parfum" : "Naxos";
          await input.fill(query);
          if (action === "direct") {
            const link = page.getByRole("navigation", { name: "Direkt zu diesen Duftvarianten" }).locator('a[href^="/duft/rabanne-1-million"]');
            await page.waitForFunction(() => document.querySelector('nav[aria-label="Direkt zu diesen Duftvarianten"] a')?.href.includes("cmp=carousel_qa"));
            await link.click();
          } else if (action === "click") {
            const link = page.locator("[data-dufynd-social-live-results]").getByRole("link").first();
            await page.waitForFunction(() => document.querySelector("[data-dufynd-social-live-results] a")?.href.includes("cmp=carousel_qa"));
            await link.click();
          } else {
            await input.press("Enter");
          }
          const path = action === "catalog" ? "/duft" : action === "direct" ? "/duft/rabanne-1-million" : "/duft/xerjoff-naxos";
          await page.waitForURL((url) => url.pathname === path);
          const target = new URL(page.url());
          assert.equal(target.searchParams.get("src"), "instagram", `${action}/${storage}/${width}: source must survive navigation`);
          assert.equal(target.searchParams.get("cmp"), "carousel_qa");
          assert.equal(target.searchParams.get("content"), "slide_2");
          if (action === "catalog") assert.equal(target.searchParams.get("q"), query, "catalog query must remain correctly encoded");
          for (let attempt = 0; attempt < 100 && events.filter((event) => event.event === "page_view").length < 2; attempt++) await page.waitForTimeout(50);
          assert.ok(events.filter((event) => event.event === "page_view").length >= 2, "destination page view must arrive");
          const destination = events.filter((event) => event.event === "page_view").at(-1);
          assert.ok(destination, "destination page view must be recorded");
          assert.equal(destination.acquisition_source, "instagram");
          assert.equal(destination.campaign_id, "carousel_qa");
          assert.equal(destination.content_id, "slide_2");
          assert.notEqual(destination.source, "social_start_instagram", "check the destination rather than the landing event");
        } finally {
          await context.close();
        }
      }
    }
  }
}
