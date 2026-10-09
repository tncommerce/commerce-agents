// Real rendered browser evidence. No image mocks, generated images or clickouts.
import { chromium } from "playwright";
import { mkdir, readFile, writeFile } from "node:fs/promises";
import path from "node:path";

const args = process.argv.slice(2);
const value = (key, fallback) => args.includes(key) ? args[args.indexOf(key) + 1] : fallback;
const base = value("--base-url", "http://127.0.0.1:3000");
const before = value("--before-url", "");
const out = path.resolve(value("--out", ".visual-qa/catalog-photos"));
await mkdir(out, { recursive: true });
const audit = JSON.parse(await readFile(new URL("../../data/dufynd_catalog_photo_audit_20261010.json", import.meta.url)));
const approved = audit.entries.filter((row) => row.status === "PASS");
const browser = await chromium.launch({
  headless: true,
  executablePath: process.env.PLAYWRIGHT_CHROMIUM_EXECUTABLE_PATH || undefined,
});
const report = { checks: [], failures: [], quality_target_met: false, reason: "33 original product photographs remain on HOLD" };

async function settle(page) {
  await page.locator("article.dufynd-catalog-card").first().waitFor();
  await page.evaluate(async () => {
    for (const image of document.images) image.loading = "eager";
    await Promise.all(Array.from(document.images, (image) => Promise.race([
      image.decode().catch(() => {}), new Promise((resolve) => setTimeout(resolve, 10000)),
    ])));
    await Promise.race([document.fonts.ready, new Promise((resolve) => setTimeout(resolve, 8000))]);
  });
}

async function showAll(page) {
  const more = page.getByRole("button", { name: /Weitere.*Düfte anzeigen/ });
  for (let attempt = 0; attempt < 4 && await more.count(); attempt++) {
    const count = await page.locator("article.dufynd-catalog-card").count();
    await more.click();
    await page.waitForFunction((previous) => document.querySelectorAll("article.dufynd-catalog-card").length > previous, count, { timeout: 5000 });
  }
  if (await more.count()) throw new Error("Catalog expansion did not finish within four actions");
}

try {
  for (const width of [320, 390, 1440]) {
    const context = await browser.newContext({ viewport: { width, height: 1000 }, deviceScaleFactor: 1 });
    // Browser QA must not become visitor or affiliate statistics.
    await context.route("**/api/analytics/events", (route) => route.abort());
    await context.route("**/api/clickout/**", (route) => route.abort());
    const phases = before ? [["before", before], ["after", base]] : [["after", base]];
    for (const [phase, origin] of phases) {
      const page = await context.newPage();
      page.setDefaultTimeout(15000);
      try {
        await page.goto(`${origin}/duft?src=qa&cmp=qa-catalog-photos-20261010&content=${phase}`, { waitUntil: "domcontentloaded", timeout: 45000 });
        await settle(page);
        await page.locator('section[aria-label="Passende Düfte"]').screenshot({ path: `${out}/${phase}-${width}.png` });
        if (phase === "after") {
          await showAll(page);
          await settle(page);
          const cards = page.locator("article.dufynd-catalog-card");
          if (await cards.count() !== audit.entries.length) throw new Error("Missing product cards");
          if (await cards.locator('[data-dufynd-image-kind="editorial"], img[src*="/products/pilot/"], img[src*="cutout-production"]').count()) throw new Error("Generated/editorial bottle leaked into catalog");
          for (const row of audit.entries) {
            const photo = cards.locator(`[data-dufynd-product-id="${row.product_id}"]`);
            if (await photo.count() !== 1) throw new Error(`Missing image policy: ${row.product_id}`);
            const expected = row.status === "PASS" ? "approved" : "hold";
            if (await photo.getAttribute("data-dufynd-photo-status") !== expected) throw new Error(`Image state/load mismatch: ${row.product_id}`);
            if (row.status === "PASS") {
              const image = photo.locator("img");
              if (await image.getAttribute("src") !== row.source) throw new Error(`Wrong original source: ${row.product_id}`);
              if (!await image.evaluate((el) => el.complete && el.naturalWidth > 0)) throw new Error(`Image did not load: ${row.product_id}`);
              await photo.screenshot({ path: `${out}/photo-${row.product_id}-${width}.png` });
            }
          }
          const overflow = await page.evaluate(() => document.documentElement.scrollWidth > window.innerWidth + 1);
          if (overflow) throw new Error("Horizontal page overflow");
          // Both HOLD cards and original-photo cards retain their real product navigation.
          for (const id of [audit.entries[0].product_id, approved[0].product_id]) {
            const link = page.locator(`article a:has([data-dufynd-product-id="${id}"])`);
            const href = await link.getAttribute("href");
            await link.click();
            await page.waitForURL((url) => url.pathname === new URL(href, base).pathname);
            if (!await page.getByRole("heading", { level: 1 }).isVisible()) throw new Error("Missing product heading after card click");
            await page.goBack({ waitUntil: "domcontentloaded" });
            await settle(page);
            await showAll(page);
          }
        }
        report.checks.push({ phase, width, status: "PASS" });
      } catch (error) {
        report.failures.push({ phase, width, message: String(error) });
      } finally {
        await page.close();
      }
    }
    await context.close();
  }
} finally {
  await browser.close();
  await writeFile(`${out}/report.json`, JSON.stringify(report, null, 2));
}
console.log(JSON.stringify(report, null, 2));
if (report.failures.length) process.exitCode = 1;
