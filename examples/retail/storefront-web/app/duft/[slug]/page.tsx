import type { Metadata } from "next";
import { notFound } from "next/navigation";

import AcquisitionAnalytics from "@/components/AcquisitionAnalytics";
import { accordLabel } from "@/lib/accordLabels";
import FragranceExplodedNotes from "@/components/FragranceExplodedNotes";
import FragranceIngredientOrbit from "@/components/FragranceIngredientOrbit";
import FragranceOffers from "@/components/FragranceOffers";
import MobileOfferBar from "@/components/MobileOfferBar";
import OfferSectionLink from "@/components/OfferSectionLink";
import FragranceVisual from "@/components/FragranceVisual";
import ImageAttribution from "@/components/ImageAttribution";
import FragranceVisualGallery from "@/components/FragranceVisualGallery";
import FragranceModel3D from "@/components/FragranceModel3D";
import FragranceSaveControls from "@/components/FragranceSaveControls";
import FragranceShareButton from "@/components/FragranceShareButton";
import NoteIcon from "@/components/NoteIcon";
import {
  LIVE_FRAGRANCES,
  comparisonPath,
  getLiveFragranceBySlug,
  getRelatedFragrances,
  isVerifiedProductTruthVisual,
  visualWorldFor,
  type RelatedFragranceKind,
  type StaticFragrance,
} from "@/lib/fragranceCatalog";
import { SITE_URL } from "@/lib/site";
import { noteLabel } from "@/lib/noteLabels";
import { targetLabel } from "@/lib/targetLabels";

export const dynamicParams = false;

type PageProps = {
  params: Promise<{
    slug: string;
  }>;
};

function relatedLabel(kind: RelatedFragranceKind): string {
  return {
    clone: "Sehr naher Duftstil",
    inspired: "Ähnlicher Duftstil",
    alternative: "Alternative",
    same_cluster: "Gleiche Duftfamilie",
    similar_profile: "Ähnliches Duftprofil",
  }[kind];
}

function scoreLevel(value: number | null): string {
  if (value == null) return "–";
  if (value <= 4) return "Niedrig";
  if (value <= 6) return "Mittel";
  return "Hoch";
}

function sharedAccordLabels(
  left: StaticFragrance,
  right: StaticFragrance,
  limit = 2,
): string[] {
  const rightAccords = new Set(
    right.accords.map((accord) => accord.toLowerCase()),
  );

  return left.accords
    .filter((accord) =>
      rightAccords.has(accord.toLowerCase()),
    )
    .slice(0, limit)
    .map(accordLabel);
}

function formatCheckedAt(value: string | null): string | null {
  if (!value) return null;

  const parsed = new Date(`${value}T00:00:00Z`);
  if (Number.isNaN(parsed.getTime())) return value;

  return parsed.toLocaleDateString("de-DE", {
    day: "2-digit",
    month: "2-digit",
    year: "numeric",
    timeZone: "UTC",
  });
}

function formatPrice(value: number | null): string {
  if (value == null) return "–";
  return new Intl.NumberFormat("de-DE", {
    style: "currency",
    currency: "EUR",
  }).format(value);
}

function formatCommunityRating(
  value: number | null,
  provisional = false,
): string | null {
  if (value == null) return null;

  const rating = `${value.toLocaleString("de-DE", {
    minimumFractionDigits: 1,
    maximumFractionDigits: 1,
  })}/10`;

  return provisional ? `${rating} (vorläufig)` : rating;
}

function noteSection(
  title: string,
  notes: string[],
) {
  if (!notes.length) return null;
  const stage =
    title === "Kopfnoten"
      ? "01"
      : title === "Herznoten"
        ? "02"
        : title === "Basisnoten"
          ? "03"
          : null;

  return (
    <div>
      <div className="flex items-center gap-2 text-[11px] font-semibold uppercase tracking-[0.08em] text-(--ink-soft)">
        {stage ? (
          <span
            aria-hidden
            className="grid h-6 w-6 place-items-center rounded-lg bg-(--accent-soft) text-[10px] tabular-nums text-(--accent-ink)"
          >
            {stage}
          </span>
        ) : null}
        {title}
      </div>
      <div className="mt-2 flex flex-wrap gap-2">
        {notes.map((note) => (
          <a
            key={note}
            href={`/duft?q=${encodeURIComponent(noteLabel(note))}`}
            className="inline-flex items-center gap-2 rounded-full border border-(--line) bg-(--well)/60 px-3 py-1.5 text-[12px] text-(--ink) transition hover:border-(--accent) hover:bg-(--accent-soft)/45"
            aria-label={`Weitere Düfte mit ${noteLabel(note)} entdecken`}
          >
            <NoteIcon note={note} className="h-4 w-4 shrink-0 text-(--accent-ink)" />
            {noteLabel(note)}
            <span aria-hidden className="text-(--ink-soft)">→</span>
          </a>
        ))}
      </div>
    </div>
  );
}

