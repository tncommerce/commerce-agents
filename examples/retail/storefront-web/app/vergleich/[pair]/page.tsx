import type { Metadata } from "next";
import { notFound } from "next/navigation";
import AcquisitionAnalytics from "@/components/AcquisitionAnalytics";

import ComparisonAnalytics from "@/components/ComparisonAnalytics";
import { accordLabel } from "@/lib/accordLabels";
import FragranceOffers from "@/components/FragranceOffers";
import FragranceVisual from "@/components/FragranceVisual";
import {
  EXPLICIT_COMPARISON_PAIRS,
  getComparisonPair,
  isVerifiedProductTruthVisual,
  type ExplicitComparisonPair,
  type StaticFragrance,
} from "@/lib/fragranceCatalog";
import { SITE_URL } from "@/lib/site";
import { formatPriceReference } from "@/lib/priceReference";
import { targetLabel } from "@/lib/targetLabels";

export const dynamicParams = false;

type PageProps = {
  params: Promise<{
    pair: string;
  }>;
};

const RELATION_LABELS: Record<
  ExplicitComparisonPair["kind"],
  string
> = {
  clone: "Sehr naher Duftstil",
  inspired: "Ähnlicher Duftstil",
  alternative: "Alternative",
};

const CONFIDENCE_LABELS: Record<string, string> = {
  high: "hoch",
  medium_high: "mittel-hoch",
  medium: "mittel",
  low: "niedrig",
};

function formatRating(value: number | null): string {
  if (value == null) return "–";
  return `${value.toLocaleString("de-DE", {
    minimumFractionDigits: 1,
    maximumFractionDigits: 1,
  })}/10`;
}

function formatNumber(value: number | null): string {
  if (value == null) return "–";
  return value.toLocaleString("de-DE", {
    minimumFractionDigits: 1,
    maximumFractionDigits: 1,
  });
}

function ProductHeader({
  fragrance,
}: {
  fragrance: StaticFragrance;
}) {
  const visual = fragrance.preferred_visual;
  const isProductTruth = isVerifiedProductTruthVisual(visual);

  return (
    <div className="overflow-hidden rounded-2xl border border-(--line) bg-(--card)">
      <a href={`/duft/${fragrance.slug}`}>
        <FragranceVisual
          imageUrl={visual?.url}
          cutoutUrl={isProductTruth ? visual?.url : undefined}
          alt={`${fragrance.brand} ${fragrance.name}`}
          variant="card"
          mode={isProductTruth ? "cutout" : "editorial"}
          className="h-56 w-full"
        />
        <div className="p-4">
          <div className="text-[10.5px] font-semibold uppercase tracking-[0.08em] text-(--ink-soft)">
            {fragrance.brand}
          </div>
          <h2 className="mt-1 text-[20px] font-semibold leading-6">
            {fragrance.name}
          </h2>
          <div className="mt-2 flex flex-wrap gap-1.5 text-[11px] text-(--ink-soft)">
            <span>{fragrance.concentration}</span>
            <span>·</span>
            <span>{fragrance.volume_ml} ml</span>
          </div>
        </div>
      </a>
    </div>
  );
}

function ComparisonRow({
  label,
  left,
  right,
}: {
  label: string;
  left: React.ReactNode;
  right: React.ReactNode;
}) {
  return (
    <div className="grid grid-cols-[1fr_0.9fr_1fr] items-center gap-3 border-t border-(--line) px-3 py-3 text-[12px] sm:px-4">
      <div className="text-right font-medium text-(--ink)">
        {left}
      </div>
      <div className="text-center text-[10.5px] font-semibold uppercase tracking-[0.06em] text-(--ink-soft)">
        {label}
      </div>
      <div className="font-medium text-(--ink)">
        {right}
      </div>
    </div>
  );
}

export function generateStaticParams() {
  return EXPLICIT_COMPARISON_PAIRS.map((pair) => ({
    pair: pair.pair_slug,
  }));
}

export async function generateMetadata({
  params,
}: PageProps): Promise<Metadata> {
  const { pair: pairSlug } = await params;
  const pair = getComparisonPair(pairSlug);

  if (!pair) {
    return {
      title: "Vergleich nicht gefunden",
    };
  }

  const title =
    `${pair.left.brand} ${pair.left.name} vs. ${pair.right.brand} ${pair.right.name}`;
  const description =
    `Vergleiche ${pair.left.brand} ${pair.left.name} und ${pair.right.brand} ${pair.right.name}: Duftprofil, Community-Bewertung, Haltbarkeit, Ausstrahlung und Preisreferenz.`;
  const canonical = `/vergleich/${pair.pair_slug}`;

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
    },
  };
}

