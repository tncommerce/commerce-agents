import assert from "node:assert/strict";

export async function verifyGuidedStartContext(browser, baseUrl) {
  const scenarios = [
    { start: "gift", confirmed: true, custom: null },
    { start: "collection", confirmed: true, custom: "Berücksichtige meine ausdrücklich übergebene Duftsammlung." },
    { start: "gift", confirmed: false, custom: null },
  ];
  for (const width of [390, 1440]) {
    for (const scenario of scenarios) {
      const context = await browser.newContext({ viewport: { width, height: 900 } });
      const page = await context.newPage();
      const messages = [];
      let releaseSession;
      const sessionReady = new Promise((resolve) => { releaseSession = resolve; });
      try {
        await context.addInitScript(({ start, confirmed, custom }) => {
          if (confirmed) sessionStorage.setItem("scentai_guided_start_v1", start);
          if (custom) sessionStorage.setItem("scentai_guided_prompt_v1", custom);
        }, scenario);
        await page.route("**/api/session", async (route) => {
          await sessionReady;
          await route.fulfill({ json: { session_id: "qa-guided-context", name: "QA Guest" } }).catch(() => {});
        });
        await page.route("**/api/products?**", (route) => route.fulfill({ json: { products: [] } }));
        await page.route("**/api/memory", (route) => route.fulfill({ json: { facts: [] } }));
        await page.route("**/api/analytics/events", (route) => route.fulfill({ json: { ok: true } }));
        await page.route("**/api/merchant-partners", (route) => route.fulfill({ json: { partners: [] } }));
        await page.route("**/api/chat", (route) => {
          messages.push(route.request().postDataJSON().message);
          return route.fulfill({ status: 200, contentType: "text/event-stream", body: "" });
        });
        await page.goto(`${baseUrl}/?start=${scenario.start}&start=gift&src=tiktok&cmp=guided_qa&content=video_1&sid=private_session&extra=preserve#advisor`);
        await page.evaluate(() => history.replaceState({ ...history.state, qaContext: "preserve" }, "", location.href));
        releaseSession();
        await page.waitForFunction(() => !new URL(location.href).searchParams.has("start"));
        const url = new URL(page.url());
        assert.equal(url.searchParams.get("src"), "tiktok");
        assert.equal(url.searchParams.get("cmp"), "guided_qa");
        assert.equal(url.searchParams.get("content"), "video_1");
        assert.equal(url.searchParams.get("sid"), "private_session");
        assert.equal(url.searchParams.get("extra"), "preserve");
        assert.equal(url.hash, "#advisor");
        assert.equal(await page.evaluate(() => history.state.qaContext), "preserve");
        if (scenario.confirmed) await page.getByText(scenario.custom || /Hilf mir, ein Parfum als Geschenk zu finden/).first().waitFor();
        await page.waitForTimeout(300);
        assert.equal(messages.length, scenario.confirmed ? 1 : 0,
          "URL cleanup must neither bypass confirmation nor send duplicate consultations");
        if (scenario.custom) assert.equal(messages[0], scenario.custom);
        else if (scenario.confirmed) assert.match(messages[0], /Parfum als Geschenk/);
        assert.equal(await page.evaluate(() => sessionStorage.getItem("scentai_guided_start_v1")), null);
        assert.equal(await page.evaluate(() => sessionStorage.getItem("scentai_guided_prompt_v1")), null);
      } finally {
        releaseSession();
        await context.close();
      }
    }
  }
}
