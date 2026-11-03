import assert from "node:assert/strict";
import fs from "node:fs";
import vm from "node:vm";
import ts from "typescript";

function compile(file) {
  return ts.transpileModule(
    fs.readFileSync(new URL(file, import.meta.url), "utf8"),
    { compilerOptions: { module: ts.ModuleKind.CommonJS, jsx: ts.JsxEmit.ReactJSX } },
  ).outputText;
}
const pairCode = compile("../app/vergleich/[pair]/page.tsx");
const pickerCode = compile("../components/FragranceComparisonPicker.tsx");
const indexCode = compile("../app/vergleich/page.tsx");

const emptyCommunity = {
  rating_10: null, rating_count: 0, longevity_10: null,
  projection_10: null, provisional: false,
};
const fragrance = (name, community = emptyCommunity) => ({
  name, brand: "Fixture", product_id: name, slug: name.toLowerCase(),
  concentration: "Eau de Parfum", volume_ml: 100,
  community, accords: [], target_groups: [],
  scores: { freshness: 5, sweetness: 4, woodiness: 6, spiciness: 3 },
  market: { reference_price_eur: 80, checked_at: "2026-10-01" },
});

function load(leftCommunity = emptyCommunity, rightCommunity = emptyCommunity, code = pairCode) {
  const pair = {
    pair_slug: "fixture-left-vs-right", kind: "alternative", confidence: "medium",
    left: fragrance("Left", leftCommunity), right: fragrance("Right", rightCommunity),
  };
  const mod = { exports: {} };
  const jsx = (type, props) => ({ type, props });
  const states = ["Left", "Right", true, "", "", ""];
  vm.runInNewContext(code, {
    module: mod, exports: mod.exports,
    require(name) {
      if (name === "react/jsx-runtime") return { jsx, jsxs: jsx };
      if (name === "react") return {
        useMemo: (fn) => fn(), useEffect: () => {}, useRef: (current) => ({ current }),
        useState: () => [states.shift(), () => {}],
      };
      if (name === "@/lib/catalogJourney") return { withCatalogContext: (url) => url };
      if (name === "@/lib/site") return { SITE_URL: "https://dufynd.example" };
      if (name === "@/lib/analytics") return { appendAcquisitionAttribution: (url) => url };
      if (name === "@/lib/fragranceCatalog") return {
        getComparisonPair: () => pair, originalPhotoFor: () => null,
        visualWorldFor: () => "neutral", EXPLICIT_COMPARISON_PAIRS: [pair],
      };
      if (name === "@/lib/priceReference") return { formatPriceReference: () => "80 € · Stand 01.10.2026" };
      if (name === "@/lib/targetLabels") return { targetGroupLabel: () => "Unisex" };
      return { default: () => null };
    },
  });
  return mod.exports;
}

function nodes(tree) {
  if (tree == null || typeof tree === "boolean") return [];
  if (Array.isArray(tree)) return tree.flatMap(nodes);
  if (typeof tree !== "object") return [tree];
  if (typeof tree.type === "function") return nodes(tree.type(tree.props));
  return [tree, ...nodes(tree.props?.children)];
}
const params = { params: Promise.resolve({ pair: "fixture-left-vs-right" }) };
const absent = load();
const absentTree = nodes(await absent.default(params));
const headers = absentTree.filter((n) => n?.props?.role === "rowheader").map((n) => n.props.children);
assert.deepEqual(headers, ["Frische", "Süße", "Holzigkeit", "Würze", "Zielgruppe", "Preis-Richtwert"]);
assert.ok(absentTree.some((n) => typeof n === "string" && n.includes("derzeit nicht veröffentlicht")));

// A published value of zero is a real value; unavailable counts use a dash.
const partial = load({ ...emptyCommunity, rating_10: 0, rating_count: 12, longevity_10: 0, provisional: true });
const partialTree = nodes(await partial.default(params));
const row = (label) => partialTree.find((n) => n?.props?.role === "row" && nodes(n).some((x) => x?.props?.role === "rowheader" && x.props.children === label));
const cells = (label) => nodes(row(label)).filter((n) => n?.props?.role === "cell").map((n) => n.props.children);
assert.deepEqual(cells("Bewertungen"), ["12", "–"]);
assert.deepEqual(cells("Community"), ["0,0/10 · vorläufig", "–"]);
assert.deepEqual(cells("Haltbarkeit"), ["0,0 · vorläufig", "–"]);
assert.equal(row("Ausstrahlung"), undefined);

