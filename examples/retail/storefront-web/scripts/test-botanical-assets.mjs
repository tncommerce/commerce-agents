import assert from "node:assert/strict";
import { createHash } from "node:crypto";
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";
import ts from "typescript";

const root = fileURLToPath(new URL("../", import.meta.url));
const directory = path.join(root, "public/visual-notes");
const photoRole = "botanical_note_illustration_not_product_photo";
const plateRole = "historical_botanical_illustration_not_product_photo";
const plateAuthors = "Brandt, Wilhelm; Gürke, M.; Köhler, F. E.; Pabst, G.; Schellenberg, G.; Vogtherr, Max.; digitisation: Biodiversity Heritage Library";
const plateLicense = "CC BY 2.0 and PD-scan-old-expired explicitly documented on source page";
const commons = "https://commons.wikimedia.org/wiki/File:";
const by = "https://creativecommons.org/licenses/by/2.0/";
const bySa = "https://creativecommons.org/licenses/by-sa/3.0/";

// Reviewed, image-specific source bindings. A Commons host or feed URL alone
// never grants rights. New artwork needs a separately reviewed entry here.
const approved = {
  "lavender-norbert-nagel.jpg": {
    source: `${commons}Lavandula_angustifolia_-_lavender_-_Lavendel_-_01.jpg`,
    author: "Norbert Nagel", license: "CC BY-SA 3.0", licenseUrl: bySa,
    shareAlike: true, role: photoRole, component: "HomeComparison.tsx", visibleCreator: "Norbert Nagel",
  },
  "coffee-nate-steiner.jpg": {
    source: `${commons}Coffee_Beans_closeup.jpg`, author: "Nate Steiner",
    license: "CC BY 2.0", licenseUrl: by, shareAlike: false,
    role: photoRole, component: "HomeComparison.tsx", visibleCreator: "Nate Steiner",
  },
  "vanilla-koehler.jpg": {
    source: `${commons}K%C3%B6hler%27s_Medizinal-Pflanzen_in_naturgetreuen_Abbildungen_mit_kurz_erl%C3%A4uterndem_Texte_(Plate_114)_(8232785888).jpg`,
    author: plateAuthors, license: plateLicense, licenseUrl: by, shareAlike: false,
    role: plateRole, component: "ScentWorlds.tsx", visibleCreator: "Biodiversity Heritage Library",
  },
  "rose-koehler.jpg": {
    source: `${commons}K%C3%B6hler%27s_Medizinal-Pflanzen_in_naturgetreuen_Abbildungen_mit_kurz_erl%C3%A4uterndem_Texte_(Plate_124)_(8232791024).jpg`,
    author: plateAuthors, license: plateLicense, licenseUrl: by, shareAlike: false,
    role: plateRole, component: "ScentWorlds.tsx", visibleCreator: "Biodiversity Heritage Library",
  },
  "citrus-koehler.jpg": {
    source: `${commons}Citrus_limonum_(K%C3%B6hler).jpg`, author: "Hermann Adolf Köhler (1834–1879)",
    license: "Public Domain Mark 1.0 / author life + 100 years",
    licenseUrl: "https://creativecommons.org/publicdomain/mark/1.0/", shareAlike: false,
    role: plateRole, component: "ScentWorlds.tsx", visibleCreator: "Hermann Adolf Köhler",
  },
};

function componentEvidence(source, name) {
  const tree = ts.createSourceFile(name, source, ts.ScriptTarget.Latest, true, ts.ScriptKind.TSX);
  const links = new Set(), literals = new Set(), visible = [];
  function visit(node) {
    if (ts.isStringLiteral(node)) literals.add(node.text);
    if (ts.isJsxText(node)) visible.push(node.text);
    if ((ts.isJsxOpeningElement(node) || ts.isJsxSelfClosingElement(node)) && node.tagName.getText(tree) === "a") {
      const href = node.attributes.properties.find((attribute) => ts.isJsxAttribute(attribute) && attribute.name.getText(tree) === "href");
      if (href?.initializer && ts.isStringLiteral(href.initializer)) links.add(href.initializer.text);
    }
    ts.forEachChild(node, visit);
  }
  visit(tree);
  return { links, literals, text: visible.join(" ") };
}

