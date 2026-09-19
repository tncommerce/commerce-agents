import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const here = path.dirname(fileURLToPath(import.meta.url));
const storefrontRoot = path.resolve(here, "..");
const dataRoot = path.resolve(storefrontRoot, "..", "data");
const publicRoot = path.join(storefrontRoot, "public");

const DEFAULT_SITE_URL = "https://dufynd.de";

function normalizedSiteUrl(value) {
  const candidate = String(value || DEFAULT_SITE_URL)
    .trim()
    .replace(/\/$/, "");

  try {
    const parsed = new URL(candidate);
    if (!["http:", "https:"].includes(parsed.protocol)) {
      return DEFAULT_SITE_URL;
    }
    return parsed.toString().replace(/\/$/, "");
  } catch {
    return DEFAULT_SITE_URL;
  }
}

function slugifyFragrance(value) {
  return String(value || "")
    .normalize("NFKD")
    .replace(/[\u0300-\u036f]/g, "")
    .replace(/[’']/g, "")
    .replace(/&/g, " und ")
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, "-")
    .replace(/^-+|-+$/g, "");
}

function xmlEscape(value) {
  return String(value)
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&apos;");
}

function readJson(fileName) {
  return JSON.parse(
    fs.readFileSync(path.join(dataRoot, fileName), "utf8"),
  );
}

const catalog = readJson("catalog.json");
const source = readJson("scentai_products.json");
const sourceById = new Map(
  (source.products || []).map((product) => [
    product.product_id,
    product,
  ]),
);

const liveProducts = (catalog.products || []).filter(
  (product) =>
    String(product.product_id || "").startsWith("SC-") &&
    product.category === "fragrance" &&
    product.in_stock !== false,
);

const liveById = new Map();
for (const product of liveProducts) {
  const sourceProduct = sourceById.get(product.product_id);
  const attributes = product.attributes || {};
  const brand = String(
    product.brand || sourceProduct?.brand || "",
  ).trim();
  const name = String(
    attributes.canonical_name ||
      sourceProduct?.name ||
      product.title ||
      "",
  ).trim();
  const slug = slugifyFragrance(`${brand} ${name}`);
  liveById.set(product.product_id, {
    ...product,
    brand,
    name,
    slug,
    relationships:
      sourceProduct?.relationships || [],
  });
}

const duplicateSlugCheck = new Map();
for (const product of liveById.values()) {
  duplicateSlugCheck.set(
    product.slug,
    (duplicateSlugCheck.get(product.slug) || 0) + 1,
  );
}
const duplicateSlugs = [...duplicateSlugCheck.entries()]
  .filter(([, count]) => count > 1)
  .map(([slug]) => slug);

if (duplicateSlugs.length) {
  throw new Error(
    `Duplicate fragrance slugs prevent sitemap generation: ${duplicateSlugs.join(", ")}`,
  );
}

const comparisonPairs = new Set();
for (const product of liveById.values()) {
  for (const relationship of product.relationships) {
    if (
      !["clone", "inspired", "alternative"].includes(
        relationship.relationship_type,
      )
    ) {
      continue;
    }

    const related = liveById.get(
      relationship.related_product_id,
    );
    if (!related) continue;

    const pair = [product.slug, related.slug]
      .sort((a, b) => a.localeCompare(b))
      .join("-vs-");
    comparisonPairs.add(pair);
  }
}

const siteUrl = normalizedSiteUrl(
  process.env.NEXT_PUBLIC_SITE_URL,
);
const indexable =
  process.env.NEXT_PUBLIC_SITE_INDEXABLE === "true";

const routes = [
  "/",
  "/duft",
  "/vergleich",
  "/duftfinder",
  "/parfum-alternativen",
  "/parfum-geschenkberater",
  "/transparenz",
  ...[...liveById.values()].map(
    (product) => `/duft/${product.slug}`,
  ),
  ...[...comparisonPairs]
    .sort((a, b) => a.localeCompare(b))
    .map((pair) => `/vergleich/${pair}`),
];

const uniqueRoutes = [...new Set(routes)];

const sitemap = [
  '<?xml version="1.0" encoding="UTF-8"?>',
  '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">',
  ...uniqueRoutes.map(
    (route) =>
      `  <url><loc>${xmlEscape(
        `${siteUrl}${route === "/" ? "" : route}`,
      )}</loc></url>`,
  ),
  "</urlset>",
  "",
].join("\n");

const robots = indexable
  ? [
      "User-agent: *",
      "Allow: /",
      "",
      `Sitemap: ${siteUrl}/sitemap.xml`,
      "",
    ].join("\n")
  : [
      "User-agent: *",
      "Disallow: /",
      "",
      "# DUFYND remains intentionally non-indexable until launch.",
      "",
    ].join("\n");

fs.mkdirSync(publicRoot, { recursive: true });
fs.writeFileSync(
  path.join(publicRoot, "sitemap.xml"),
  sitemap,
  "utf8",
);
fs.writeFileSync(
  path.join(publicRoot, "robots.txt"),
  robots,
  "utf8",
);

console.log(
  `DUFYND SEO generated: ${uniqueRoutes.length} sitemap routes; indexable=${indexable}; site=${siteUrl}`,
);
