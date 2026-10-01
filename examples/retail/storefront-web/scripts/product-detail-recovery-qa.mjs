import assert from "node:assert/strict";

// The showcase mounts the same advisor result component without a paid chat call.
export async function verifyProductDetailRecovery(browser, baseUrl) {
  const context = await browser.newContext({ viewport: { width: 390, height: 844 } });
  const page = await context.newPage();
  let mode = "error";
  let requests = 0;
  let lateCompleted = false;
  const recovered = "Produktdetails nach erneutem Laden wieder verfügbar.";
  await page.route("**/api/products/AR-*", async (route) => {
    requests += 1;
    const productId = new URL(route.request().url()).pathname.split("/").pop();
    if (mode === "error") {
      await route.fulfill({ status: 503, body: "unavailable" });
      return;
    }
    const stalled = mode === "stall";
    if (stalled) await new Promise((resolve) => setTimeout(resolve, 9_500));
    try {
      await route.fulfill({
        contentType: "application/json",
        body: JSON.stringify({
          product_id: productId,
          title: "QA product",
          currency: "EUR",
          price: 45,
          long_description: stalled ? "STALE PRODUCT DETAIL RESPONSE" : recovered,
          specs: {},
        }),
      });
    } catch {
      // An aborted request may already have been disposed by the browser.
    } finally {
      if (stalled) lateCompleted = true;
    }
  });
  try {
    const openFirst = async () => {
      await page.goto(`${baseUrl}/showcase`);
      await page.locator('[data-component="products"]')
        .getByRole("button", { name: /Details ansehen/ }).first().click();
    };
    const retry = page.getByRole("button", { name: "Produktdetails erneut laden" });
    const loading = page.getByText("Details werden geladen…", { exact: true }).filter({ visible: true });
    const recoveredText = page.getByText(recovered, { exact: true }).filter({ visible: true });
    await openFirst();
    await retry.waitFor();
    assert.equal(await loading.count(), 0);
    const failedRequests = requests;
    assert.equal(failedRequests, 1, "the hidden desktop panel must not also fetch details");
    mode = "success";
    await retry.click();
    await recoveredText.waitFor();
    assert.equal(requests, failedRequests + 1, "retry must make exactly one new detail request");

    mode = "stall";
    await openFirst();
    await retry.waitFor({ timeout: 10_000 });
    assert.equal(await loading.count(), 0);
    const timedOutRequests = requests;
    mode = "success";
    await retry.click();
    await recoveredText.waitFor();
    const deadline = Date.now() + 5_000;
    while (!lateCompleted && Date.now() < deadline) {
      await new Promise((resolve) => setTimeout(resolve, 100));
    }
    assert.equal(lateCompleted, true, "exercise the late timed-out response");
    assert.equal(await page.getByText("STALE PRODUCT DETAIL RESPONSE", { exact: true }).count(), 0);
    assert.equal(await recoveredText.isVisible(), true);
    assert.equal(requests, timedOutRequests + 1);
  } finally {
    await context.close();
  }
}

export async function verifySingleResponsiveProductDetail(browser, baseUrl) {
  for (const width of [390, 1440]) {
    const context = await browser.newContext({ viewport: { width, height: 900 } });
    const page = await context.newPage();
    let requests = 0;
    const marker = "Responsive product detail loaded.";
    await page.route("**/api/products/AR-*", async (route) => {
      requests += 1;
      await route.fulfill({
        contentType: "application/json",
        body: JSON.stringify({
          product_id: "AR-1401", title: "QA product", currency: "EUR", price: 45,
          long_description: marker, specs: {},
        }),
      });
    });
    try {
      await page.goto(`${baseUrl}/showcase`);
      const products = page.locator('[data-component="products"]');
      if (width === 390) {
        await products.getByRole("button", { name: /Details ansehen/ }).first().click();
      } else {
        await products.getByRole("button", { name: /Stacking Wooden/ }).first().click();
      }
      const visibleDetail = page.getByText(marker, { exact: true }).filter({ visible: true });
      await visibleDetail.waitFor();
      await page.waitForTimeout(300);
      assert.equal(requests, 1, `${width}px: one open must make one request`);
      await page.setViewportSize({ width: width === 390 ? 1440 : 390, height: 900 });
      await visibleDetail.waitFor();
      await page.waitForTimeout(300);
      assert.equal(requests, 2, "a breakpoint change must mount only the newly visible panel");
      assert.equal(await visibleDetail.count(), 1);
      await products.getByRole("button", { name: "Details schließen", exact: true }).click();
      await page.waitForTimeout(300);
      if (width === 390) {
        // The desktop fold retains its child for the closing animation.
        assert.equal(await products.locator(".ac-collapse").getAttribute("aria-hidden"), "true");
      } else {
        assert.equal(await visibleDetail.count(), 0);
      }
      assert.equal(requests, 2, "closing must not load hidden detail panels");
    } finally {
      await context.close();
    }
  }
}