function ProfileRow({
  label,
  value,
}: {
  label: string;
  value: number | null;
}) {
  const safe = value == null ? 0 : Math.min(10, Math.max(0, value));

  return (
    <div>
      <div className="flex items-center justify-between gap-3 text-[12px]">
        <span className="font-medium text-(--ink)">
          {label}
        </span>
        <span className="text-(--ink-soft)">
          {scoreLevel(value)}
        </span>
      </div>
      <div className="mt-1.5 h-1.5 overflow-hidden rounded-full bg-(--well)">
        <div
          className="h-full rounded-full bg-(--ink)"
          style={{ width: `${safe * 10}%` }}
        />
      </div>
    </div>
  );
}

function descriptionFor(
  fragrance: StaticFragrance,
): string {
  const accords = fragrance.accords
    .slice(0, 3)
    .map(accordLabel)
    .join(", ");

  return [
    `${fragrance.brand} ${fragrance.name}`,
    fragrance.concentration,
    accords ? `Duftprofil: ${accords}` : null,
    formatCommunityRating(
      fragrance.community.rating_10,
      fragrance.community.provisional,
    )
      ? `${formatCommunityRating(
          fragrance.community.rating_10,
          fragrance.community.provisional,
        )} Community-Bewertung`
      : null,
  ]
    .filter(Boolean)
    .join(" · ");
}

export function generateStaticParams() {
  return LIVE_FRAGRANCES.map((fragrance) => ({
    slug: fragrance.slug,
  }));
}

export async function generateMetadata({
  params,
}: PageProps): Promise<Metadata> {
  const { slug } = await params;
  const fragrance = getLiveFragranceBySlug(slug);

  if (!fragrance) {
    return {
      title: "Duft nicht gefunden",
    };
  }

  const title =
    `${fragrance.brand} ${fragrance.name} – Duftprofil & Angebote`;
  const description = descriptionFor(fragrance);
  const canonical = `/duft/${fragrance.slug}`;
  const shareImage = isVerifiedProductTruthVisual(fragrance.preferred_visual)
    ? fragrance.preferred_visual?.url
    : null;

  return {
    title,
    description,
    alternates: {
      canonical,
    },
    openGraph: {
      type: "website",
      url: `${SITE_URL}${canonical}`,
      title,
      description,
      images: shareImage ? [shareImage] : undefined,
    },
    twitter: {
      card: shareImage ? "summary_large_image" : "summary",
      title,
      description,
      images: shareImage ? [shareImage] : undefined,
    },
  };
}

