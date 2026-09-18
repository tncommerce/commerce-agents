import catalog from "../../data/catalog.json";
import scentaiProducts from "../../data/scentai_products.json";

import { fragranceSlug } from "@/lib/fragranceSlug";

type CatalogRow = {
  product_id: string;
  title: string;
  image_url?: string | null;
  brand?: string | null;
  price: number;
  currency?: string;
  review_count?: number | null;
  category?: string | null;
  labels?: string[];
  attributes?: Record<string, string>;
  in_stock?: boolean;
  short_description?: string | null;
};

type SourceRow = {
  product_id: string;
  brand: string;
  name: string;
  concentration: string;
  volume_ml: number;
  release_year?: number | null;
  classification?: {
    scentai_target_groups?: string[];
  };
  notes?: {
    top?: string[];
    heart?: string[];
    base?: string[];
  };
  community?: {
    source?: string;
    rating_10?: number | null;
    rating_count?: number | null;
    longevity_10?: number | null;
    projection_10?: number | null;
  };
  fragrance_profile?: {
    community_accords?: string[];
    scores?: {
      freshness?: number;
      sweetness?: number;
      woodiness?: number;
      spiciness?: number;
    };
  };
  market?: {
    market_price_eur?: number | null;
    price_checked_at?: string | null;
  };
};

export interface StaticFragrance {
  product_id: string;
  slug: string;
  title: string;
  brand: string;
  name: string;
  concentration: string;
  volume_ml: number;
  release_year?: number | null;
  image_url?: string | null;
  short_description?: string | null;
  target_groups: string[];
  notes: {
    top: string[];
    heart: string[];
    base: string[];
  };
  community: {
    source: string;
    rating_10: number | null;
    rating_count: number;
    longevity_10: number | null;
    projection_10: number | null;
  };
  accords: string[];
  scores: {
    freshness: number | null;
    sweetness: number | null;
    woodiness: number | null;
    spiciness: number | null;
  };
  market: {
    reference_price_eur: number | null;
    checked_at: string | null;
  };
}

const sourceById = new Map(
  (scentaiProducts.products as SourceRow[]).map(
    (product) => [product.product_id, product],
  ),
);

function asNumber(value: string | undefined): number | null {
  if (value == null || value === "") return null;
  const parsed = Number(value);
  return Number.isFinite(parsed) ? parsed : null;
}

function catalogToFragrance(
  row: CatalogRow,
): StaticFragrance {
  const source = sourceById.get(row.product_id);
  const attributes = row.attributes || {};
  const brand = String(row.brand || source?.brand || "").trim();
  const name = String(
    attributes.canonical_name ||
      source?.name ||
      row.title,
  ).trim();

  const concentration = String(
    attributes.concentration ||
      source?.concentration ||
      "",
  ).trim();

  const volumeMl =
    asNumber(attributes.volume_ml) ??
    source?.volume_ml ??
    0;

  const targetGroups = source?.classification
    ?.scentai_target_groups?.length
    ? source.classification.scentai_target_groups
    : String(attributes.target_group || "")
        .split(",")
        .map((value) => value.trim())
        .filter(Boolean);

  const rating10 =
    source?.community?.rating_10 ??
    asNumber(attributes.community_rating_10);

  const ratingCount =
    source?.community?.rating_count ??
    Number(row.review_count || 0);

  const accords = source?.fragrance_profile
    ?.community_accords?.length
    ? source.fragrance_profile.community_accords
    : String(attributes.main_accords || "")
        .split(",")
        .map((value) => value.trim())
        .filter(Boolean);

  const scores = source?.fragrance_profile?.scores;

  return {
    product_id: row.product_id,
    slug: fragranceSlug(brand, name),
    title: row.title,
    brand,
    name,
    concentration,
    volume_ml: volumeMl,
    release_year: source?.release_year ?? null,
    image_url: row.image_url,
    short_description: row.short_description,
    target_groups: targetGroups,
    notes: {
      top: source?.notes?.top || [],
      heart: source?.notes?.heart || [],
      base: source?.notes?.base || [],
    },
    community: {
      source:
        source?.community?.source ||
        attributes.rating_source ||
        "Parfumo",
      rating_10: rating10,
      rating_count: ratingCount,
      longevity_10:
        source?.community?.longevity_10 ??
        asNumber(attributes.longevity),
      projection_10:
        source?.community?.projection_10 ??
        asNumber(attributes.projection),
    },
    accords,
    scores: {
      freshness:
        scores?.freshness ??
        asNumber(attributes.freshness),
      sweetness:
        scores?.sweetness ??
        asNumber(attributes.sweetness),
      woodiness:
        scores?.woodiness ??
        asNumber(attributes.woodiness),
      spiciness:
        scores?.spiciness ??
        asNumber(attributes.spiciness),
    },
    market: {
      reference_price_eur:
        source?.market?.market_price_eur ??
        asNumber(attributes.market_price_eur) ??
        row.price ??
        null,
      checked_at:
        source?.market?.price_checked_at ||
        attributes.price_checked_at ||
        null,
    },
  };
}

export const LIVE_FRAGRANCES: StaticFragrance[] = (
  catalog.products as CatalogRow[]
)
  .filter(
    (product) =>
      product.product_id.startsWith("SC-") &&
      product.category === "fragrance" &&
      product.in_stock !== false,
  )
  .map(catalogToFragrance);

const slugCounts = new Map<string, number>();

for (const fragrance of LIVE_FRAGRANCES) {
  slugCounts.set(
    fragrance.slug,
    (slugCounts.get(fragrance.slug) || 0) + 1,
  );
}

const duplicateSlugs = Array.from(slugCounts.entries())
  .filter(([, count]) => count > 1)
  .map(([slug]) => slug);

if (duplicateSlugs.length) {
  throw new Error(
    `Duplicate SCENTAI fragrance slugs: ${duplicateSlugs.join(", ")}`,
  );
}

const bySlug = new Map(
  LIVE_FRAGRANCES.map(
    (fragrance) => [fragrance.slug, fragrance],
  ),
);

export function getLiveFragranceBySlug(
  slug: string,
): StaticFragrance | null {
  return bySlug.get(slug) || null;
}
