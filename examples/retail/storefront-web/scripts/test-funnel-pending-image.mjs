import assert from "node:assert/strict";
import { chromium } from "playwright";
import { verifyFirstMoneyFunnel } from "./first-money-funnel-qa.mjs";

const baseUrl = process.argv[2] || "http://127.0.0.1:3000";
const browser = await chromium.launch({ headless: true });
let pendingImages = 0;
try {
  const fixtureBrowser = {
    async newContext(options) {
      const context = await browser.newContext(options);
      context.setDefaultNavigationTimeout(5000);
      // Deliberately never complete this local image. No external request or
      // merchant click is made; the context teardown cancels the request.
      await context.route("**/__qa_pending_visual.svg", () => { pendingImages += 1; });
      await context.route("**/duft?*", async (route) => {
        if (!route.request().isNavigationRequest()) return route.continue();
        const response = await route.fetch();
        const html = await response.text();
        return route.fulfill({
          response,
          body: html.replace("</body>", '<img alt="QA pending image" src="/__qa_pending_visual.svg" width="1" height="1"></body>'),
        });
      });
      return context;
    },
  };
  const cases = await verifyFirstMoneyFunnel(fixtureBrowser, baseUrl);
  assert.equal(cases, 4);
  assert.equal(pendingImages, 4, "each funnel must encounter the stalled image fixture");
  console.log(JSON.stringify({ status: "passed", cases, pendingImages, merchantClicks: 0 }));
} finally {
  await browser.close();
}
