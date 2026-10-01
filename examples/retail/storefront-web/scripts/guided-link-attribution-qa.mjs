import assert from "node:assert/strict";

export async function verifyGuidedLinkAttribution(browser, baseUrl) {
  for (const width of [390, 1440]) {
    for (const storage of ["available", "attribution_denied", "all_denied"]) {
      const context = await browser.newContext({ viewport: { width, height: 900 } });
      const page = await context.newPage();
      const events = [];
      const messages = [];
      try {
        await context.addInitScript(({ storage }) => {
          if (storage === "available") return;
          const get = Storage.prototype.getItem;
          const set = Storage.prototype.setItem;
          const denied = (key) => storage === "all_denied" || key === "dufynd_acquisition_attribution_v1";
          Storage.prototype.getItem = function (key) {
            if (denied(key)) throw new DOMException("Denied", "SecurityError");
            return get.call(this, key);
          };
          Storage.prototype.setItem = function (key, value) {
            if (denied(key)) throw new DOMException("Denied", "SecurityError");
            return set.call(this, key, value);
          };
        }, { storage });
        await page.route("**/api/session", (route) => route.fulfill({ json: { session_id: "qa-guided-handoff", name: "QA Guest" } }));
        await page.route("**/api/products?**", (route) => route.fulfill({ json: { products: [] } }));
        await page.route("**/api/memory", (route) => route.fulfill({ json: { facts: [] } }));
        await page.route("**/api/merchant-partners", (route) => route.fulfill({ json: { partners: [] } }));
        await page.route("**/api/analytics/events", (route) => {
          events.push(route.request().postDataJSON());
          return route.fulfill({ json: { ok: true } });
        });
        await page.route("**/api/chat", (route) => {
          messages.push(route.request().postDataJSON().message);
          return route.fulfill({ status: 200, contentType: "text/event-stream", body: "" });
        });
        await page.goto(`${baseUrl}/parfum-geschenkberater?src=tiktok&cmp=gift_video&content=video_1`);
        const link = page.getByRole("link", { name: "Geschenkberatung starten", exact: true });
        await page.waitForFunction(() => {
          const link = Array.from(document.querySelectorAll("a")).find((element) => element.textContent?.trim() === "Geschenkberatung starten");
          return link && new URL(link.href).searchParams.get("src") === "tiktok";
        });
        const target = new URL(await link.getAttribute("href"), baseUrl);
        assert.equal(target.searchParams.get("start"), "gift");
        assert.equal(target.searchParams.get("cmp"), "gift_video");
        assert.equal(target.searchParams.get("content"), "video_1");
        await link.click();
        await page.waitForURL((url) => url.pathname === "/");
        if (storage !== "all_denied") {
          await page.getByText(/Hilf mir, ein Parfum als Geschenk zu finden/).first().waitFor();
        } else {
          await page.waitForFunction(() => !new URL(location.href).searchParams.has("start"));
        }
        await page.waitForTimeout(300);
        assert.equal(messages.length, storage === "all_denied" ? 0 : 1,
          "attribution handoff must preserve the existing storage-based confirmation gate");
        const homeView = events.find((event) => event.event === "page_view" && event.source === "storefront");
        assert.ok(homeView, "the destination page view must be recorded");
        const consultation = events.find((event) => event.event === "consultation_start");
        if (storage !== "all_denied") assert.ok(consultation);
        for (const event of [homeView, consultation].filter(Boolean)) {
          assert.equal(event.acquisition_source, "tiktok");
          assert.equal(event.campaign_id, "gift_video");
          assert.equal(event.content_id, "video_1");
        }
        assert.equal(new URL(page.url()).searchParams.get("cmp"), "gift_video");
      } finally {
        await context.close();
      }
    }
  }
}
