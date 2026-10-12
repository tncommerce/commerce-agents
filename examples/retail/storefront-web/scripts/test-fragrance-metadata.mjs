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
