import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";

// Exercise the successful API path, including the backend's category-before-limit
// contract. Empty/offline mocks leave the complete static catalog on screen.
export async function verifyHomeCatalogHydration(browser, baseUrl) {
  const catalog = JSON.parse(await readFile(new URL("../../data/catalog.json", import.meta.url), "utf8"));
  const source = JSON.parse(await readFile(new URL("../../data/scentai_products.json", import.meta.url), "utf8"));
  const blocked = new Set(source.products.filter((row) =>
    row.validation?.blockers?.some((blocker) => String(blocker || "").trim())
  ).map((row) => row.product_id));
  const visible = catalog.products.filter((row) => !blocked.has(row.product_id));
  const fragrances = visible.filter((row) => row.category === "fragrance");
  assert.ok(visible.length > 100, "fixture must exercise the unfiltered API cap");
  assert.ok(visible.slice(100).some((row) => row.category === "fragrance"), "fragrances must occur beyond the unfiltered cap");
  let cases = 0;
  for (const width of [390, 1440]) {
    const context = await browser.newContext({ viewport: { width, height: 900 }, reducedMotion: "reduce" });
    const page = await context.newPage();
    const queries = [];
    try {
      // Selection is under test; external image-host availability is covered elsewhere.
      for (const row of fragrances) {
        if (String(row.image_url || "").startsWith("https://")) {
          await page.route(row.image_url, (route) => route.fulfill({ contentType: "image/png", body: Buffer.from("iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+jv1sAAAAASUVORK5CYII=", "base64") }));
        }
      }
      await page.route("**/api/session", (route) => route.fulfill({ json: { session_id: "qa-catalog-hydration", name: "QA Guest" } }));
      await page.route("**/api/merchant-partners", (route) => route.fulfill({ json: { partners: [] } }));
      await page.route("**/api/analytics/events", (route) => route.fulfill({ json: { ok: true } }));
      await page.route("**/api/products?**", (route) => {
        const query = new URL(route.request().url()).searchParams;
        queries.push(Object.fromEntries(query));
        const selected = query.get("category")
          ? visible.filter((row) => row.category === query.get("category")) : visible;
        return route.fulfill({ json: { products: selected.slice(0, Math.max(1, Math.min(Number(query.get("limit") || 24), 100))) } });
      });
      const response = page.waitForResponse((response) => new URL(response.url()).pathname === "/api/products");
      await page.goto(baseUrl + "/");
      await (await response).finished();
      assert.ok(queries.length > 0, "successful live catalog must be requested");
      assert.ok(queries.every((query) => query.category === "fragrance" && query.limit === "100"), "live catalog must filter fragrances before applying the API cap");
      // Wait for session settlement and the client-rendered homepage, then check
      // every audience against the same visible catalog as the production API.
      await page.getByRole("link", { name: `Alle ${fragrances.length} Düfte im Katalog entdecken →`, exact: true }).waitFor();
      for (const audience of ["women", "men", "unisex"]) {
        const count = fragrances.filter((row) => {
          const groups = String(row.attributes?.target_group || "").split(",").map((group) => group.trim());
          const exclusive = groups.includes("unisex") || (groups.includes("men") && groups.includes("women"))
            ? "unisex" : groups.includes("women") ? "women" : groups.includes("men") ? "men" : null;
          return exclusive === audience;
        }).length;
        const card = page.locator(`a[data-dufynd-home-audience-card][href*="zielgruppe=${audience}"]`);
        const text = count === 1 ? "1 Duft im aktuellen Katalog" : `${count} Düfte im aktuellen Katalog`;
        await page.waitForFunction(({ audience, text }) => {
          const card = document.querySelector(`a[data-dufynd-home-audience-card][href*="zielgruppe=${audience}"]`);
          return card?.innerText.includes(text);
        }, { audience, text });
        if (count) await card.locator("img").first().waitFor({ state: "attached" });
      }
      cases++;
    } finally {
      await context.close();
    }
  }
  return cases;
}
