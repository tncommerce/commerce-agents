import assert from "node:assert/strict";
import fs from "node:fs";
import vm from "node:vm";
import ts from "typescript";

const read = (path) => JSON.parse(fs.readFileSync(new URL(path, import.meta.url), "utf8"));
const originals = read("../lib/generated/original-photos.json");
const products = read("../lib/generated/public-fragrances.json").products;
const code = ts.transpileModule(
  fs.readFileSync(new URL("../lib/homeVisualAssets.ts", import.meta.url), "utf8"),
  { compilerOptions: { module: ts.ModuleKind.CommonJS } },
).outputText;

function load({ registryAvailable = true } = {}) {
  const mod = { exports: {} };
  vm.runInNewContext(code, {
    module: mod, exports: mod.exports,
    require(name) {
      assert.equal(name, "./fragranceCatalog");
      return {
        originalPhotoFor(fragrance) {
          if (!registryAvailable) return null;
          return fragrance.visuals.find((visual) => originals.some((approved) =>
            approved.product_id === fragrance.product_id &&
            approved.volume_ml === fragrance.volume_ml && approved.url === visual.url,
          )) || null;
        },
      };
    },
  });
  return mod.exports;
}

const contract = load();
const { HOME_EDITORIAL_PRODUCT_ID, HOME_PARTNER_PRODUCTS, getHomeVisual } = contract;
const find = (id) => structuredClone(products.find((product) => product.product_id === id));
const editorial = { kind: "editorial" };
const top = (entry) => ({
  kind: "merchant_showcase", merchantId: "top-parfuemerie",
  destinationUrl: entry.merchantProductUrl,
});
assert.equal(HOME_EDITORIAL_PRODUCT_ID, "SC-LANCOME-LA-VIE-EST-BELLE-EDP-100");
assert.deepEqual(Array.from(HOME_PARTNER_PRODUCTS, (entry) => entry.productId).sort(), [
  "SC-PDM-DELINA-EDP-75", "SC-YSL-BLACK-OPIUM-EDP-90", "SC-YSL-LIBRE-EDP-90",
]);

const lancome = find(HOME_EDITORIAL_PRODUCT_ID);
assert.equal(getHomeVisual(lancome, editorial)?.provenance, "licensed");
assert.equal(getHomeVisual(lancome, top(HOME_PARTNER_PRODUCTS[0])), null);
for (const required of ["license_name", "license_url", "attribution_text", "share_alike_required"]) {
  const incomplete = structuredClone(lancome);
  delete incomplete.visuals[0][required];
  assert.equal(getHomeVisual(incomplete, editorial), null, `Cannot drop ${required}`);
}

for (const entry of HOME_PARTNER_PRODUCTS) {
  const product = find(entry.productId);
  assert.ok(product, `${entry.productId} remains in the public source`);
  assert.equal(product.volume_ml, entry.displayedVolumeMl);
  assert.equal(entry.destinationRequiresSizeSelection, true);
  assert.equal(new URL(entry.merchantProductUrl).hostname, "www.topparfuemerie.de");
  assert.equal(new URL(entry.merchantProductUrl).search, "");
  assert.equal(getHomeVisual(product, top(entry))?.url, entry.imageUrl);
  assert.equal(getHomeVisual(product, editorial), null, "Merchant permission is not editorial permission");
  assert.equal(getHomeVisual(product, { ...top(entry), merchantId: "notino" }), null);
  for (const destinationUrl of [
    "https://www.notino.de/", "/duft/yves-saint-laurent-libre",
    `${entry.merchantProductUrl}?merchant=notino`,
    entry.merchantProductUrl.replace("www.topparfuemerie.de", "www.topparfuemerie.de.example"),
  ]) assert.equal(getHomeVisual(product, { ...top(entry), destinationUrl }), null);
  assert.equal(getHomeVisual({ ...product, volume_ml: 30 }, top(entry)), null);
  assert.equal(getHomeVisual({ ...product, concentration: "Eau de Toilette" }, top(entry)), null);
  const generated = structuredClone(product);
  generated.visuals[0].provenance = "dufynd_generated";
  assert.equal(getHomeVisual(generated, top(entry)), null, "Verified generated fidelity cannot pass");
  const changed = structuredClone(product);
  changed.visuals[0].url += "?altered=1";
  assert.equal(getHomeVisual(changed, top(entry)), null, "Approval binds to exact bitmap URL");
  const pending = structuredClone(product);
  pending.visuals[0].fidelity_status = "pending_review";
  assert.equal(getHomeVisual(pending, top(entry)), null);
  assert.equal(load({ registryAvailable: false }).getHomeVisual(product, top(entry)), null,
    "Placement permission cannot override missing public photo approval");
}

// Existing catalogue visual fidelity is deliberately broader than this contract.
for (const id of ["SC-XERJOFF-NAXOS-100", "SC-SOSPIRO-VIBRATO-100", "SC-RABANNE-1-MILLION-EDT-100"]) {
  const product = find(id);
  assert.ok(product);
  assert.equal(getHomeVisual(product, editorial), null);
  assert.equal(getHomeVisual(product, top(HOME_PARTNER_PRODUCTS[0])), null);
}
const unknown = { ...lancome, product_id: "UNREVIEWED-NEW-PRODUCT" };
assert.equal(getHomeVisual(unknown, editorial), null);
assert.equal(load({ registryAvailable: false }).getHomeVisual(lancome, editorial), null);
console.log("Home visual assets: exact originals, merchant placement, variant, attribution and fail-closed guards PASS");
