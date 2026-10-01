import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";

function assertAttribution(url, label) {
  assert.equal(url.searchParams.get("src"), "youtube", `${label}: source must survive`);
  assert.equal(url.searchParams.get("cmp"), "missing_qa", `${label}: campaign must survive`);
  assert.equal(url.searchParams.get("content"), "video_1", `${label}: content must survive`);
}

export async function verifyErrorRecoveryNavigationAttribution(browser, baseUrl) {
  let cases = 0;
  const targets = [
    { name: "Duftkatalog öffnen", path: "/duft" },
    { name: "Zur Duftberatung", path: "/" },
  ];

  for (const width of [390, 1440]) {
    for (const denied of [false, true]) {
      for (const target of targets) {
        const context = await browser.newContext({
          viewport: { width, height: 900 },
          reducedMotion: "reduce",
        });
        const page = await context.newPage();
        const events = [];
        try {
          if (denied) {
            await context.addInitScript(() => {
              const get = Storage.prototype.getItem;
              const set = Storage.prototype.setItem;
              Storage.prototype.getItem = function (key) {
                if (key === "dufynd_acquisition_attribution_v1") {
                  throw new DOMException("Denied", "SecurityError");
                }
                return get.call(this, key);
              };
              Storage.prototype.setItem = function (key, value) {
                if (key === "dufynd_acquisition_attribution_v1") {
                  throw new DOMException("Denied", "SecurityError");
                }
                return set.call(this, key, value);
              };
            });
          }

          await page.route("**/api/session", (route) =>
            route.fulfill({ json: { session_id: "qa-error-recovery", name: "QA" } }),
          );
          await page.route("**/api/products?**", (route) =>
            route.fulfill({ json: { products: [] } }),
          );
          await page.route("**/api/merchant-partners", (route) =>
            route.fulfill({ json: { partners: [] } }),
          );
          await page.route("**/api/analytics/events", (route) => {
            events.push(route.request().postDataJSON());
            return route.fulfill({ json: { ok: true } });
          });

          await page.goto(
            `${baseUrl}/missing-recovery-route?src=youtube&cmp=missing_qa&content=video_1`,
          );
          await page.getByText("Diese Seite gibt es hier nicht.", { exact: true }).waitFor();

          const link = page.getByRole("link", { name: target.name, exact: true });
          await page.waitForFunction(
            ({ name }) => {
              const candidate = [...document.querySelectorAll("a")].find(
                (anchor) => anchor.textContent?.trim() === name,
              );
              if (!candidate) return false;
              const url = new URL(candidate.href);
              return (
                url.searchParams.get("src") === "youtube" &&
                url.searchParams.get("cmp") === "missing_qa" &&
                url.searchParams.get("content") === "video_1"
              );
            },
            { name: target.name },
          );

          const href = await link.getAttribute("href");
          assert.ok(href, `${target.name}: recovery link must have href`);
          assertAttribution(new URL(href, baseUrl), target.name);

          await link.click();
          await page.waitForURL((url) => url.pathname === target.path);
          assertAttribution(new URL(page.url()), target.name);

          for (
            let attempt = 0;
            attempt < 100 && !events.some((event) => event.event === "page_view");
            attempt += 1
          ) {
            await page.waitForTimeout(50);
          }
          const destinationView = events.filter((event) => event.event === "page_view").at(-1);
          assert.ok(destinationView, `${target.name}: destination page_view missing`);
          assert.equal(destinationView.acquisition_source, "youtube");
          assert.equal(destinationView.campaign_id, "missing_qa");
          assert.equal(destinationView.content_id, "video_1");
          cases += 1;
        } finally {
          await context.close();
        }
      }
    }
  }

  const errorSource = await readFile(new URL("../app/error.tsx", import.meta.url), "utf8");
  assert.match(
    errorSource,
    /<AcquisitionInternalLink[\s\S]*?href="\/duft"/,
    "global error recovery catalog link must use AcquisitionInternalLink",
  );
  assert.doesNotMatch(
    errorSource,
    /<a[\s\S]*?href="\/duft"/,
    "global error recovery must not regress to a raw catalog anchor",
  );

  return cases;
}
