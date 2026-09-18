import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const here = path.dirname(fileURLToPath(import.meta.url));
const storefrontRoot = path.resolve(here, "..");
const dataRoot = path.resolve(storefrontRoot, "..", "data");
const publicRoot = path.join(storefrontRoot, "public");
const strict = process.argv.includes("--strict");

function readJson(fileName) {
  return JSON.parse(
    fs.readFileSync(path.join(dataRoot, fileName), "utf8"),
  );
}

function env(name) {
  return String(process.env[name] || "").trim();
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

function validHttpUrl(value, { requireHttps = true } = {}) {
  try {
    const parsed = new URL(value);
    if (requireHttps) return parsed.protocol === "https:";
    return ["http:", "https:"].includes(parsed.protocol);
  } catch {
    return false;
  }
}

const checks = [];

function add(status, id, message) {
  checks.push({ status, id, message });
}

const catalog = readJson("catalog.json");
const source = readJson("scentai_products.json");
const merchantOffers = readJson("merchant_offers.json");
const merchantPartners = readJson("merchant_partners.json");

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

if (liveProducts.length > 0) {
  add(
    "pass",
    "live_catalog",
    `${liveProducts.length} live fragrances are available.`,
  );
} else {
  add("gate", "live_catalog", "No live fragrances are available.");
}

const slugCounts = new Map();
const missingSourceRows = [];
const missingImages = [];

for (const product of liveProducts) {
  const sourceProduct = sourceById.get(product.product_id);
  if (!sourceProduct) missingSourceRows.push(product.product_id);

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

  slugCounts.set(slug, (slugCounts.get(slug) || 0) + 1);

  const imageUrl = String(product.image_url || "").trim();
  if (!imageUrl) {
    missingImages.push(`${product.product_id}: no image_url`);
  } else if (imageUrl.startsWith("/")) {
    const imagePath = path.join(
      publicRoot,
      imageUrl.replace(/^\/+/, ""),
    );
    if (!fs.existsSync(imagePath)) {
      missingImages.push(
        `${product.product_id}: ${imageUrl}`,
      );
    }
  }
}

const duplicateSlugs = [...slugCounts.entries()]
  .filter(([, count]) => count > 1)
  .map(([slug]) => slug);

add(
  duplicateSlugs.length ? "gate" : "pass",
  "unique_slugs",
  duplicateSlugs.length
    ? `Duplicate fragrance slugs: ${duplicateSlugs.join(", ")}`
    : "All live fragrance slugs are unique.",
);

add(
  missingSourceRows.length ? "gate" : "pass",
  "source_coverage",
  missingSourceRows.length
    ? `Missing scentai_products rows: ${missingSourceRows.join(", ")}`
    : "Every live fragrance has a source-data row.",
);

add(
  missingImages.length ? "gate" : "pass",
  "image_coverage",
  missingImages.length
    ? `Missing live product images: ${missingImages.join("; ")}`
    : "Every live fragrance has a resolvable product image.",
);

const apiUrl = env("NEXT_PUBLIC_API_URL");
add(
  validHttpUrl(apiUrl)
    ? "pass"
    : "gate",
  "public_api_url",
  validHttpUrl(apiUrl)
    ? `Public API URL is HTTPS: ${apiUrl}`
    : "NEXT_PUBLIC_API_URL must be configured with an HTTPS public API URL.",
);

const siteUrl = env("NEXT_PUBLIC_SITE_URL");
add(
  validHttpUrl(siteUrl)
    ? "pass"
    : "gate",
  "site_url",
  validHttpUrl(siteUrl)
    ? `Canonical site URL is HTTPS: ${siteUrl}`
    : "NEXT_PUBLIC_SITE_URL must be configured with the canonical HTTPS site URL.",
);

const legalFields = [
  "NEXT_PUBLIC_LEGAL_BUSINESS_NAME",
  "NEXT_PUBLIC_LEGAL_OWNER_NAME",
  "NEXT_PUBLIC_LEGAL_STREET",
  "NEXT_PUBLIC_LEGAL_POSTCODE",
  "NEXT_PUBLIC_LEGAL_CITY",
  "NEXT_PUBLIC_LEGAL_EMAIL",
];
const missingLegalFields = legalFields.filter(
  (name) => !env(name),
);

add(
  missingLegalFields.length ? "gate" : "pass",
  "legal_identity",
  missingLegalFields.length
    ? `Missing legal environment fields: ${missingLegalFields.join(", ")}`
    : "Public legal identity fields are configured.",
);

const indexable =
  env("NEXT_PUBLIC_SITE_INDEXABLE") === "true";
add(
  indexable ? "pass" : "gate",
  "search_indexing",
  indexable
    ? "Search-engine indexing is enabled."
    : "NEXT_PUBLIC_SITE_INDEXABLE is not true; launch remains intentionally noindex.",
);

const offers = merchantOffers.offers || [];
const now = Date.now();
const eligibleOffers = offers.filter((offer) => {
  const checkedAt = Date.parse(offer.last_updated_at || "");
  const ageHours = Number.isFinite(checkedAt)
    ? (now - checkedAt) / 3_600_000
    : Number.POSITIVE_INFINITY;

  return (
    offer.in_stock !== false &&
    Number(offer.price) > 0 &&
    ageHours >= 0 &&
    ageHours <= 72
  );
});

add(
  eligibleOffers.length ? "pass" : "warn",
  "merchant_offer_freshness",
  eligibleOffers.length
    ? `${eligibleOffers.length} merchant offers are within the 72-hour freshness gate.`
    : "No merchant offers are currently within the 72-hour freshness gate; product discovery still works but active offers may be empty.",
);

const affiliateOffers = eligibleOffers.filter(
  (offer) => String(offer.affiliate_url || "").trim(),
);
add(
  affiliateOffers.length ? "pass" : "warn",
  "affiliate_offer_coverage",
  affiliateOffers.length
    ? `${affiliateOffers.length} fresh affiliate offers are available.`
    : "No fresh affiliate offers are active yet; monetization is not a launch blocker for recommendation quality.",
);

const activeMerchantPartners = (
  merchantPartners.partners || []
).filter(
  (partner) =>
    partner.status === "active" &&
    validHttpUrl(
      String(partner.affiliate_url || ""),
    ) &&
    partner.last_verified_at,
);
add(
  activeMerchantPartners.length ? "pass" : "warn",
  "merchant_level_affiliate_links",
  activeMerchantPartners.length
    ? `${activeMerchantPartners.length} merchant-level affiliate entry points are configured.`
    : "No merchant-level affiliate entry point is active yet; the UI stays hidden until a verified partner link is configured.",
);

if (
  validHttpUrl(siteUrl) &&
  new URL(siteUrl).hostname.endsWith(".onrender.com")
) {
  add(
    "warn",
    "custom_domain",
    "Canonical URL still uses the Render hostname. A custom domain is optional for technical launch but recommended before broad marketing.",
  );
} else if (validHttpUrl(siteUrl)) {
  add("pass", "custom_domain", "Canonical URL uses a non-Render host.");
}

const order = { gate: 0, warn: 1, pass: 2 };
checks.sort(
  (a, b) =>
    order[a.status] - order[b.status] ||
    a.id.localeCompare(b.id),
);

const counts = {
  gate: checks.filter((check) => check.status === "gate").length,
  warn: checks.filter((check) => check.status === "warn").length,
  pass: checks.filter((check) => check.status === "pass").length,
};

console.log(
  `SCENTAI launch readiness | pass=${counts.pass} | warn=${counts.warn} | gate=${counts.gate}`,
);
for (const check of checks) {
  console.log(
    `[${check.status.toUpperCase()}] ${check.id}: ${check.message}`,
  );
}

if (strict && counts.gate > 0) {
  process.exitCode = 1;
}
