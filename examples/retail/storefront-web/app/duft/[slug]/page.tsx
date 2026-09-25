import type { Metadata } from "next";
import { notFound } from "next/navigation";

import AcquisitionAnalytics from "@/components/AcquisitionAnalytics";
import FragranceExplodedNotes from "@/components/FragranceExplodedNotes";
import FragranceOffers from "@/components/FragranceOffers";
import FragranceVisual from "@/components/FragranceVisual";
import FragranceVisualGallery from "@/components/FragranceVisualGallery";
import FragranceModel3D from "@/components/FragranceModel3D";
import FragranceSaveControls from "@/components/FragranceSaveControls";
import NoteIcon from "@/components/NoteIcon";
import {
  LIVE_FRAGRANCES,
  comparisonPath,
  getLiveFragranceBySlug,
  getRelatedFragrances,
  isVerifiedProductTruthVisual,
  type RelatedFragranceKind,
  type StaticFragrance,
} from "@/lib/fragranceCatalog";
import { SITE_URL } from "@/lib/site";
import { noteLabel } from "@/lib/noteLabels";

export const dynamicParams = false;

type PageProps = {
  params: Promise<{
    slug: string;
  }>;
};

const ACCORD_LABELS: Record<string, string> = {
  fresh: "Frisch",
  citrus: "Zitrisch",
  aquatic: "Aquatisch",
  green: "Grün",
  spicy: "Würzig",
  sweet: "Süß",
  synthetic: "Synthetisch",
  fruity: "Fruchtig",
  woody: "Holzig",
  smoky: "Rauchig",
  powdery: "Pudrig",
  floral: "Blumig",
  creamy: "Cremig",
  gourmand: "Gourmand",
  oriental: "Orientalisch",
  aromatic: "Aromatisch",
  leathery: "Ledrig",
  resinous: "Harzig",
};

const TARGET_LABELS: Record<string, string> = {
  men: "Herren",
  women: "Damen",
  unisex: "Unisex",
};

function accordLabel(value: string): string {
  return ACCORD_LABELS[value.toLowerCase()] || value;
}

type FragranceVisualTheme =
  | "amber"
  | "mineral"
  | "ember"
  | "silk"
  | "noir";

function visualThemeFor(fragrance: StaticFragrance): FragranceVisualTheme {
  const accords = new Set(
    fragrance.accords.map((accord) => accord.toLowerCase()),
  );

  if (
    accords.has("smoky") ||
    accords.has("leathery") ||
    accords.has("resinous")
  ) {
    return "noir";
  }

  if (
    accords.has("gourmand") ||
    accords.has("sweet") ||
    accords.has("oriental") ||
    accords.has("creamy")
  ) {
    return "amber";
  }

  if (
    accords.has("floral") ||
    accords.has("powdery")
  ) {
    return "silk";
  }

  if (
    accords.has("fresh") ||
    accords.has("citrus") ||
    accords.has("aquatic") ||
    accords.has("green")
  ) {
    return "mineral";
  }

  return "ember";
}

