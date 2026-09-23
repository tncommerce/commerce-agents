import type { Metadata } from "next";
import { notFound } from "next/navigation";

import AcquisitionAnalytics from "@/components/AcquisitionAnalytics";
import DufyndDepthInteraction from "@/components/DufyndDepthInteraction";
import FragranceOffers from "@/components/FragranceOffers";
import FragranceSaveControls from "@/components/FragranceSaveControls";
import {
  LIVE_FRAGRANCES,
  comparisonPath,
  getLiveFragranceBySlug,
  getRelatedFragrances,
  type RelatedFragranceKind,
  type StaticFragrance,
} from "@/lib/fragranceCatalog";
import { SITE_URL } from "@/lib/site";

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

const ACCORD_TONES: Record<
  string,
  { dot: string; background: string; border: string }
> = {
  fresh: { dot: "#79a8a2", background: "#eef7f5", border: "#d7eae6" },
  citrus: { dot: "#d5a83f", background: "#fff8e8", border: "#f0dfb6" },
  aquatic: { dot: "#6f9cb5", background: "#edf6fa", border: "#d7e8f0" },
  green: { dot: "#789667", background: "#f1f6ed", border: "#dce8d5" },
  spicy: { dot: "#b46f46", background: "#fbf1eb", border: "#edd9cc" },
  sweet: { dot: "#c59a68", background: "#fbf3e8", border: "#eadbc8" },
  synthetic: { dot: "#8f91a5", background: "#f3f3f6", border: "#dfdfe7" },
  fruity: { dot: "#b96d6b", background: "#fbefef", border: "#edd6d5" },
  woody: { dot: "#8b6949", background: "#f6f0e9", border: "#e3d7ca" },
  smoky: { dot: "#73706d", background: "#f2f1ef", border: "#dedbd7" },
  powdery: { dot: "#b9a98f", background: "#f8f5ef", border: "#e8e0d4" },
  floral: { dot: "#b87f91", background: "#faf0f4", border: "#ecd9e0" },
  creamy: { dot: "#c6ad7d", background: "#fbf7ee", border: "#eadfca" },
  gourmand: { dot: "#a9784e", background: "#f8f0e8", border: "#e6d5c5" },
  oriental: { dot: "#9f7545", background: "#f8f1e8", border: "#e7d8c5" },
  aromatic: { dot: "#6e8a78", background: "#eff5f1", border: "#d9e6dd" },
  leathery: { dot: "#705748", background: "#f3eeeb", border: "#ded3cc" },
  resinous: { dot: "#9a713f", background: "#f8f1e5", border: "#e7d7bf" },
};

function AccordChip({ accord }: { accord: string }) {
  const tone =
    ACCORD_TONES[accord.toLowerCase()] || {
      dot: "#9a7a45",
      background: "#f7f2e8",
      border: "#e5d9c2",
    };

  return (
    <span
      className="inline-flex items-center gap-2 rounded-full border px-3 py-1.5 text-[12px] font-medium text-(--ink)"
      style={{
        background: tone.background,
        borderColor: tone.border,
      }}
    >
      <span
        aria-hidden
        className="h-2 w-2 rounded-full shadow-[0_0_0_3px_rgba(255,255,255,0.6)]"
        style={{ background: tone.dot }}
      />
      {accordLabel(accord)}
    </span>
  );
}

function accordLabel(value: string): string {
  return ACCORD_LABELS[value.toLowerCase()] || value;
}

function targetLabel(value: string): string {
  return TARGET_LABELS[value.toLowerCase()] || value;
}

