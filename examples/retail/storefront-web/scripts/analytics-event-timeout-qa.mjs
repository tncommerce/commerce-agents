import assert from "node:assert/strict";

async function waitFor(predicate, timeout = 12_000) {
  const deadline = Date.now() + timeout;
  while (!predicate()) {
    if (Date.now() >= deadline) throw new Error("analytics event queue did not recover from a stalled POST");
    await new Promise((resolve) => setTimeout(resolve, 50));
  }
}

export async function verifyAnalyticsEventTimeout(browser, baseUrl) {
  for (const advisor of [false, true]) {
    const context = await browser.newContext({ viewport: { width: 390, height: 844 } });
    const page = await context.newPage();
    const posts = [];
    let sessions = 0;
    let aborted = 0;
    let release;
    const stalled = new Promise((resolve) => { release = resolve; });
    try {
      page.on("requestfailed", (request) => {
        if (request.url().endsWith("/api/analytics/events")) aborted += 1;
      });
      await page.route("**/api/session", (route) => {
        sessions += 1;
        return route.fulfill({ json: { session_id: `qa-event-${advisor ? "advisor" : "analytics"}-${sessions}`, name: "QA Guest" } });
      });
      await page.route("**/api/products?**", (route) => route.fulfill({ json: { products: [] } }));
      await page.route("**/api/analytics/events", async (route) => {
        posts.push({ payload: route.request().postDataJSON(), session: route.request().headers()["x-session-id"] });
        if (posts.length === 1) await stalled;
        await route.fulfill({ json: { ok: true } }).catch(() => {});
      });
      await page.goto(`${baseUrl}/${advisor ? "" : "duft/xerjoff-naxos"}?src=tiktok&cmp=event_qa&content=event_video`);
      await waitFor(() => posts.length === 1);
      assert.equal(sessions, 1);
      if (advisor) {
        // Keep navigation in this context while exercising the real spotlight click handler.
        await page.evaluate(() => document.addEventListener("click", (event) => {
          if (event.target instanceof Element && event.target.closest("a")) event.preventDefault();
        }));
        await page.getByRole("link", { name: /entdecken$/ }).first().click();
      } else {
        await page.getByRole("button", { name: "♡ Merken", exact: true }).click();
        assert.equal(await page.getByRole("button", { name: "✓ Gemerkt", exact: true }).getAttribute("aria-pressed"), "true",
          "stalled analytics must not block saving a fragrance");
      }
      const queuedEvent = advisor ? "product_open" : "wishlist_add";
      await waitFor(() => posts.some((post) => post.payload.event === queuedEvent));
      assert.equal(aborted, 1, "the stalled POST must be aborted");
      assert.equal(sessions, advisor ? 1 : 2,
        "only an analytics-owned session may be renewed by the existing retry policy");
      assert.equal(posts.filter((post) => post.payload.event === "page_view").length, advisor ? 1 : 2);
      const queued = posts.find((post) => post.payload.event === queuedEvent);
      assert.equal(queued.session, `qa-event-${advisor ? "advisor-1" : "analytics-2"}`);
      assert.equal(queued.payload.acquisition_source, "tiktok");
      assert.equal(queued.payload.campaign_id, "event_qa");
      assert.equal(queued.payload.content_id, "event_video");
      assert.ok(queued.payload.product_id);
      const count = posts.length;
      release();
      await page.waitForTimeout(600);
      assert.equal(posts.length, count, "a late aborted response must not restart or duplicate queued events");
      assert.equal(sessions, advisor ? 1 : 2);
    } finally {
      release();
      await context.close();
    }
  }
}