function verify({ entries, files, credits, components }) {
  assert.ok(Array.isArray(entries), "Botanical source ledger must be an array");
  const names = entries.map((entry) => entry.file);
  assert.equal(new Set(names).size, names.length, "Duplicate botanical source entry");
  assert.deepEqual([...names].sort(), Object.keys(approved).sort(), "Only the five reviewed note illustrations may ship");
  assert.deepEqual(Object.keys(files).sort(), [...names].sort(), "Every shipped botanical image needs exactly one source entry");
  const parsed = Object.fromEntries(Object.entries(components).map(([name, source]) => [name, componentEvidence(source, name)]));
  for (const entry of entries) {
    assert.match(entry.file, /^[a-z0-9]+(?:-[a-z0-9]+)*\.jpg$/, "Asset path must be a local JPEG basename");
    const expected = approved[entry.file];
    const label = entry.file;
    for (const [field, value] of Object.entries({ source_url: expected.source, author: expected.author,
      license: expected.license, license_url: expected.licenseUrl, share_alike: expected.shareAlike, asset_role: expected.role })) {
      assert.equal(entry[field], value, `${label}: reviewed ${field} binding changed`);
    }
    assert.ok(entry.title?.trim(), `${label}: source title missing`);
    assert.match(entry.verified_at, /^\d{4}-\d{2}-\d{2}$/, `${label}: verification date missing`);
    assert.ok(Number.isFinite(Date.parse(entry.verified_at)), `${label}: verification date invalid`);
    assert.match(entry.sha256, /^[a-f0-9]{64}$/, `${label}: invalid SHA256`);
    assert.ok(Number.isSafeInteger(entry.bytes) && entry.bytes > 0, `${label}: byte count missing`);
    const data = files[label];
    assert.equal(data.length, entry.bytes, `${label}: byte length differs from reviewed ledger`);
    assert.equal(createHash("sha256").update(data).digest("hex"), entry.sha256, `${label}: file differs from reviewed ledger`);
    assert.equal(data.readUInt16BE(0), 0xffd8, `${label}: expected JPEG data`);
    const download = new URL(entry.download_url);
    assert.equal(download.origin, "https://upload.wikimedia.org", `${label}: unreviewed download origin`);
    assert.equal(download.search + download.hash, "", `${label}: download must not contain tracking or fragments`);
    const sourceName = decodeURIComponent(new URL(expected.source).pathname.slice("/wiki/File:".length));
    assert.equal(decodeURIComponent(download.pathname.split("/").at(-1)).replace(/^\d+px-/, ""), sourceName,
      `${label}: thumbnail points at a different work`);
    assert.ok(entry.file_changes?.trim() && entry.presentation_changes?.trim(), `${label}: modification disclosure missing`);
    if (expected.shareAlike) assert.ok(entry.presentation_changes.includes("CC BY-SA 3.0"), `${label}: derivative share-alike disclosure missing`);
    assert.ok(credits.includes(expected.source) && credits.includes(expected.licenseUrl), `${label}: documentation credit missing`);
    const component = parsed[expected.component];
    assert.ok(component.literals.has(`/visual-notes/${label}`), `${label}: reviewed display binding missing`);
    assert.ok(component.links.has(expected.source) && component.links.has(expected.licenseUrl), `${label}: visible source/licence links missing`);
    assert.ok(component.text.includes(expected.visibleCreator), `${label}: visible creator credit missing`);
    assert.match(component.text, /keine Produkt(?:abbildungen|bilder)/i, `${label}: note illustration must not be represented as product photography`);
  }
}

const diskNames = fs.readdirSync(directory).filter((name) => !["sources.json", "CREDITS.md"].includes(name));
const files = Object.fromEntries(diskNames.map((name) => {
  assert.match(name, /^[a-z0-9]+(?:-[a-z0-9]+)*\.jpg$/, `Unexpected botanical path: ${name}`);
  const location = path.join(directory, name);
  assert.equal(fs.realpathSync(location), location, `${name}: botanical assets must not be symlinks`);
  return [name, fs.readFileSync(location)];
}));
const baseline = {
  entries: JSON.parse(fs.readFileSync(path.join(directory, "sources.json"), "utf8")), files,
  credits: fs.readFileSync(path.join(directory, "CREDITS.md"), "utf8"),
  components: Object.fromEntries(["HomeComparison.tsx", "ScentWorlds.tsx"].map((name) => [name,
    fs.readFileSync(path.join(root, "components", name), "utf8")])),
};
verify(baseline);

// Failure cases exercise the gate without modifying working files or fetching
// third-party content: changed bytes, wrong provenance, and removed credit.
let rejected = 0;
function rejects(change) {
  const sample = { ...baseline, entries: structuredClone(baseline.entries), files: { ...files }, components: { ...baseline.components } };
  change(sample);
  assert.throws(() => verify(sample), assert.AssertionError);
  rejected += 1;
}
rejects((sample) => { sample.files["lavender-norbert-nagel.jpg"] = Buffer.from(sample.files["lavender-norbert-nagel.jpg"]); sample.files["lavender-norbert-nagel.jpg"][100] ^= 1; });
rejects((sample) => { sample.entries[0].source_url = approved["coffee-nate-steiner.jpg"].source; });
rejects((sample) => { sample.entries[0].license_url = by; });
rejects((sample) => { sample.entries[0].asset_role = "product_photo"; });
rejects((sample) => { sample.entries[0].file = "../unreviewed.jpg"; });
rejects((sample) => { sample.entries.push(structuredClone(sample.entries[0])); });
rejects((sample) => { delete sample.files["rose-koehler.jpg"]; });
rejects((sample) => { sample.components["HomeComparison.tsx"] = sample.components["HomeComparison.tsx"].replace(`href="${bySa}"`, 'href="/"'); });
rejects((sample) => { sample.components["ScentWorlds.tsx"] = sample.components["ScentWorlds.tsx"].replace(`href="${approved["citrus-koehler.jpg"].source}"`, 'href="/"'); });
console.log(`Botanical assets: ${baseline.entries.length} exact files/source bindings/visible credits verified; ${rejected} unsafe changes rejected — PASS`);