const meta = await absent.generateMetadata(params);
assert.doesNotMatch(meta.description, /Community|Haltbarkeit|Ausstrahlung/);
assert.match(meta.description, /exakte Varianten/);
assert.equal(meta.twitter.title, meta.openGraph.title);
assert.equal(meta.twitter.description, meta.description);
assert.equal(meta.twitter.card, "summary");
assert.equal(meta.openGraph.url, "https://dufynd.example/vergleich/fixture-left-vs-right");

const pickerProps = (community) => ({ fragrances: [fragrance("Left", community), fragrance("Right")] });
const picker = load(emptyCommunity, emptyCommunity, pickerCode);
const emptyPicker = nodes(picker.default(pickerProps(emptyCommunity)));
assert.deepEqual(emptyPicker.filter((n) => n?.props?.role === "rowheader").map((n) => n.props.children), headers);
assert.ok(emptyPicker.some((n) => typeof n === "string" && n.includes("derzeit nicht veröffentlicht")));
const zeroPicker = load(emptyCommunity, emptyCommunity, pickerCode);
const publishedPicker = nodes(zeroPicker.default(pickerProps({ ...emptyCommunity, rating_10: 0, projection_10: 0, provisional: true })));
assert.ok(publishedPicker.includes("0,0/10 · vorläufig"));
assert.ok(publishedPicker.includes("0,0 · vorläufig"));
assert.ok(!publishedPicker.some((n) => n?.props?.role === "rowheader" && n.props.children === "Haltbarkeit"));

const index = load(emptyCommunity, emptyCommunity, indexCode).metadata;
assert.doesNotMatch(index.description, /Community|Haltbarkeit|Ausstrahlung/);
assert.equal(index.twitter.title, index.title);
assert.equal(index.openGraph.url, "https://dufynd.example/vergleich");
assert.equal(index.twitter.description, index.description);
console.log("Comparison trust: pair pages, free picker, withheld/partial/zero values and hub/social metadata PASS");

// Evidence is independent of merchant availability. Missing notes must not become
// invented differences; normalization must not imply unsupported synonym matches.
const evidenceModule = { exports: {} };
vm.runInNewContext(compile("../components/FragranceComparisonEvidence.tsx"), {
  module: evidenceModule, exports: evidenceModule.exports,
  require(name) {
    if (name === "react/jsx-runtime") return { jsx: (type, props) => ({ type, props }), jsxs: (type, props) => ({ type, props }) };
    if (name === "@/lib/accordLabels") return { accordLabel: term => term };
    if (name === "@/lib/noteLabels") return { noteLabel: term => term };
    throw new Error(`Unexpected evidence dependency: ${name}`);
  },
});
const evidenceFragrance = (name, key = []) => ({ name, accords: [], notes: { top: [], heart: [], base: [], key, supporting: [] } });
const evidenceNodes = (left, right) => nodes(evidenceModule.exports.default({ left, right }));
const insufficient = evidenceNodes(evidenceFragrance("Left"), evidenceFragrance("Right"));
assert.ok(insufficient.some(n => typeof n === "string" && n.includes("Keine übereinstimmende Note in den vorhandenen Notenlisten")));
assert.ok(insufficient.some(n => typeof n === "string" && n.includes("Das schließt einen ähnlichen Dufteindruck nicht aus")));
const documented = evidenceNodes(evidenceFragrance("Left", ["Vanilla", "vanilla", "coffee", "Moroccan orange blossom"]), evidenceFragrance("Right", [" VANILLA ", "jasmine", "orange blossom"]));
const terms = label => nodes(documented.find(n => n?.type === "ul" && n.props["aria-label"] === label)).filter(n => n?.type === "li").map(n => n.props.children);
assert.deepEqual(terms("Dokumentierte gemeinsame Duftnoten"), ["Vanilla"]);
assert.deepEqual(terms("Zusätzlich für Left dokumentierte Noten"), ["coffee", "Moroccan orange blossom"]);
assert.deepEqual(terms("Zusätzlich für Right dokumentierte Noten"), ["jasmine", "orange blossom"]);
assert.ok(documented.some(n => typeof n === "string" && n.includes("Nicht genannte Noten sind nicht sicher ausgeschlossen")));
console.log("Comparison evidence: missing data, deduplication, exact overlap and non-inferred synonyms PASS");
