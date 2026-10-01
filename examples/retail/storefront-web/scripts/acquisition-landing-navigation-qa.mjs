import assert from "node:assert/strict";

export async function verifyAcquisitionLandingNavigation(browser, baseUrl) {
  for (const width of [390, 1440]) {
    for (const denied of [false, true]) {
      for (const landing of ["duftfinder", "parfum-alternativen", "parfum-geschenkberater"]) {
        for (const surface of ["catalog", "spotlight"]) {
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
            await page.route("**/api/session", (route) => route.fulfill({ json: { session_id: "qa-acquisition-landing", name: "QA Guest" } }));
            await page.route("**/api/analytics/events", (route) => {
              events.push(route.request().postDataJSON());
              return route.fulfill({ json: { ok: true } });
            });
            await page.goto(`${baseUrl}/${landing}?src=youtube&cmp=landing_qa&content=video_2`);
            await page.waitForFunction(() => [...document.querySelectorAll("a")].filter((link) => !link.closest("footer") && new URL(link.href).origin === location.origin).every((link) => new URL(link.href).searchParams.get("cmp") === "landing_qa"));
            const link = surface === "catalog"
              ? page.getByRole("link", { name: "Katalog entdecken", exact: true })
              : page.locator(".dufynd-acquisition-bottle").first();
            const destination = new URL(await link.getAttribute("href"), baseUrl);
            await link.click();
            await page.waitForURL((url) => url.pathname === destination.pathname);
            const target = new URL(page.url());
            assert.equal(target.searchParams.get("src"), "youtube", `${landing}/${surface}/${width}/${denied}: source must survive`);
            assert.equal(target.searchParams.get("cmp"), "landing_qa");
            assert.equal(target.searchParams.get("content"), "video_2");
            for (let attempt = 0; attempt < 100 && events.filter((event) => event.event === "page_view").length < 2; attempt++) await page.waitForTimeout(50);
            const views = events.filter((event) => event.event === "page_view");
            assert.equal(views.length, 2, "landing and destination must each be recorded");
            for (const event of views) {
              assert.equal(event.acquisition_source, "youtube");
              assert.equal(event.campaign_id, "landing_qa");
              assert.equal(event.content_id, "video_2");
            }
          } finally {
            await context.close();
          }
        }
      }
    }
  }
}