export default async function ComparisonPage({
  params,
}: PageProps) {
  const { pair: pairSlug } = await params;
  const pair = getComparisonPair(pairSlug);

  if (!pair) notFound();

  const left = pair.left;
  const right = pair.right;
  const canonicalUrl = `${SITE_URL}/vergleich/${pair.pair_slug}`;
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
        name: "Vergleiche",
        item: `${SITE_URL}/vergleich`,
      },
      {
        "@type": "ListItem",
        position: 3,
        name: `${left.brand} ${left.name} vs. ${right.brand} ${right.name}`,
        item: canonicalUrl,
      },
    ],
  };
  const breadcrumbJson = JSON.stringify(
    breadcrumbStructuredData,
  ).replaceAll("<", "\\u003c");

  return (
    <main className="min-h-screen bg-(--surface) text-(--ink)">
      <script
        type="application/ld+json"
        dangerouslySetInnerHTML={{ __html: breadcrumbJson }}
      />
      <AcquisitionAnalytics source="comparison_detail" />
      <ComparisonAnalytics
        productId={left.product_id}
        relatedProductId={right.product_id}
      />
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
          <a
            href="/vergleich"
            className="rounded-xl border border-(--line) px-3 py-2 text-[12px] font-semibold text-(--ink)"
          >
            Weitere Vergleiche
          </a>
        </div>
      </header>

      <div className="mx-auto max-w-[1080px] px-4 py-6 sm:px-6 sm:py-9">
        <nav
          aria-label="Breadcrumb"
          className="mb-5 text-[12px] text-(--ink-soft)"
        >
          <a href="/" className="hover:underline">
            DUFYND
          </a>
          <span className="px-2">/</span>
          <a href="/vergleich" className="hover:underline">
            Vergleiche
          </a>
          <span className="px-2">/</span>
          <span className="text-(--ink)">
            {left.name} vs. {right.name}
          </span>
        </nav>

        <div className="max-w-3xl">
          <div className="text-[11px] font-semibold uppercase tracking-[0.12em] text-(--ink-soft)">
            DUFYND Duftvergleich
          </div>
          <h1 className="mt-2 text-[30px] font-semibold leading-[1.1] tracking-[-0.035em] sm:text-[40px]">
            {left.brand} {left.name} vs. {right.brand} {right.name}
          </h1>
          <div className="mt-3 inline-flex rounded-full border border-(--line) bg-(--card) px-3 py-1.5 text-[11px] font-semibold text-(--ink-soft)">
            {RELATION_LABELS[pair.kind]}
            {pair.confidence
              ? ` · Datenvertrauen: ${CONFIDENCE_LABELS[pair.confidence] || pair.confidence}`
              : ""}
          </div>
          <p className="mt-4 text-[13px] leading-5 text-(--ink-soft)">
            Dieser Vergleich basiert auf dokumentierten DUFYND-Duftbeziehungen,
            Community-Daten und redaktionellen Duftprofil-Merkmalen.
            Eine Duftbeziehung bedeutet nicht, dass die Formeln chemisch
            identisch sind.
          </p>
        </div>

        <section className="mt-7 grid gap-4 sm:grid-cols-2">
          <ProductHeader fragrance={left} />
          <ProductHeader fragrance={right} />
        </section>

        <section className="mt-5 overflow-hidden rounded-2xl border border-(--line) bg-(--card) shadow-(--shadow-sm)">
          <div className="grid grid-cols-[1fr_0.9fr_1fr] gap-3 bg-(--well)/55 px-3 py-3 text-[11px] sm:px-4">
            <div className="text-right font-semibold">
              {left.name}
            </div>
            <div className="text-center font-semibold uppercase tracking-[0.06em] text-(--ink-soft)">
              Vergleich
            </div>
            <div className="font-semibold">
              {right.name}
            </div>
          </div>

          <ComparisonRow
            label="Community"
            left={formatRating(left.community.rating_10)}
            right={formatRating(right.community.rating_10)}
          />
          <ComparisonRow
            label="Bewertungen"
            left={left.community.rating_count.toLocaleString("de-DE")}
            right={right.community.rating_count.toLocaleString("de-DE")}
          />
          <ComparisonRow
            label="Haltbarkeit"
            left={formatNumber(left.community.longevity_10)}
            right={formatNumber(right.community.longevity_10)}
          />
          <ComparisonRow
            label="Ausstrahlung"
            left={formatNumber(left.community.projection_10)}
            right={formatNumber(right.community.projection_10)}
          />
          <ComparisonRow
            label="Frische"
            left={formatNumber(left.scores.freshness)}
            right={formatNumber(right.scores.freshness)}
          />
          <ComparisonRow
            label="Süße"
            left={formatNumber(left.scores.sweetness)}
            right={formatNumber(right.scores.sweetness)}
          />
          <ComparisonRow
            label="Holzigkeit"
            left={formatNumber(left.scores.woodiness)}
            right={formatNumber(right.scores.woodiness)}
          />
          <ComparisonRow
            label="Würze"
            left={formatNumber(left.scores.spiciness)}
            right={formatNumber(right.scores.spiciness)}
          />
          <ComparisonRow
            label="Zielgruppe"
            left={left.target_groups.map(targetLabel).join(", ")}
            right={right.target_groups.map(targetLabel).join(", ")}
          />
          <ComparisonRow
            label="Preis-Richtwert"
            left={formatPriceReference(left.market.reference_price_eur, left.market.checked_at)}
            right={formatPriceReference(right.market.reference_price_eur, right.market.checked_at)}
          />
        </section>
        <p className="mt-2 text-[11px] leading-5 text-(--ink-soft)">
          Historische Marktbeobachtung zum angegebenen Stand, kein aktuelles Kaufangebot.
          Verfügbare Händlerangebote werden auf den Duftseiten separat geprüft.
        </p>

        <section className="mt-5 grid gap-4 sm:grid-cols-2">
          {[left, right].map((fragrance) => (
            <div
              key={fragrance.product_id}
              className="rounded-2xl border border-(--line) bg-(--card) p-5 shadow-(--shadow-sm)"
            >
              <h2 className="text-[16px] font-semibold">
                {fragrance.name}: Duftprofil
              </h2>
              <div className="mt-3 flex flex-wrap gap-2">
                {fragrance.accords.slice(0, 5).map((accord) => (
                  <span
                    key={accord}
                    className="rounded-full bg-(--well) px-2.5 py-1.5 text-[11px] text-(--ink-soft)"
                  >
                    {accordLabel(accord)}
                  </span>
                ))}
              </div>
              <a
                href={`/duft/${fragrance.slug}`}
                className="mt-4 inline-block text-[12px] font-semibold text-(--accent-ink) hover:underline"
              >
                Vollständige Duftseite ansehen →
              </a>
            </div>
          ))}
        </section>

        <section className="mt-5">
          <div className="mb-3">
            <h2 className="text-[17px] font-semibold">
              Aktuelle Händlerangebote
            </h2>
            <p className="mt-1 text-[12px] leading-5 text-(--ink-soft)">
              Preisreferenzen oben dienen dem Duftvergleich. Kaufbare Angebote
              werden separat auf Aktualität und Verfügbarkeit geprüft.
            </p>
          </div>

          <div className="grid gap-4 lg:grid-cols-2">
            <FragranceOffers
              productId={left.product_id}
              heading={`Angebote für ${left.name}`}
              trackProductOpen={false}
              analyticsSurface="documented_comparison"
              compact
            />
            <FragranceOffers
              productId={right.product_id}
              heading={`Angebote für ${right.name}`}
              trackProductOpen={false}
              analyticsSurface="documented_comparison"
              compact
            />
          </div>
        </section>

        <section className="mt-5 rounded-2xl border border-(--line) bg-(--well)/45 p-4 text-[10.5px] leading-5 text-(--ink-soft)">
          Community-Werte sind Nutzerbewertungen auf einer 0–10-Skala
          und keine objektiv gemessenen Stunden oder Meter. Die
          DUFYND-Profilachsen dienen der Suche und Empfehlung und sind
          redaktionelle Merkmale.
        </section>

        <footer className="mt-8 flex flex-wrap gap-x-4 gap-y-2 border-t border-(--line) py-6 text-[11px] text-(--ink-soft)">
          <a href="/duft" className="hover:underline">
            Duftkatalog
          </a>
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
    </main>
  );
}