function relatedLabel(kind: RelatedFragranceKind): string {
  return {
    clone: "Sehr naher Duftstil",
    inspired: "Inspiriert",
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
  icon: string,
) {
  if (!notes.length) return null;

  const tierStyle =
    title === "Kopfnote"
      ? {
          accent: "#c89a43",
          surface: "linear-gradient(135deg,#fffaf0,#f7edda)",
        }
      : title === "Herznote"
        ? {
            accent: "#a97868",
            surface: "linear-gradient(135deg,#fff9f6,#f5ece7)",
          }
        : {
            accent: "#755a3a",
            surface: "linear-gradient(135deg,#f8f3eb,#eee3d4)",
          };

  return (
    <div
      className="rounded-2xl border border-white/70 p-3.5 shadow-[0_10px_30px_-24px_rgba(58,40,15,0.55)] sm:p-4"
      style={{ background: tierStyle.surface }}
    >
      <div className="flex items-center justify-between gap-3">
        <div className="flex items-center gap-2.5">
          <span
            aria-hidden
            className="grid h-8 w-8 place-items-center rounded-full border border-white/80 bg-white/80 text-[13px] shadow-sm"
            style={{ color: tierStyle.accent }}
          >
            {icon}
          </span>
          <div>
            <div className="text-[11px] font-semibold uppercase tracking-[0.1em] text-(--ink)">
              {title}
            </div>
            <div className="mt-0.5 text-[10px] text-(--ink-soft)">
              {notes.length} {notes.length === 1 ? "Duftnote" : "Duftnoten"}
            </div>
          </div>
        </div>
        <span
          aria-hidden
          className="h-px w-12"
          style={{
            background: `linear-gradient(90deg,${tierStyle.accent},transparent)`,
          }}
        />
      </div>
      <div className="mt-3 flex flex-wrap gap-2">
        {notes.map((note) => (
          <span
            key={note}
            className="rounded-full border border-white/80 bg-white/75 px-3 py-1.5 text-[11.5px] font-medium text-(--ink) shadow-[0_5px_16px_-14px_rgba(42,31,14,0.8)]"
          >
            {note}
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
      images: fragrance.image_url
        ? [fragrance.image_url]
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
  const related = getRelatedFragrances(
    fragrance,
    4,
  );
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

  return (
    <main className="min-h-screen bg-(--surface) text-(--ink)">
      <script
        type="application/ld+json"
        dangerouslySetInnerHTML={{ __html: breadcrumbJson }}
      />
      <AcquisitionAnalytics source="fragrance_detail" />
      <DufyndDepthInteraction />
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

        <section className="relative overflow-hidden rounded-[30px] border border-[#d9c9aa]/70 bg-[linear-gradient(135deg,#f8f1e4_0%,#fffdf8_48%,#eee0c5_100%)] p-4 shadow-[0_24px_70px_-42px_rgba(82,56,18,0.55)] sm:p-6 lg:grid lg:grid-cols-[0.9fr_1.1fr] lg:gap-8 lg:p-8">
          <div
            aria-hidden
            className="pointer-events-none absolute -right-16 -top-20 h-64 w-64 rounded-full bg-[#c79b4c]/12 blur-3xl"
          />
          <div className="dufynd-depth-stage relative mx-auto w-full max-w-[280px] overflow-hidden rounded-[26px] border border-white/80 bg-[radial-gradient(circle_at_50%_40%,#ffffff_0%,#f7edda_58%,#e8d7b6_100%)] shadow-[0_26px_65px_-34px_rgba(61,42,14,0.65)] sm:max-w-[360px] lg:mx-0 lg:max-w-none">
            {fragrance.image_url ? (
              // eslint-disable-next-line @next/next/no-img-element
              <img
                src={fragrance.image_url}
                alt={`${fragrance.brand} ${fragrance.name}`}
                className="dufynd-depth-object aspect-square h-full w-full scale-[1.05] object-contain p-5 sm:p-9"
              />
            ) : (
              <div className="grid aspect-square place-items-center bg-(--well)">
                <div className="text-center">
                  <div className="mx-auto h-4 w-12 rounded-t bg-(--ink)/80" />
                  <div className="mx-auto h-4 w-8 bg-(--ink)/60" />
                  <div className="mx-auto grid h-28 w-24 place-items-center rounded-[24px] border border-white bg-white/80 shadow-md">
                    <span className="text-[11px] font-semibold tracking-[0.18em]">
                      DUFYND
                    </span>
                  </div>
                </div>
              </div>
            )}
          </div>

          <div className="relative mt-5 flex flex-col justify-center lg:mt-0">
            <div className="mb-1 text-[9.5px] font-semibold uppercase tracking-[0.19em] text-[#8a6426]">
              DUFYND · Duftprofil
            </div>
            <div className="text-[11px] font-semibold uppercase tracking-[0.12em] text-(--ink-soft)">
              {fragrance.brand}
            </div>
            <h1 className="mt-2 max-w-2xl text-[36px] font-semibold leading-[1.02] tracking-[-0.045em] sm:text-[48px] lg:text-[54px]">
              {fragrance.name}
            </h1>

            <div className="mt-3 flex flex-wrap gap-1.5 text-[11px] text-(--ink-soft) sm:gap-2 sm:text-[12px]">
              <span className="rounded-full border border-(--line) bg-(--card) px-2.5 py-1.5 sm:px-3">
                {fragrance.concentration}
              </span>
              <span className="rounded-full border border-(--line) bg-(--card) px-2.5 py-1.5 sm:px-3">
                {fragrance.volume_ml} ml
              </span>
              {fragrance.target_groups.map((group) => (
                <span
                  key={group}
                  className="rounded-full border border-(--line) bg-(--card) px-2.5 py-1.5 sm:px-3"
                >
                  {targetLabel(group)}
                </span>
              ))}
              {fragrance.release_year ? (
                <span className="rounded-full border border-(--line) bg-(--card) px-2.5 py-1.5 sm:px-3">
                  Seit {fragrance.release_year}
                </span>
              ) : null}
            </div>

            <div className="mt-4 grid grid-cols-2 gap-2 sm:mt-5 sm:flex sm:flex-wrap sm:gap-2.5">
              <a
                href="#angebote"
                className="rounded-xl bg-[#8a6426] px-3 py-2.5 text-center text-[12px] font-semibold text-white shadow-[0_10px_30px_-18px_rgba(86,58,15,0.9)] transition hover:bg-[#75521d] sm:px-4 sm:text-[13px]"
              >
                Aktuelle Angebote prüfen
              </a>
              {related.length ? (
                <a
                  href="#alternativen"
                  className="rounded-xl border border-(--line) bg-(--card) px-3 py-2.5 text-center text-[12px] font-semibold text-(--ink) transition hover:border-(--ink) sm:px-4 sm:text-[13px]"
                >
                  Alternativen ansehen
                </a>
              ) : null}
            </div>

            <div className="mt-3">
              <FragranceSaveControls
                productId={fragrance.product_id}
                compact
              />
              <p className="mt-1.5 text-[10.5px] leading-4 text-(--ink-soft)">
                Merkliste und Sammlung werden nur lokal auf diesem Gerät gespeichert.
              </p>
            </div>

            <div className="mt-2 text-[10.5px] leading-4 text-(--ink-soft)">
              DUFYND verkauft nicht selbst. Kauf und Versand erfolgen beim
              jeweiligen Händler.
            </div>

            <div className="mt-4 grid grid-cols-3 gap-2 sm:mt-6 sm:gap-3">
              <div className="rounded-2xl border border-white/75 bg-white/70 p-3 shadow-[0_8px_24px_-20px_rgba(50,35,12,0.65)] backdrop-blur-sm sm:p-4">
                <div className="text-[11px] text-(--ink-soft)">
                  Community
                </div>
                <div className="mt-1 text-[20px] font-semibold sm:text-[22px]">
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
                <div className="mt-0.5 hidden text-[10.5px] text-(--ink-soft) sm:block">
                  {fragrance.community.source}
                  {fragrance.community.rating_count
                    ? ` · ${fragrance.community.rating_count.toLocaleString(
                        "de-DE",
                      )} Bewertungen`
                    : ""}
                </div>
              </div>

              <div className="rounded-2xl border border-white/75 bg-white/70 p-3 shadow-[0_8px_24px_-20px_rgba(50,35,12,0.65)] backdrop-blur-sm sm:p-4">
                <div className="text-[11px] text-(--ink-soft)">
                  Haltbarkeit
                </div>
                <div className="mt-1 text-[20px] font-semibold sm:text-[22px]">
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
                <div className="mt-0.5 hidden text-[10.5px] text-(--ink-soft) sm:block">
                  Community-Skala 0–10
                </div>
              </div>

              <div className="rounded-2xl border border-white/75 bg-white/70 p-3 shadow-[0_8px_24px_-20px_rgba(50,35,12,0.65)] backdrop-blur-sm sm:p-4">
                <div className="text-[11px] text-(--ink-soft)">
                  Ausstrahlung
                </div>
                <div className="mt-1 text-[20px] font-semibold sm:text-[22px]">
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
                <div className="mt-0.5 hidden text-[10.5px] text-(--ink-soft) sm:block">
                  Community-Skala 0–10
                </div>
              </div>
            </div>

            <p className="mt-5 hidden max-w-2xl text-[13px] leading-5 text-(--ink-soft) sm:block">
              Community-Werte beschreiben Nutzerbewertungen und sind keine
              objektiv gemessenen Stunden- oder Meterangaben.
            </p>
          </div>
        </section>

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
            <div className="text-[10px] font-semibold uppercase tracking-[0.14em] text-[#8a6426]">
              Charakter
            </div>
            <h2 className="mt-1 text-[19px] font-semibold tracking-[-0.02em]">
              Duftprofil
            </h2>

            <div className="mt-3 flex flex-wrap gap-2">
              {fragrance.accords.map((accord) => (
                <AccordChip key={accord} accord={accord} />
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
            <summary className="flex cursor-pointer list-none items-center justify-between gap-3 text-[17px] font-semibold">
              <span>Duftnoten</span>
              <span
                aria-hidden
                className="text-[18px] text-(--accent-ink) transition group-open:rotate-45"
              >
                +
              </span>
            </summary>
            <div className="mt-4 space-y-4">
              {noteSection("Kopfnote", fragrance.notes.top, "✦")}
              {noteSection("Herznote", fragrance.notes.heart, "♥")}
              {noteSection("Basisnote", fragrance.notes.base, "◆")}
              {!fragrance.notes.top.length &&
              !fragrance.notes.heart.length &&
              !fragrance.notes.base.length ? (
                <p className="text-[13px] leading-5 text-(--ink-soft)">
                  Für diesen Duft sind aktuell keine verifizierten
                  Notenpyramiden im DUFYND-Katalog hinterlegt.
                </p>
              ) : null}
            </div>
          </details>

          <section className="hidden rounded-2xl border border-(--line) bg-(--card) p-5 shadow-(--shadow-sm) lg:block">
            <div className="text-[10px] font-semibold uppercase tracking-[0.14em] text-[#8a6426]">
              Pyramide
            </div>
            <h2 className="mt-1 text-[19px] font-semibold tracking-[-0.02em]">
              Duftnoten
            </h2>
            <div className="mt-4 space-y-4">
              {noteSection("Kopfnote", fragrance.notes.top, "✦")}
              {noteSection("Herznote", fragrance.notes.heart, "♥")}
              {noteSection("Basisnote", fragrance.notes.base, "◆")}
              {!fragrance.notes.top.length &&
              !fragrance.notes.heart.length &&
              !fragrance.notes.base.length ? (
                <p className="text-[13px] leading-5 text-(--ink-soft)">
                  Für diesen Duft sind aktuell keine verifizierten
                  Notenpyramiden im DUFYND-Katalog hinterlegt.
                </p>
              ) : null}
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

                return (
                  <article
                    key={item.fragrance.product_id}
                    className="min-w-[220px] snap-start overflow-hidden rounded-xl border border-(--line) bg-(--well)/35 sm:min-w-0"
                  >
                    <a
                      href={`/duft/${item.fragrance.slug}`}
                      className="block"
                    >
                      <div className="flex h-36 items-center justify-center bg-white p-3">
                        {item.fragrance.image_url ? (
                          // eslint-disable-next-line @next/next/no-img-element
                          <img
                            src={item.fragrance.image_url}
                            alt={`${item.fragrance.brand} ${item.fragrance.name}`}
                            className="h-full w-full object-contain"
                          />
                        ) : (
                          <span className="text-[11px] font-semibold tracking-[0.14em] text-(--ink-soft)">
                            DUFYND
                          </span>
                        )}
                      </div>
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
              DUFYND Advisor öffnen
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
    </main>
  );
}