export default async function FragrancePage({
  params,
}: PageProps) {
  const { slug } = await params;
  const fragrance = getLiveFragranceBySlug(slug);

  if (!fragrance) notFound();

  const checkedAt = formatCheckedAt(
    fragrance.market.checked_at,
  );
  const productTruthVisual = fragrance.preferred_visual;
  const productTruthIsVerified =
    isVerifiedProductTruthVisual(productTruthVisual);
  const heroVisual =
    fragrance.presentation_visual || productTruthVisual;
  const heroIsProductTruth =
    isVerifiedProductTruthVisual(heroVisual);
  const visualTheme = visualWorldFor(fragrance);
  const related = getRelatedFragrances(
    fragrance,
    4,
  );
  const allNotes = [
    ...fragrance.notes.top,
    ...fragrance.notes.heart,
    ...fragrance.notes.base,
    ...fragrance.notes.key,
    ...fragrance.notes.supporting,
  ];
  const notePreview = allNotes.slice(0, 3);
  const sceneNotes = Array.from(
    new Set(
      [
        fragrance.notes.top[0],
        fragrance.notes.heart[0],
        fragrance.notes.base[0],
        fragrance.notes.key[0],
        fragrance.notes.supporting[0],
      ].filter((note): note is string => Boolean(note)),
    ),
  ).slice(0, 4);
  const phaseNotes = [
    { stage: "01", label: "Kopf", note: fragrance.notes.top[0] },
    { stage: "02", label: "Herz", note: fragrance.notes.heart[0] },
    { stage: "03", label: "Basis", note: fragrance.notes.base[0] },
  ].filter(
    (item): item is { stage: string; label: string; note: string } =>
      Boolean(item.note),
  );
  const visualGalleryAssetCount = new Set(
    fragrance.visuals
      .filter((asset) => asset.role !== "model_3d")
      .map((asset) => asset.url),
  ).size;
  const hasVisualGallery = visualGalleryAssetCount >= 2;
  const noteCount = new Set(allNotes).size;
  const canonicalUrl = `${SITE_URL}/duft/${fragrance.slug}`;
  const breadcrumbStructuredData = {
    "@context": "https://schema.org",
    "@type": "BreadcrumbList",
    itemListElement: [
      {
        "@type": "ListItem",
        position: 1,
        name: "DUFYND",
        item: SITE_URL,
      },
      {
        "@type": "ListItem",
        position: 2,
        name: "Düfte",
        item: `${SITE_URL}/duft`,
      },
      {
        "@type": "ListItem",
        position: 3,
        name: `${fragrance.brand} ${fragrance.name}`,
        item: canonicalUrl,
      },
    ],
  };
  const breadcrumbJson = JSON.stringify(
    breadcrumbStructuredData,
  ).replaceAll("<", "\\u003c");
  const verifiedProductImage =
    productTruthIsVerified && productTruthVisual?.url
      ? productTruthVisual.url.startsWith("http")
        ? productTruthVisual.url
        : `${SITE_URL}${productTruthVisual.url}`
      : null;
  const productStructuredData = {
    "@context": "https://schema.org",
    "@type": "Product",
    name: `${fragrance.brand} ${fragrance.name}`,
    sku: fragrance.product_id,
    category: "Parfum",
    url: canonicalUrl,
    description: descriptionFor(fragrance),
    brand: {
      "@type": "Brand",
      name: fragrance.brand,
    },
    ...(verifiedProductImage
      ? { image: [verifiedProductImage] }
      : {}),
    additionalProperty: [
      {
        "@type": "PropertyValue",
        name: "Konzentration",
        value: fragrance.concentration,
      },
      {
        "@type": "PropertyValue",
        name: "Füllmenge",
        value: `${fragrance.volume_ml} ml`,
      },
    ],
  };
  const productJson = JSON.stringify(
    productStructuredData,
  ).replaceAll("<", "\\u003c");

  return (
    <main className="dufynd-detail-page min-h-screen pb-24 text-(--ink) sm:pb-0">
      <script
        type="application/ld+json"
        dangerouslySetInnerHTML={{ __html: breadcrumbJson }}
      />
      <script
        type="application/ld+json"
        dangerouslySetInnerHTML={{ __html: productJson }}
      />
      <AcquisitionAnalytics source="fragrance_detail" />
      <header className="border-b border-(--line) bg-(--card)">
        <div className="mx-auto flex max-w-[1080px] items-center justify-between gap-4 px-4 py-4 sm:px-6">
          <a
            href="/"
            className="flex items-center gap-2.5"
            aria-label="Zur DUFYND Startseite"
          >
            <img
              src="/icon.svg"
              alt=""
              aria-hidden
              width={32}
              height={32}
              className="h-8 w-8 rounded-lg"
            />
            <span className="text-[17px] font-bold tracking-[-0.02em]">
              DUFYND
            </span>
          </a>
          <div className="flex items-center gap-2">
            <a
              href="/sammlung"
              className="hidden rounded-xl border border-(--line) px-3 py-2 text-[12px] font-semibold text-(--ink) transition hover:border-(--ink) sm:inline-flex"
            >
              Meine Sammlung
            </a>
            <a
              href="/"
              className="rounded-xl border border-(--line) px-3 py-2 text-[12px] font-semibold text-(--ink) transition hover:border-(--ink)"
            >
              Duftberatung öffnen
            </a>
          </div>
        </div>
      </header>

      <div className="mx-auto max-w-[1080px] px-4 py-5 sm:px-6 sm:py-8">
        <nav
          aria-label="Breadcrumb"
          className="mb-5 text-[12px] text-(--ink-soft)"
        >
          <a href="/" className="hover:underline">
            DUFYND
          </a>
          <span className="px-2">/</span>
          <a href="/duft" className="hover:underline">
            Düfte
          </a>
          <span className="px-2">/</span>
          <span className="text-(--ink)">
            {fragrance.brand} {fragrance.name}
          </span>
        </nav>

        <section
          className={`dufynd-fragrance-hero dufynd-fragrance-hero--${visualTheme} relative overflow-hidden rounded-[30px] border border-(--line) bg-(--card) shadow-(--shadow)`}
        >
          <div
            aria-hidden
            className="dufynd-fragrance-hero-atmosphere pointer-events-none absolute inset-0"
          />
          <div
            aria-hidden
            className="dufynd-fragrance-hero-orbit pointer-events-none absolute"
          />
          <div
            aria-hidden
            className="dufynd-fragrance-scene-beam pointer-events-none absolute"
          />
          <div
            aria-hidden
            className="dufynd-fragrance-scene-mist pointer-events-none absolute"
          />
          <div
            aria-hidden
            className="dufynd-fragrance-scene-particles pointer-events-none absolute inset-0"
          />
          <div className="dufynd-fragrance-hero-grid relative z-10 grid lg:grid-cols-[1.08fr_0.92fr]">
            <div className="dufynd-fragrance-identity dufynd-fragrance-panel-section dufynd-fragrance-panel-section--identity p-5 pb-4 sm:p-7 sm:pb-5 lg:col-start-2 lg:row-start-1 lg:p-9 lg:pb-0">
              <div className="text-[11px] font-semibold uppercase tracking-[0.14em] text-(--accent-ink)">
                {fragrance.brand}
              </div>
              <h1 className="mt-1.5 text-[32px] font-semibold leading-[1.05] tracking-[-0.045em] sm:text-[46px]">
                {fragrance.name}
              </h1>
              <div className="mt-3 flex flex-wrap gap-1.5 text-[11px] text-(--ink-soft) sm:gap-2 sm:text-[12px]">
                <span className="rounded-full border border-(--line) bg-(--surface) px-2.5 py-1.5 sm:px-3">
                  {fragrance.concentration}
                </span>
                <span className="rounded-full border border-(--line) bg-(--surface) px-2.5 py-1.5 sm:px-3">
                  {fragrance.volume_ml} ml
                </span>
                {fragrance.target_groups.map((group) => (
                  <span key={group} className="rounded-full border border-(--line) bg-(--surface) px-2.5 py-1.5 sm:px-3">
                    {targetLabel(group)}
                  </span>
                ))}
                {fragrance.release_year ? (
                  <span className="hidden rounded-full border border-(--line) bg-(--surface) px-2.5 py-1.5 sm:inline-flex sm:px-3">
                    Seit {fragrance.release_year}
                  </span>
                ) : null}
              </div>
              {fragrance.accords.length ? (
                <p className="mt-3 text-[11px] leading-4 text-(--ink-soft) sm:text-[12px]">
                  Duftcharakter: {fragrance.accords.slice(0, 3).map(accordLabel).join(" · ")}
                </p>
              ) : null}
              {fragrance.market.reference_price_eur != null ? (
                <p className="mt-2 text-[11px] leading-4 text-(--ink-soft)">
                  Preisreferenz {formatPrice(fragrance.market.reference_price_eur)}
                  {checkedAt ? ` · Stand ${checkedAt}` : ""} · aktuelle Angebote separat prüfen
                </p>
              ) : null}
              {fragrance.community.rating_10 != null ? (
                <p className="mt-2 text-[11px] leading-4 text-(--ink-soft)">
                  Community {fragrance.community.rating_10.toLocaleString("de-DE", { minimumFractionDigits: 1, maximumFractionDigits: 1 })}/10
                  {fragrance.community.rating_count
                    ? ` · ${fragrance.community.rating_count.toLocaleString("de-DE")} Bewertungen`
                    : ""}
                </p>
              ) : null}
              {heroIsProductTruth ? (
                <div className="mt-2">
                  <ImageAttribution visual={heroVisual} />
                </div>
              ) : null}
            </div>
            <div className="dufynd-fragrance-stage-shell relative min-h-[304px] overflow-hidden sm:min-h-[380px] lg:col-start-1 lg:row-span-2 lg:row-start-1 lg:min-h-[560px]">
              {fragrance.model_3d_url ? (
                <FragranceModel3D
                  modelUrl={fragrance.model_3d_url}
                  imageUrl={heroIsProductTruth ? undefined : heroVisual?.url}
                  cutoutUrl={heroIsProductTruth ? heroVisual?.url : undefined}
                  backdropUrl={
                    heroIsProductTruth
                      ? fragrance.backdrop_visual?.url
                      : undefined
                  }
                  alt={`${fragrance.brand} ${fragrance.name}`}
                  className="dufynd-fragrance-stage-visual absolute inset-0 h-full w-full"
                  priority
                />
              ) : (
                <FragranceVisual
                  imageUrl={heroVisual?.url}
                  cutoutUrl={heroIsProductTruth ? heroVisual?.url : undefined}
                  backdropUrl={
                    heroIsProductTruth
                      ? fragrance.backdrop_visual?.url
                      : undefined
                  }
                  alt={`${fragrance.brand} ${fragrance.name}`}
                  variant="hero"
                  mode={heroIsProductTruth ? "cutout" : "editorial"}
                  world={visualTheme}
                  className="dufynd-fragrance-stage-visual absolute inset-0 h-full w-full"
                  priority
                />
              )}

              <div
                aria-hidden
                className="dufynd-fragrance-stage-reflection"
              />

              {phaseNotes.length ? (
                <div
                  aria-hidden
                  className="dufynd-fragrance-phase-rail"
                >
                  {phaseNotes.map((phase) => (
                    <div
                      key={phase.stage}
                      className="dufynd-fragrance-phase"
                      data-dufynd-phase={phase.stage}
                    >
                      <span className="dufynd-fragrance-phase-index">
                        {phase.stage}
                      </span>
                      <span className="dufynd-fragrance-phase-copy">
                        <strong>{phase.label}</strong>
                        <em>{noteLabel(phase.note)}</em>
                      </span>
                    </div>
                  ))}
                </div>
              ) : null}

              <FragranceIngredientOrbit notes={sceneNotes} />

              <div
                aria-hidden
                className="dufynd-fragrance-stage-kicker"
              >
                <span>{fragrance.brand}</span>
                <strong>{fragrance.name}</strong>
              </div>
            </div>

            <div className="dufynd-fragrance-hero-copy dufynd-fragrance-panel-section dufynd-fragrance-panel-section--copy flex flex-col justify-center p-5 pt-4 sm:p-7 sm:pt-5 lg:col-start-2 lg:row-start-2 lg:p-9 lg:pt-3">
              <div className={`grid gap-2 sm:flex sm:flex-wrap sm:gap-2.5 ${related.length ? "grid-cols-2" : "grid-cols-1"}`}>
                <OfferSectionLink
                  id="dufynd-hero-offer-cta"
                  productId={fragrance.product_id}
                  source="hero_offer_cta"
                  className="rounded-xl bg-(--accent-strong) px-3 py-2.5 text-center text-[12px] font-semibold text-white shadow-sm transition hover:-translate-y-0.5 hover:brightness-95 sm:px-4 sm:text-[13px]"
                >
                  Angebote prüfen
                </OfferSectionLink>
                {related.length ? (
                  <a
                    href="#alternativen"
                    className="rounded-xl border border-(--line-strong) bg-(--surface) px-3 py-2.5 text-center text-[12px] font-semibold text-(--ink) transition hover:border-(--ink) sm:px-4 sm:text-[13px]"
                  >
                    Alternativen ansehen
                  </a>
                ) : null}
              </div>

              <div className="mt-4 flex flex-wrap items-center gap-2">
                <FragranceSaveControls
                  productId={fragrance.product_id}
                  compact
                />
                <FragranceShareButton
                  brand={fragrance.brand}
                  name={fragrance.name}
                />
                <a
                  href={`/vergleich?left=${encodeURIComponent(fragrance.product_id)}`}
                  className="rounded-lg border border-(--line) bg-(--surface) px-2.5 py-1.5 text-[11px] font-semibold text-(--accent-ink) transition hover:border-(--accent)"
                >
                  Mit anderem Duft vergleichen →
                </a>
              </div>

              <div className="mt-5 grid grid-cols-3 overflow-hidden rounded-2xl border border-(--line) bg-(--surface)">
                <div className="p-3 sm:p-4">
                  <div className="text-[10.5px] text-(--ink-soft)">
                    Community
                  </div>
                  <div className="mt-1 text-[19px] font-semibold tracking-[-0.03em] sm:text-[22px]">
                    {fragrance.community.rating_10 != null
                      ? `${fragrance.community.rating_10.toLocaleString(
                          "de-DE",
                          {
                            minimumFractionDigits: 1,
                            maximumFractionDigits: 1,
                          },
                        )}/10`
                      : "–"}
                  </div>
                  {fragrance.community.provisional ? (
                    <div className="mt-0.5 text-[9.5px] font-medium text-(--ink-soft)">
                      vorläufig
                    </div>
                  ) : null}
                </div>

                <div className="border-l border-(--line) p-3 sm:p-4">
                  <div className="text-[10.5px] text-(--ink-soft)">
                    Haltbarkeit
                  </div>
                  <div className="mt-1 text-[19px] font-semibold tracking-[-0.03em] sm:text-[22px]">
                    {fragrance.community.longevity_10 != null
                      ? fragrance.community.longevity_10.toLocaleString(
                          "de-DE",
                          {
                            minimumFractionDigits: 1,
                            maximumFractionDigits: 1,
                          },
                        )
                      : "–"}
                  </div>
                  {fragrance.community.provisional ? (
                    <div className="mt-0.5 text-[9.5px] font-medium text-(--ink-soft)">
                      vorläufig
                    </div>
                  ) : null}
                </div>

                <div className="border-l border-(--line) p-3 sm:p-4">
                  <div className="text-[10.5px] text-(--ink-soft)">
                    Ausstrahlung
                  </div>
                  <div className="mt-1 text-[19px] font-semibold tracking-[-0.03em] sm:text-[22px]">
                    {fragrance.community.projection_10 != null
                      ? fragrance.community.projection_10.toLocaleString(
                          "de-DE",
                          {
                            minimumFractionDigits: 1,
                            maximumFractionDigits: 1,
                          },
                        )
                      : "–"}
                  </div>
                  {fragrance.community.provisional ? (
                    <div className="mt-0.5 text-[9.5px] font-medium text-(--ink-soft)">
                      vorläufig
                    </div>
                  ) : null}
                </div>
              </div>

              <div className="mt-3 flex flex-wrap items-center gap-x-2 gap-y-1 text-[10.5px] leading-4 text-(--ink-soft)">
                <span>
                  {fragrance.community.source}
                  {fragrance.community.rating_count
                    ? ` · ${fragrance.community.rating_count.toLocaleString(
                        "de-DE",
                      )} Bewertungen`
                    : ""}
                </span>
                <span aria-hidden>·</span>
                <span>Community-Werte, keine Laborwerte</span>
              </div>

              <p className="mt-4 text-[10.5px] leading-4 text-(--ink-soft)">
                DUFYND verkauft nicht selbst. Kauf und Versand erfolgen beim jeweiligen Händler.
              </p>
              {heroVisual && !heroIsProductTruth ? (
                <p className="mt-2 text-[10.5px] leading-4 text-(--ink-soft)">
                  Bild: stilisierte DUFYND-Inszenierung. Details des Flakons können vom Original abweichen.
                </p>
              ) : null}
            </div>
          </div>
        </section>

        <nav
          aria-label="Schnellnavigation auf der Duftseite"
          className="dufynd-detail-quick-nav mt-3 overflow-x-auto rounded-2xl border border-(--line) bg-(--card)/95 p-2 shadow-(--shadow-sm) backdrop-blur sm:mt-4"
        >
          <div className="flex min-w-max items-center gap-1.5">
            <OfferSectionLink
              productId={fragrance.product_id}
              source="detail_quick_nav"
              className="rounded-xl bg-(--accent-strong) px-3 py-2 text-[11px] font-semibold text-white transition hover:brightness-95 sm:px-4 sm:text-[12px]"
            >
              Angebote
            </OfferSectionLink>
            <a
              href="#duftprofil"
              className="rounded-xl px-3 py-2 text-[11px] font-semibold text-(--ink) transition hover:bg-(--well) sm:px-4 sm:text-[12px]"
            >
              Duft-DNA · {fragrance.accords.length} Akkorde
            </a>
            <a
              href="#duftnoten"
              className="rounded-xl px-3 py-2 text-[11px] font-semibold text-(--ink) transition hover:bg-(--well) sm:px-4 sm:text-[12px]"
            >
              Duftnoten · {noteCount}
            </a>
            {related.length ? (
              <a
                href="#alternativen"
                className="rounded-xl px-3 py-2 text-[11px] font-semibold text-(--ink) transition hover:bg-(--well) sm:px-4 sm:text-[12px]"
              >
                Alternativen · {related.length}
              </a>
            ) : null}
          </div>
        </nav>

        <div className="dufynd-fragrance-journey">
          <div
            aria-hidden
            className="dufynd-fragrance-journey-axis"
          />

          <div
            id="angebote"
            className="dufynd-fragrance-chapter dufynd-fragrance-chapter--offers mt-5 scroll-mt-24"
            data-dufynd-chapter="angebote"
          >
            <span
              aria-hidden
              className="dufynd-fragrance-chapter-index"
            >
              01
            </span>
            <FragranceOffers productId={fragrance.product_id} />
          </div>

        {productTruthIsVerified && productTruthVisual?.url ? (
          <div
            className="dufynd-fragrance-chapter dufynd-fragrance-chapter--experience"
            data-dufynd-chapter="erleben"
          >
            <span
              aria-hidden
              className="dufynd-fragrance-chapter-index"
            >
              02
            </span>
            <FragranceExplodedNotes
              cutoutUrl={productTruthVisual.url}
              alt={`${fragrance.brand} ${fragrance.name}`}
              top={fragrance.notes.top}
              heart={fragrance.notes.heart}
              base={fragrance.notes.base}
              keyNotes={fragrance.notes.key}
              supporting={fragrance.notes.supporting}
            />
          </div>
        ) : null}

        {hasVisualGallery ? (
          <div
            className="dufynd-fragrance-chapter dufynd-fragrance-chapter--gallery"
            data-dufynd-chapter="ansichten"
          >
            <FragranceVisualGallery
              assets={fragrance.visuals}
              alt={`${fragrance.brand} ${fragrance.name}`}
            />
          </div>
        ) : null}

        <div
          className="dufynd-fragrance-chapter dufynd-fragrance-chapter--profile mt-5 grid gap-4 lg:mt-7 lg:grid-cols-[1.05fr_0.95fr]"
          data-dufynd-chapter="verstehen"
        >
          <span
            aria-hidden
            className="dufynd-fragrance-chapter-index"
          >
            03
          </span>
          <section
            id="duftprofil"
            className="dufynd-fragrance-profile-card scroll-mt-24 rounded-2xl border border-(--line) bg-(--card) p-4 shadow-(--shadow-sm) sm:p-5"
          >
            <h2 className="text-[17px] font-semibold">
              Duftprofil
            </h2>

            <div className="mt-3 flex flex-wrap gap-2">
              {fragrance.accords.map((accord) => (
                <a
                  key={accord}
                  href={`/duft?q=${encodeURIComponent(accordLabel(accord))}`}
                  className="rounded-full border border-transparent bg-(--well) px-3 py-1.5 text-[12px] text-(--ink) transition hover:border-(--accent) hover:bg-(--accent-soft)/45"
                  aria-label={`Weitere Düfte mit Duftcharakter ${accordLabel(accord)} entdecken`}
                >
                  {accordLabel(accord)} <span aria-hidden>→</span>
                </a>
              ))}
            </div>

            <div className="mt-4 grid gap-2.5 sm:mt-5 sm:grid-cols-2 sm:gap-3">
              <ProfileRow
                label="Frische"
                value={fragrance.scores.freshness}
              />
              <ProfileRow
                label="Süße"
                value={fragrance.scores.sweetness}
              />
              <ProfileRow
                label="Holzigkeit"
                value={fragrance.scores.woodiness}
              />
              <ProfileRow
                label="Würze"
                value={fragrance.scores.spiciness}
              />
            </div>

            <p className="mt-4 text-[10.5px] leading-4 text-(--ink-soft)">
              Die vier Profilachsen sind redaktionelle DUFYND-Merkmale,
              die zur Suche und Empfehlung genutzt werden. Sie sind keine
              Laborwerte.
            </p>
          </section>

          <div id="duftnoten" className="dufynd-fragrance-notes-card scroll-mt-24">
          <details className="group rounded-2xl border border-(--line) bg-(--card) p-4 shadow-(--shadow-sm) lg:hidden">
            <summary className="flex cursor-pointer list-none items-center justify-between gap-3">
              <span className="min-w-0">
                <span className="block text-[17px] font-semibold">
                  Duftnoten
                </span>
                {notePreview.length ? (
                  <span className="mt-1.5 flex flex-wrap gap-1.5 text-[10.5px] font-medium text-(--ink-soft)">
                    {notePreview.map((note) => (
                      <span
                        key={note}
                        className="inline-flex items-center gap-1 rounded-full bg-(--well) px-2 py-1"
                      >
                        <NoteIcon note={note} className="h-3.5 w-3.5" />
                        {noteLabel(note)}
                      </span>
                    ))}
                  </span>
                ) : null}
              </span>
              <span
                aria-hidden
                className="shrink-0 text-[18px] text-(--accent-ink) transition group-open:rotate-45"
              >
                +
              </span>
            </summary>
            <div className="mt-4 space-y-4">
              {fragrance.notes.top.length ||
              fragrance.notes.heart.length ||
              fragrance.notes.base.length ? (
                <>
                  {noteSection("Kopfnoten", fragrance.notes.top)}
                  {noteSection("Herznoten", fragrance.notes.heart)}
                  {noteSection("Basisnoten", fragrance.notes.base)}
                </>
              ) : (
                <>
                  {noteSection("Schlüsselnoten", fragrance.notes.key)}
                  {noteSection("Weitere Noten", fragrance.notes.supporting)}
                  {!fragrance.notes.key.length &&
                  !fragrance.notes.supporting.length ? (
                    <p className="text-[13px] leading-5 text-(--ink-soft)">
                      Für diesen Duft sind aktuell keine verifizierten
                      Duftnoten im DUFYND-Katalog hinterlegt.
                    </p>
                  ) : null}
                </>
              )}
            </div>
          </details>

          <section className="hidden rounded-2xl border border-(--line) bg-(--card) p-5 shadow-(--shadow-sm) lg:block">
            <h2 className="text-[17px] font-semibold">
              Duftnoten
            </h2>
            <div className="mt-4 space-y-4">
              {fragrance.notes.top.length ||
              fragrance.notes.heart.length ||
              fragrance.notes.base.length ? (
                <>
                  {noteSection("Kopfnoten", fragrance.notes.top)}
                  {noteSection("Herznoten", fragrance.notes.heart)}
                  {noteSection("Basisnoten", fragrance.notes.base)}
                </>
              ) : (
                <>
                  {noteSection("Schlüsselnoten", fragrance.notes.key)}
                  {noteSection("Weitere Noten", fragrance.notes.supporting)}
                  {!fragrance.notes.key.length &&
                  !fragrance.notes.supporting.length ? (
                    <p className="text-[13px] leading-5 text-(--ink-soft)">
                      Für diesen Duft sind aktuell keine verifizierten
                      Duftnoten im DUFYND-Katalog hinterlegt.
                    </p>
                  ) : null}
                </>
              )}
            </div>
          </section>
          </div>
        </div>
        </div>

        {related.length ? (
          <section
            id="alternativen"
            className="mt-5 scroll-mt-6 rounded-2xl border border-(--line) bg-(--card) p-5 shadow-(--shadow-sm)"
          >
            <div className="flex flex-wrap items-end justify-between gap-3">
              <div>
                <h2 className="text-[17px] font-semibold">
                  Ähnliche Düfte & Alternativen
                </h2>
                <p className="mt-1 max-w-2xl text-[11px] leading-4 text-(--ink-soft) sm:text-[12px] sm:leading-5">
                  Zuerst zeigt DUFYND dokumentierte Beziehungen aus dem
                  Duftkatalog. Weitere Vorschläge bleiben innerhalb
                  derselben Duftfamilie und werden dort nach Profilnähe
                  eingeordnet.
                </p>
              </div>
              <a
                href={`/vergleich?left=${encodeURIComponent(fragrance.product_id)}`}
                className="text-[12px] font-semibold text-(--accent-ink) hover:underline"
              >
                Mit diesem Duft vergleichen
              </a>
            </div>

            <div className="-mx-1 mt-4 flex snap-x gap-3 overflow-x-auto px-1 pb-2 sm:mx-0 sm:grid sm:grid-cols-2 sm:overflow-visible sm:px-0 sm:pb-0 lg:grid-cols-4">
              {related.map((item) => {
                const comparisonHref = comparisonPath(
                  fragrance,
                  item.fragrance,
                );
                const hasComparison = comparisonHref.startsWith(
                  "/vergleich/",
                );
                const relatedVisual =
                  item.fragrance.presentation_visual ||
                  item.fragrance.preferred_visual;
                const relatedIsProductTruth =
                  isVerifiedProductTruthVisual(relatedVisual);
                const sharedAccords = sharedAccordLabels(
                  fragrance,
                  item.fragrance,
                );

                return (
                  <article
                    key={item.fragrance.product_id}
                    className="min-w-[220px] snap-start overflow-hidden rounded-xl border border-(--line) bg-(--well)/35 sm:min-w-0"
                  >
                    <a
                      href={`/duft/${item.fragrance.slug}`}
                      className="block"
                    >
                      <FragranceVisual
                        imageUrl={relatedVisual?.url}
                        cutoutUrl={
                          relatedIsProductTruth
                            ? relatedVisual?.url
                            : undefined
                        }
                        backdropUrl={
                          relatedIsProductTruth
                            ? item.fragrance.backdrop_visual?.url
                            : undefined
                        }
                        alt={`${item.fragrance.brand} ${item.fragrance.name}`}
                        variant="card"
                        mode={
                          relatedIsProductTruth
                            ? "cutout"
                            : "editorial"
                        }
                        className="h-36 w-full"
                      />
                      <div className="p-3">
                        <div className="text-[10px] font-semibold uppercase tracking-[0.08em] text-(--ink-soft)">
                          {relatedLabel(item.kind)}
                        </div>
                        <div className="mt-1 text-[11px] text-(--ink-soft)">
                          {item.fragrance.brand}
                        </div>
                        <h3 className="mt-0.5 text-[14px] font-semibold leading-5 text-(--ink)">
                          {item.fragrance.name}
                        </h3>
                        {sharedAccords.length ? (
                          <div className="mt-2">
                            <div className="text-[9.5px] font-semibold uppercase tracking-[0.07em] text-(--ink-soft)">
                              Gemeinsame Akkorde
                            </div>
                            <div className="mt-1 flex flex-wrap gap-1">
                              {sharedAccords.map((accord) => (
                                <span
                                  key={accord}
                                  className="rounded-full border border-(--line) bg-(--card) px-2 py-0.5 text-[9.5px] font-medium text-(--ink-soft)"
                                >
                                  {accord}
                                </span>
                              ))}
                            </div>
                          </div>
                        ) : null}
                        {item.fragrance.community.rating_10 != null ? (
                          <div className="mt-2 text-[11px] text-(--ink-soft)">
                            <span className="font-semibold text-(--ink)">
                              {formatCommunityRating(
                                item.fragrance.community.rating_10,
                                item.fragrance.community.provisional,
                              )}
                            </span>
                            {" · "}
                            {item.fragrance.community.source}
                          </div>
                        ) : null}
                      </div>
                    </a>

                    {hasComparison ? (
                      <a
                        href={comparisonHref}
                        aria-label={`${fragrance.brand} ${fragrance.name} mit ${item.fragrance.brand} ${item.fragrance.name} vergleichen`}
                        className="block border-t border-(--line) px-3 py-2.5 text-[11px] font-semibold text-(--accent-ink) hover:bg-(--card)"
                      >
                        Direkt vergleichen →
                      </a>
                    ) : null}
                  </article>
                );
              })}
            </div>
          </section>
        ) : null}

        <section className="mt-5 rounded-2xl border border-(--line) bg-(--card) p-5 shadow-(--shadow-sm)">
          <div className="flex flex-wrap items-center justify-between gap-4">
            <div>
              <h2 className="text-[17px] font-semibold">
                Passt dieser Duft zu dir?
              </h2>
              <p className="mt-1 max-w-2xl text-[13px] leading-5 text-(--ink-soft)">
                Starte die DUFYND-Beratung und vergleiche diesen Duft
                mit Alternativen nach Budget, Anlass und Duftprofil.
              </p>
            </div>
            <a
              href="/"
              className="rounded-xl bg-(--ink) px-4 py-2.5 text-[13px] font-semibold text-(--surface)"
            >
              DUFYND Duftberater öffnen
            </a>
          </div>
        </section>

        <section className="mt-5 rounded-2xl border border-(--line) bg-(--well)/45 p-4 text-[11px] leading-5 text-(--ink-soft)">
          <strong className="text-(--ink)">
            Preisreferenz:
          </strong>{" "}
          {formatPrice(
            fragrance.market.reference_price_eur,
          )}
          {checkedAt ? ` · Stand ${checkedAt}` : ""}. Aktuelle
          kaufbare Angebote werden darüber separat geprüft und können
          von dieser Marktpreis-Referenz abweichen.
        </section>

        <footer className="mt-8 flex flex-wrap gap-x-4 gap-y-2 border-t border-(--line) py-6 text-[11px] text-(--ink-soft)">
          <a href="/transparenz" className="hover:underline">
            Transparenz
          </a>
          <a href="/impressum" className="hover:underline">
            Impressum
          </a>
          <a href="/datenschutz" className="hover:underline">
            Datenschutz
          </a>
          <a href="/bildnachweise" className="hover:underline">
            Bildnachweise
          </a>
        </footer>
      </div>

      <MobileOfferBar
        brand={fragrance.brand}
        name={fragrance.name}
        productId={fragrance.product_id}
      />
    </main>
  );
}