function targetLabel(value: string): string {
  return TARGET_LABELS[value.toLowerCase()] || value;
}

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
          <span
            key={note}
            className="inline-flex items-center gap-2 rounded-full border border-(--line) bg-(--well)/60 px-3 py-1.5 text-[12px] text-(--ink)"
          >
            <NoteIcon note={note} className="h-4 w-4 shrink-0 text-(--accent-ink)" />
            {noteLabel(note)}
          </span>
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
    fragrance.community.rating_10 != null
      ? `${fragrance.community.rating_10.toLocaleString("de-DE", {
          minimumFractionDigits: 1,
          maximumFractionDigits: 1,
        })}/10 Community-Bewertung`
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
      images: fragrance.preferred_visual?.url
        ? [fragrance.preferred_visual.url]
        : undefined,
    },
    twitter: {
      card: fragrance.preferred_visual?.url
        ? "summary_large_image"
        : "summary",
      title,
      description,
      images: fragrance.preferred_visual?.url
        ? [fragrance.preferred_visual.url]
        : undefined,
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
  const heroVisual = fragrance.preferred_visual;
  const heroIsProductTruth =
    isVerifiedProductTruthVisual(heroVisual);
  const visualTheme = visualThemeFor(fragrance);
  const related = getRelatedFragrances(
    fragrance,
    4,
  );
  const notePreview = [
    ...fragrance.notes.top,
    ...fragrance.notes.heart,
    ...fragrance.notes.base,
    ...fragrance.notes.key,
    ...fragrance.notes.supporting,
  ].slice(0, 3);
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
    heroIsProductTruth && heroVisual?.url
      ? heroVisual.url.startsWith("http")
        ? heroVisual.url
        : `${SITE_URL}${heroVisual.url}`
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
    <main className="min-h-screen bg-(--surface) pb-24 text-(--ink) sm:pb-0">
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
          <div className="relative z-10 grid lg:grid-cols-[0.94fr_1.06fr]">
            {fragrance.model_3d_url || heroIsProductTruth ? (
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
                className="min-h-[330px] w-full sm:min-h-[430px] lg:min-h-[520px]"
                priority
              />
            ) : (
              <FragranceVisual
                imageUrl={heroVisual?.url}
                alt={`${fragrance.brand} ${fragrance.name}`}
                variant="hero"
                mode="editorial"
                className="min-h-[330px] w-full sm:min-h-[430px] lg:min-h-[520px]"
                priority
              />
            )}

            <div className="dufynd-fragrance-hero-copy flex flex-col justify-center p-5 sm:p-7 lg:p-9">
              <div className="text-[11px] font-semibold uppercase tracking-[0.14em] text-(--accent-ink)">
                {fragrance.brand}
              </div>
              <h1 className="mt-2 text-[34px] font-semibold leading-[1.02] tracking-[-0.045em] sm:text-[46px]">
                {fragrance.name}
              </h1>

              <div className="mt-4 flex flex-wrap gap-1.5 text-[11px] text-(--ink-soft) sm:gap-2 sm:text-[12px]">
                <span className="rounded-full border border-(--line) bg-(--surface) px-2.5 py-1.5 sm:px-3">
                  {fragrance.concentration}
                </span>
                <span className="rounded-full border border-(--line) bg-(--surface) px-2.5 py-1.5 sm:px-3">
                  {fragrance.volume_ml} ml
                </span>
                {fragrance.target_groups.map((group) => (
                  <span
                    key={group}
                    className="rounded-full border border-(--line) bg-(--surface) px-2.5 py-1.5 sm:px-3"
                  >
                    {targetLabel(group)}
                  </span>
                ))}
                {fragrance.release_year ? (
                  <span className="rounded-full border border-(--line) bg-(--surface) px-2.5 py-1.5 sm:px-3">
                    Seit {fragrance.release_year}
                  </span>
                ) : null}
              </div>

              <div className="mt-5 grid grid-cols-2 gap-2 sm:flex sm:flex-wrap sm:gap-2.5">
                <a
                  href="#angebote"
                  className="rounded-xl bg-(--accent-strong) px-3 py-2.5 text-center text-[12px] font-semibold text-white shadow-sm transition hover:-translate-y-0.5 hover:brightness-95 sm:px-4 sm:text-[13px]"
                >
                  Angebote prüfen
                </a>
                {related.length ? (
                  <a
                    href="#alternativen"
                    className="rounded-xl border border-(--line-strong) bg-(--surface) px-3 py-2.5 text-center text-[12px] font-semibold text-(--ink) transition hover:border-(--ink) sm:px-4 sm:text-[13px]"
                  >
                    Alternativen ansehen
                  </a>
                ) : null}
              </div>

              <div className="mt-4">
                <FragranceSaveControls
                  productId={fragrance.product_id}
                  compact
                />
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

        {heroIsProductTruth && heroVisual?.url ? (
          <FragranceExplodedNotes
            cutoutUrl={heroVisual.url}
            alt={`${fragrance.brand} ${fragrance.name}`}
            top={fragrance.notes.top}
            heart={fragrance.notes.heart}
            base={fragrance.notes.base}
            keyNotes={fragrance.notes.key}
            supporting={fragrance.notes.supporting}
          />
        ) : null}

        <FragranceVisualGallery
          assets={fragrance.visuals}
          alt={`${fragrance.brand} ${fragrance.name}`}
        />

        <div
          id="angebote"
          className="mt-5 scroll-mt-6"
        >
          <FragranceOffers
            productId={fragrance.product_id}
          />
        </div>

        <div className="mt-5 grid gap-4 lg:mt-7 lg:grid-cols-[1.05fr_0.95fr]">
          <section className="rounded-2xl border border-(--line) bg-(--card) p-4 shadow-(--shadow-sm) sm:p-5">
            <h2 className="text-[17px] font-semibold">
              Duftprofil
            </h2>

            <div className="mt-3 flex flex-wrap gap-2">
              {fragrance.accords.map((accord) => (
                <span
                  key={accord}
                  className="rounded-full bg-(--well) px-3 py-1.5 text-[12px] text-(--ink)"
                >
                  {accordLabel(accord)}
                </span>
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
                href="/vergleich"
                className="text-[12px] font-semibold text-(--accent-ink) hover:underline"
              >
                Vergleiche entdecken
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
                  item.fragrance.preferred_visual;
                const relatedIsProductTruth =
                  isVerifiedProductTruthVisual(relatedVisual);

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
                        {item.fragrance.community.rating_10 != null ? (
                          <div className="mt-2 text-[11px] text-(--ink-soft)">
                            <span className="font-semibold text-(--ink)">
                              {item.fragrance.community.rating_10.toLocaleString(
                                "de-DE",
                                {
                                  minimumFractionDigits: 1,
                                  maximumFractionDigits: 1,
                                },
                              )}/10
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
        </footer>
      </div>

      <div className="dufynd-mobile-offer-bar fixed inset-x-0 bottom-0 z-40 border-t border-(--line) bg-(--card)/94 px-3 pt-2.5 shadow-[0_-10px_30px_rgba(23,21,19,0.10)] backdrop-blur-xl sm:hidden">
        <div className="mx-auto flex max-w-[420px] items-center gap-3">
          <div className="min-w-0 flex-1">
            <div className="truncate text-[11px] font-semibold text-(--ink)">
              {fragrance.brand} {fragrance.name}
            </div>
            <div className="text-[10px] text-(--ink-soft)">
              Händlerangebote vergleichen
            </div>
          </div>
          <a
            href="#angebote"
            className="shrink-0 rounded-xl bg-(--accent-strong) px-4 py-2.5 text-[12px] font-semibold text-white"
          >
            Angebote prüfen
          </a>
        </div>
      </div>
    </main>
  );
}
