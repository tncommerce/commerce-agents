import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import vm from "node:vm";
import sharp from "sharp";
import ts from "typescript";
import { RC1_SOCIAL_CARD, source } from "./generate-rc1-social-card.mjs";
for (const fact of ["DUFYND", "RABANNE", "1 Million", "Eau de Toilette · 100 ml"]) {
  assert.ok(source.includes(fact), "Missing editorial fact " + fact);
}
assert.ok(!/<(?:image|foreignObject)(?:\s|>)/i.test(source));
assert.ok(!/(?:href\s*=|xlink:href|url\(https?:|€|InStock|auf Lager|kaufen für)/i.test(source));
const image = readFileSync(new URL("../public" + RC1_SOCIAL_CARD, import.meta.url));
const imageMeta = await sharp(image).metadata();
assert.equal(imageMeta.format, "png");
assert.equal(imageMeta.width, 1200);
assert.equal(imageMeta.height, 630);
assert.ok(image.length < 1_500_000);
const code = ts.transpileModule(
  readFileSync(new URL("../components/FragranceDetailPage.tsx", import.meta.url), "utf8"),
  { compilerOptions: { module: ts.ModuleKind.CommonJS, jsx: ts.JsxEmit.ReactJSX } },
).outputText;
async function metadataFor({ productId, slug, originalUrl = null }) {
  const mod = { exports: {} };
  vm.runInNewContext(code, {
    module: mod, exports: mod.exports,
    require(name) {
      if (name === "@/lib/releasedProfileCatalog") return { RELEASED_PROFILES: [] };
      if (name === "@/lib/accordLabels") return { accordLabel: (value) => value };
      if (name === "@/lib/site") return {
        SITE_INDEXABLE: false, SITE_URL: "https://dufynd.example",
      };
      if (name === "@/lib/fragranceCatalog") return {
        getLiveFragranceBySlug(target) {
          return target !== slug ? null : {
            product_id: productId, slug, brand: "Rabanne", name: "1 Million",
            concentration: "Eau de Toilette", volume_ml: 100, accords: [],
          };
        },
        originalPhotoFor() { return originalUrl ? { url: originalUrl } : null; },
      };
      return {};
    },
  });
  const output = await mod.exports.generateMetadata({ params: Promise.resolve({ slug }) });
  return JSON.parse(JSON.stringify(output));
}
const rc1 = await metadataFor({
  productId: "SC-RABANNE-1-MILLION-EDT-100", slug: "rabanne-1-million",
});
assert.equal(rc1.alternates.canonical, "/duft/rabanne-1-million");
assert.equal(rc1.openGraph.images?.[0]?.url, RC1_SOCIAL_CARD);
assert.equal(rc1.openGraph.images?.[0]?.width, 1200);
assert.equal(rc1.openGraph.images?.[0]?.height, 630);
assert.match(rc1.openGraph.images?.[0]?.alt, /kein Produktfoto/);
assert.equal(rc1.twitter.card, "summary_large_image");
assert.equal(rc1.twitter.images?.[0], RC1_SOCIAL_CARD);
const other = await metadataFor({ productId: "SC-OTHER", slug: "other" });
assert.equal(other.openGraph.images, undefined);
assert.equal(other.twitter.card, "summary");
const original = "https://example.invalid/licensed-original.webp";
const licensed = await metadataFor({
  productId: "SC-RABANNE-1-MILLION-EDT-100", slug: "rabanne-1-million",
  originalUrl: original,
});
assert.equal(licensed.openGraph.images?.[0], original);
assert.equal(licensed.twitter.images?.[0], original);
console.log("RC1 social preview: exact variant, editorial image and product-photo gates PASS");
