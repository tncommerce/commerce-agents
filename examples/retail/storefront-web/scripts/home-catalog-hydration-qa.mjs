import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";

// Homepage catalog counts are derived from the public static facts (37 + 20),
// not the legacy capped /api/products response. An unavailable API must never
// hide a previously owner-approved fragrance or invent another product.
export async function verifyHomeCatalogHydration(browser, baseUrl) {
  const read = async (name) => JSON.parse(
    await readFile(new URL(name, import.meta.url), "utf8"),
  );
  const catalog = await read("../../data/catalog.json");
  const sources = await read("../../data/scentai_products.json");
  const release = await read("../lib/generated/released-profiles.json");
  const approvals = await read("../../data/dufynd_release_authorizations.json");
  const sourceById = new Map(sources.products.map((row) => [row.product_id, row]));
  const baseFragrances = catalog.products.filter((row) =>
    String(row.product_id || "").startsWith("SC-") &&
    row.category === "fragrance" &&
    row.in_stock !== false &&
    !sourceById.get(row.product_id)?.validation?.blockers?.some((x) => String(x || "").trim())
  );
  const released = release.profiles;
  const eligible = new Set(approvals.approvals.filter((row) =>
    row.publication_approved === true && row.indexing_approved === true
  ).map((row) => row.product_id));
  assert.equal(baseFragrances.length, 37, "existing verified public cohort");
  assert.equal(released.length, 20, "exact owner-authorized fact-only wave");
  assert.equal(eligible.size, released.length, "release approvals are exact");
  assert.deepEqual(new Set(released.map((row) => row.product_id)), eligible);
  assert.equal(new Set([
    ...baseFragrances.map((row) => row.product_id), ...eligible,
  ]).size, 57, "no duplicate public product or unapproved second wave");

  function audienceOf(values) {
    const groups = new Set(values.map((x) => String(x).toLowerCase().trim()).filter(Boolean));
    if (groups.has("unisex") || (groups.has("men") && groups.has("women"))) return "unisex";
    if (groups.has("women")) return "women";
    if (groups.has("men")) return "men";
    return null;
  }
  const expected = { women: 0, men: 0, unisex: 0 };
  for (const row of baseFragrances) {
    const original = sourceById.get(row.product_id);
    const groups = original?.classification?.scentai_target_groups?.length
      ? original.classification.scentai_target_groups
      : String(row.attributes?.target_group || "").split(",").filter(Boolean);
    const audience = audienceOf(groups);
    assert.ok(audience, `missing source audience for ${row.product_id}`);
    expected[audience] += 1;
  }
  for (const row of released) {
    assert.equal(row.indexing_approved, true);
    const audience = audienceOf(row.target_groups || []);
    assert.ok(audience, `missing released audience for ${row.product_id}`);
    expected[audience] += 1;
  }
  assert.equal(Object.values(expected).reduce((a, b) => a + b, 0), 57);

  let cases = 0;
  for (const width of [390, 1440]) {
    const context = await browser.newContext({
      viewport: { width, height: 900 }, reducedMotion: "reduce",
    });
    const page = await context.newPage();
    const requests = [];
    try {
      // Only synthetic API responses; never load merchant links or analytics.
      // /api/products intentionally fails because the homepage no longer uses it.
      await page.route("**/api/products?**", (route) => {
        requests.push(route.request().url());
        return route.fulfill({ status: 503, json: { error: "Synthetic API outage" } });
      });
      await page.route("**/api/session", (route) =>
        route.fulfill({ json: { session_id: "qa-home-57", name: "QA Guest" } }));
      await page.route("**/api/merchant-partners", (route) =>
        route.fulfill({ json: { partners: [] } }));
      await page.route("**/api/analytics/events", (route) =>
        route.fulfill({ json: { ok: true } }));
      await page.route("**/api/clickout/**", () => {
        throw new Error("Homepage QA must never click an affiliate merchant");
      });
      await page.goto(baseUrl + "/", { waitUntil: "domcontentloaded" });
      const all = page.getByRole("link", {
        name: "Alle 57 Düfte im Katalog entdecken →", exact: true,
      });
      await all.waitFor({ state: "visible", timeout: 30_000 });
      assert.equal(new URL(await all.getAttribute("href"), baseUrl).pathname,
        "/duft", "homepage catalog entry must remain internal");
      for (const audience of ["women", "men", "unisex"]) {
        const card = page.locator(
          `a[data-dufynd-home-audience-card][href*="zielgruppe=${audience}"]`,
        );
        await card.waitFor({ state: "visible" });
        const count = expected[audience];
        const label = count === 1
          ? "1 Duft im aktuellen Katalog"
          : `${count} Düfte im aktuellen Katalog`;
        assert.ok((await card.innerText()).includes(label),
          `homepage audience ${audience}: expected ${label}`);
        assert.equal(
          new URL(await card.getAttribute("href"), baseUrl).searchParams.get("zielgruppe"),
          audience,
        );
      }
      assert.deepEqual(requests, [],
        "57-product homepage must not depend on legacy capped products API");
      cases++;
    } finally {
      await context.close();
    }
  }
  return cases;
}
