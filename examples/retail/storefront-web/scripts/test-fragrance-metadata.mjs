import assert from "node:assert/strict";
import fs from "node:fs";
import vm from "node:vm";
import ts from "typescript";

const code = ts.transpileModule(
  fs.readFileSync(new URL("../components/FragranceDetailPage.tsx", import.meta.url), "utf8"),
  { compilerOptions: { module: ts.ModuleKind.CommonJS, jsx: ts.JsxEmit.ReactJSX } },
).outputText;

const product = {
  slug: "fixture-exact-fragrance",
  indexing_approved: true,
  seo: {
    title: "Fixture fragrance — Eau de Parfum 100 ml",
    description: "Synthetic metadata fixture; no merchant offer or public release.",
    public_path: "/duft/fixture-exact-fragrance",
  },
};

async function metadata(siteIndexable, indexingApproved) {
  const mod = { exports: {} };
  vm.runInNewContext(code, {
    module: mod,
    exports: mod.exports,
    require(name) {
      if (name === "@/lib/site") {
        return { SITE_URL: "https://dufynd.example", SITE_INDEXABLE: siteIndexable };
      }
      if (name === "@/lib/releasedProfileCatalog") {
        return { RELEASED_PROFILES: [{ ...product, indexing_approved: indexingApproved }] };
      }
      // No component render, network, build artifacts, or real approvals involved.
      return {};
    },
  });
  return JSON.parse(JSON.stringify(await mod.exports.generateMetadata({
    params: Promise.resolve({ slug: product.slug }),
  })));
}

for (const globalGate of [false, true]) {
  for (const productGate of [false, true]) {
    const meta = await metadata(globalGate, productGate);
    assert.equal(meta.robots.index, globalGate && productGate,
      "product approval cannot override the global noindex gate");
    assert.equal(meta.robots.follow, globalGate);
    assert.equal(meta.alternates.canonical, product.seo.public_path);
    assert.equal(meta.openGraph.url, `https://dufynd.example${product.seo.public_path}`);
    assert.equal(meta.openGraph.title, product.seo.title);
    assert.equal(meta.openGraph.description, product.seo.description);
    assert.equal(meta.twitter.title, product.seo.title);
    assert.equal(meta.twitter.description, product.seo.description);
    assert.equal(meta.twitter.card, "summary");
    assert.deepEqual(meta.openGraph.images, []);
    assert.deepEqual(meta.twitter.images, []);
  }
}
console.log("Fragrance metadata: all four indexing gates and product-specific social previews PASS");

// WORK45: rejected editorial creative must not enter the release.
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
assert.equal(rc1.openGraph.images, undefined);
assert.equal(rc1.twitter.images, undefined);
assert.equal(rc1.twitter.card, "summary");
assert.match(rc1.title, /Rabanne 1 Million/);
assert.match(rc1.title, /100 ml/);
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
assert.equal(licensed.twitter.card, "summary_large_image");
console.log("RC1 metadata: exact identity, unapproved creative excluded, licensed-photo precedence PASS");
