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
  attributes?: Record<string, string | undefined>;
  in_stock?: boolean;
  short_description?: string | null;
};

export type FragranceVisualRole =
  | "primary"
  | "cutout"
  | "editorial"
  | "macro"
  | "model_3d";

export type FragranceVisualFidelity =
  | "verified"
  | "pending_review"
  | "editorial_only"
  | "rejected";

export type FragranceVisualComposition =
  | "product_scene"
  | "bottle_free_backdrop";

export interface FragranceVisualAsset {
  role: FragranceVisualRole;
  url: string;
  provenance?: string | null;
  fidelity_status: FragranceVisualFidelity;
  variant?: string | null;
  composition?: FragranceVisualComposition | null;
}

type SourceRow = {
  product_id: string;
  brand: string;
  name: string;
  concentration: string;
  volume_ml: number;
  release_year?: number | null;
  classification?: {
    scentai_target_groups?: string[];
    role?: string | null;
    cluster_id?: string | null;
  };
  notes?: {
    top?: string[];
    heart?: string[];
    base?: string[];
    key?: string[];
    supporting?: string[];
  };
  community?: {
    source?: string;
    rating_10?: number | null;
    rating_count?: number | null;
    longevity_10?: number | null;
    projection_10?: number | null;
    provisional?: boolean;
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
  relationships?: {
    related_product_id: string;
    relationship_type: string;
    confidence?: string | null;
  }[];
  visuals?: FragranceVisualAsset[];
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
  cutout_image_url?: string | null;
  model_3d_url?: string | null;
  visuals: FragranceVisualAsset[];
  preferred_visual: FragranceVisualAsset | null;
  backdrop_visual: FragranceVisualAsset | null;
  short_description?: string | null;
  target_groups: string[];
  role: string | null;
  cluster_id: string | null;
  relationships: {
    related_product_id: string;
    relationship_type: string;
    confidence: string | null;
  }[];
  notes: {
    top: string[];
    heart: string[];
    base: string[];
    key: string[];
    supporting: string[];
  };
  community: {
    source: string;
    rating_10: number | null;
    rating_count: number;
    longevity_10: number | null;
    projection_10: number | null;
    provisional: boolean;
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
  (scentaiProducts.products as unknown as SourceRow[]).map(
    (product) => [product.product_id, product],
  ),
);

function asNumber(value: string | undefined): number | null {
  if (value == null || value === "") return null;
  const parsed = Number(value);
  return Number.isFinite(parsed) ? parsed : null;
}

const VARIANT_BOUND_VERIFIED_ROLES = new Set<FragranceVisualRole>([
  "primary",
  "cutout",
  "macro",
  "model_3d",
]);

function normalizedVariant(value: string | null | undefined): string {
  return String(value || "")
    .trim()
    .toLowerCase()
    .replace(/\s+/g, "");
}

function visualMatchesProductVariant(
  source: SourceRow | undefined,
  visual: FragranceVisualAsset,
): boolean {
  if (
    visual.fidelity_status !== "verified" ||
    !VARIANT_BOUND_VERIFIED_ROLES.has(visual.role)
  ) {
    return true;
  }

  if (!source?.volume_ml) return false;

  return (
    normalizedVariant(visual.variant) ===
    normalizedVariant(`${source.volume_ml}ml`)
  );
}

function activeVisuals(source: SourceRow | undefined): FragranceVisualAsset[] {
  return (source?.visuals || []).filter(
    (visual) =>
      Boolean(visual.url?.trim()) &&
      visual.fidelity_status !== "rejected" &&
      visual.fidelity_status !== "pending_review" &&
      visualMatchesProductVariant(source, visual),
  );
}

export function isVerifiedProductTruthVisual(
  visual: FragranceVisualAsset | null | undefined,
): boolean {
  return Boolean(
    visual &&
      visual.fidelity_status === "verified" &&
      (visual.role === "primary" || visual.role === "cutout"),
  );
}

function selectVerifiedModel3D(
  visuals: FragranceVisualAsset[],
): FragranceVisualAsset | null {
  return (
    visuals.find(
      (visual) =>
        visual.role === "model_3d" &&
        visual.fidelity_status === "verified",
    ) || null
  );
}

function selectBottleFreeBackdrop(
  visuals: FragranceVisualAsset[],
): FragranceVisualAsset | null {
  return (
    visuals.find(
      (visual) =>
        visual.role === "editorial" &&
        visual.composition === "bottle_free_backdrop" &&
        visual.fidelity_status === "editorial_only",
    ) || null
  );
}

function selectPreferredVisual(
  visuals: FragranceVisualAsset[],
  editorialFallback?: string | null,
  legacyCutoutFallback?: string | null,
): FragranceVisualAsset | null {
  const verifiedPrimary = visuals.find(
    (visual) =>
      visual.role === "primary" &&
      visual.fidelity_status === "verified",
  );
  if (verifiedPrimary) return verifiedPrimary;

  const verifiedCutout = visuals.find(
    (visual) =>
      visual.role === "cutout" &&
      visual.fidelity_status === "verified",
  );
  if (verifiedCutout) return verifiedCutout;

  const editorial = visuals.find(
    (visual) => visual.role === "editorial",
  );
  if (editorial) return editorial;

  const editorialUrl = editorialFallback?.trim();
  if (editorialUrl) {
    return {
      role: "editorial",
      url: editorialUrl,
      provenance: "legacy_catalog",
      fidelity_status: "editorial_only",
    };
  }

  const legacyCutoutUrl = legacyCutoutFallback?.trim();
  if (legacyCutoutUrl) {
    return {
      role: "cutout",
      url: legacyCutoutUrl,
      provenance: "legacy_catalog",
      fidelity_status: "pending_review",
    };
  }

  return null;
}

function catalogToFragrance(
  row: CatalogRow,
): StaticFragrance {
  const source = sourceById.get(row.product_id);
  const attributes = row.attributes || {};
  const legacyCutoutUrl =
    String(attributes.product_cutout_url || "").trim() || null;
  const visuals = activeVisuals(source);
  const preferredVisual = selectPreferredVisual(
    visuals,
    row.image_url,
    legacyCutoutUrl,
  );
  const verifiedModel3D = selectVerifiedModel3D(visuals);
  const backdropVisual = selectBottleFreeBackdrop(visuals);
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
    cutout_image_url: legacyCutoutUrl,
    model_3d_url: verifiedModel3D?.url || null,
    visuals,
    preferred_visual: preferredVisual,
    backdrop_visual: backdropVisual,
    short_description: row.short_description,
    target_groups: targetGroups,
    role: source?.classification?.role || null,
    cluster_id: source?.classification?.cluster_id || null,
    relationships: (source?.relationships || []).map(
      (relationship) => ({
        related_product_id: relationship.related_product_id,
        relationship_type: relationship.relationship_type,
        confidence: relationship.confidence || null,
      }),
    ),
    notes: {
      top: source?.notes?.top || [],
      heart: source?.notes?.heart || [],
      base: source?.notes?.base || [],
      key: source?.notes?.key || [],
      supporting: source?.notes?.supporting || [],
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
      provisional: source?.community?.provisional === true,
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
    `Duplicate DUFYND fragrance slugs: ${duplicateSlugs.join(", ")}`,
  );
}

const bySlug = new Map(
  LIVE_FRAGRANCES.map(
    (fragrance) => [fragrance.slug, fragrance],
  ),
);

export type RelatedFragranceKind =
  | "clone"
  | "inspired"
  | "alternative"
  | "same_cluster"
  | "similar_profile";

export interface RelatedFragrance {
  fragrance: StaticFragrance;
  kind: RelatedFragranceKind;
  confidence: string | null;
  similarity_score: number;
}

const byProductId = new Map(
  LIVE_FRAGRANCES.map(
    (fragrance) => [fragrance.product_id, fragrance],
  ),
);

const confidenceRank: Record<string, number> = {
  high: 4,
  medium_high: 3,
  medium: 2,
  low: 1,
};

function explicitRelationship(
  left: StaticFragrance,
  right: StaticFragrance,
): {
  kind: RelatedFragranceKind;
  confidence: string | null;
} | null {
  const candidates = [
    ...left.relationships
      .filter(
        (relationship) =>
          relationship.related_product_id === right.product_id,
      ),
    ...right.relationships
      .filter(
        (relationship) =>
          relationship.related_product_id === left.product_id,
      ),
  ];

  if (!candidates.length) return null;

  candidates.sort(
    (a, b) =>
      (confidenceRank[b.confidence || ""] || 0) -
      (confidenceRank[a.confidence || ""] || 0),
  );

  const selected = candidates[0];
  const kind = selected.relationship_type as RelatedFragranceKind;

  if (!["clone", "inspired", "alternative"].includes(kind)) {
    return null;
  }

  return {
    kind,
    confidence: selected.confidence || null,
  };
}

function profileSimilarity(
  left: StaticFragrance,
  right: StaticFragrance,
): number {
  const leftAccords = new Set(
    left.accords.map((accord) => accord.toLowerCase()),
  );
  const rightAccords = new Set(
    right.accords.map((accord) => accord.toLowerCase()),
  );

  const sharedAccords = [...leftAccords].filter(
    (accord) => rightAccords.has(accord),
  ).length;

  const leftTargets = new Set(left.target_groups);
  const sharedTargets = right.target_groups.filter(
    (target) => leftTargets.has(target),
  ).length;

  const axes = [
    "freshness",
    "sweetness",
    "woodiness",
    "spiciness",
  ] as const;

  let profileCloseness = 0;

  for (const axis of axes) {
    const leftValue = left.scores[axis];
    const rightValue = right.scores[axis];

    if (leftValue == null || rightValue == null) continue;

    profileCloseness +=
      Math.max(0, 10 - Math.abs(leftValue - rightValue)) / 10;
  }

  return (
    sharedAccords * 3 +
    sharedTargets * 1.5 +
    profileCloseness
  );
}

export function getRelatedFragrances(
  fragrance: StaticFragrance,
  limit = 4,
): RelatedFragrance[] {
  const candidates = LIVE_FRAGRANCES
    .filter(
      (candidate) =>
        candidate.product_id !== fragrance.product_id,
    )
    .map((candidate) => {
      const explicit = explicitRelationship(
        fragrance,
        candidate,
      );
      const sameCluster =
        Boolean(fragrance.cluster_id) &&
        fragrance.cluster_id === candidate.cluster_id;

      // Product-detail recommendations are trust-sensitive. Do not mix in
      // unrelated cross-cluster fragrances just because a few broad accords
      // overlap. Cross-cluster candidates need an explicit documented
      // relationship; otherwise only the same fragrance family is eligible.
      if (!explicit && !sameCluster) {
        return null;
      }

      const similarity = profileSimilarity(
        fragrance,
        candidate,
      );

      return {
        fragrance: candidate,
        kind: explicit?.kind || "same_cluster",
        confidence: explicit?.confidence || null,
        similarity_score:
          (explicit ? 100 : 0) +
          (sameCluster ? 25 : 0) +
          similarity,
      } satisfies RelatedFragrance;
    })
    .filter(
      (candidate): candidate is RelatedFragrance =>
        candidate !== null,
    )
    .sort(
      (a, b) =>
        b.similarity_score - a.similarity_score ||
        b.fragrance.community.rating_count -
          a.fragrance.community.rating_count,
    );

  return candidates.slice(0, limit);
}

export interface ExplicitComparisonPair {
  left: StaticFragrance;
  right: StaticFragrance;
  kind: "clone" | "inspired" | "alternative";
  confidence: string | null;
  pair_slug: string;
}

export function comparisonPairSlug(
  left: StaticFragrance,
  right: StaticFragrance,
): string {
  return [left.slug, right.slug]
    .sort((a, b) => a.localeCompare(b))
    .join("-vs-");
}

const comparisonPairMap = new Map<
  string,
  ExplicitComparisonPair
>();

for (const fragrance of LIVE_FRAGRANCES) {
  for (const relationship of fragrance.relationships) {
    const related = byProductId.get(
      relationship.related_product_id,
    );

    if (!related) continue;
    if (
      !["clone", "inspired", "alternative"].includes(
        relationship.relationship_type,
      )
    ) {
      continue;
    }

    const pairSlug = comparisonPairSlug(
      fragrance,
      related,
    );

    const candidate: ExplicitComparisonPair = {
      left: fragrance.slug.localeCompare(related.slug) <= 0
        ? fragrance
        : related,
      right: fragrance.slug.localeCompare(related.slug) <= 0
        ? related
        : fragrance,
      kind: relationship.relationship_type as
        ExplicitComparisonPair["kind"],
      confidence: relationship.confidence || null,
      pair_slug: pairSlug,
    };

    const existing = comparisonPairMap.get(pairSlug);
    const existingRank =
      confidenceRank[existing?.confidence || ""] || 0;
    const candidateRank =
      confidenceRank[candidate.confidence || ""] || 0;

    if (!existing || candidateRank > existingRank) {
      comparisonPairMap.set(pairSlug, candidate);
    }
  }
}

export const EXPLICIT_COMPARISON_PAIRS =
  [...comparisonPairMap.values()].sort(
    (a, b) => a.pair_slug.localeCompare(b.pair_slug),
  );

export function getComparisonPair(
  pairSlug: string,
): ExplicitComparisonPair | null {
  return comparisonPairMap.get(pairSlug) || null;
}

export function comparisonPath(
  left: StaticFragrance,
  right: StaticFragrance,
): string {
  const pairSlug = comparisonPairSlug(left, right);

  return comparisonPairMap.has(pairSlug)
    ? `/vergleich/${pairSlug}`
    : `/duft/${right.slug}`;
}

export function getLiveFragranceBySlug(
  slug: string,
): StaticFragrance | null {
  return bySlug.get(slug) || null;
}

export function getLiveFragranceByProductId(
  productId: string,
): StaticFragrance | null {
  return byProductId.get(productId) || null;
}
