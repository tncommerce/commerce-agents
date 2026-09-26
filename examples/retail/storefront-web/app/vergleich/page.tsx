import type { Metadata } from "next";

import FragranceComparisonPicker from "@/components/FragranceComparisonPicker";
import FragranceVisual from "@/components/FragranceVisual";
import {
  EXPLICIT_COMPARISON_PAIRS,
  LIVE_FRAGRANCES,
  isVerifiedProductTruthVisual,
  type StaticFragrance,
} from "@/lib/fragranceCatalog";

export const metadata: Metadata = {
  title: "Parfumvergleiche",
  description:
    "Vergleiche ausgewählte Parfums bei DUFYND nach Duftprofil, Community-Bewertung, Haltbarkeit, Ausstrahlung und Preisreferenz.",
  alternates: {
    canonical: "/vergleich",
  },
};

const RELATION_LABELS = {
  clone: "Sehr naher Duftstil",
  inspired: "Ähnlicher Duftstil",
  alternative: "Alternative",
} as const;

function ComparisonThumbnail({ fragrance }: { fragrance: StaticFragrance }) {
  const visual = fragrance.preferred_visual;
  if (!visual?.url) {
    return (
      <div className="mb-2 flex h-24 flex-col items-center justify-center overflow-hidden rounded-xl border border-[#e7d9bd] bg-[radial-gradient(circle_at_50%_30%,#fffaf0,#eee1c8)] px-2 text-center sm:h-28">
        <span className="text-[9px] font-semibold uppercase tracking-[0.12em] text-[#947747]">
          Duftprofil
        </span>
        <span className="mt-1 line-clamp-2 text-[12px] font-semibold leading-4 text-[#3a2d1d]">
          {fragrance.brand}
        </span>
      </div>
    );
  }

  const isProductTruth = isVerifiedProductTruthVisual(visual);
  return (
    <FragranceVisual
      imageUrl={visual.url}
      cutoutUrl={isProductTruth ? visual.url : undefined}
      alt={`${fragrance.brand} ${fragrance.name}`}
      variant="card"
      mode={isProductTruth ? "cutout" : "editorial"}
      className="mb-2 h-24 w-full overflow-hidden rounded-xl sm:h-28"
    />
  );
}

export default function ComparisonIndexPage() {
  return (
    <main className="min-h-screen bg-(--surface) text-(--ink)">
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
            href="/duft"
            className="rounded-xl border border-(--line) px-3 py-2 text-[12px] font-semibold text-(--ink)"
          >
            Duftkatalog
          </a>
        </div>
      </header>

      <div className="mx-auto max-w-[1080px] px-4 py-7 sm:px-6 sm:py-10">
        <section className="relative overflow-hidden rounded-[30px] border border-[#d7c7a2]/45 bg-[#15120f] px-5 py-7 text-white shadow-[0_24px_80px_-38px_rgba(40,27,10,0.75)] sm:px-8 sm:py-9">
          <div aria-hidden className="pointer-events-none absolute inset-0 bg-[radial-gradient(circle_at_85%_20%,rgba(212,174,101,0.22),transparent_34%),linear-gradient(135deg,#17130f_0%,#0e0c0a_66%,#211a11_100%)]" />
          <div className="relative max-w-3xl">
            <div className="text-[10.5px] font-semibold uppercase tracking-[0.18em] text-[#d9bd82]">
              DUFYND · Duftvergleich
            </div>
            <h1 className="mt-3 text-[32px] font-semibold leading-[1.05] tracking-[-0.045em] text-[#fffaf0] sm:text-[48px]">
              Parfums direkt vergleichen
            </h1>
            <p className="mt-4 max-w-2xl text-[13px] leading-6 text-white/70 sm:text-[14px]">
              Ähnliche Duftstile und verwandte Profile nebeneinander entdecken:
              mit Duftcharakter, Community-Daten und Preisreferenzen.
            </p>
            <div className="mt-5 inline-flex rounded-full border border-white/15 bg-white/[0.06] px-3 py-1.5 text-[11px] font-semibold text-white/80">
              {EXPLICIT_COMPARISON_PAIRS.length} dokumentierte Vergleiche
            </div>
          </div>
        </section>

        <FragranceComparisonPicker
          fragrances={LIVE_FRAGRANCES}
        />

        <div className="mt-9">
          <h2 className="text-[20px] font-semibold">
            Dokumentierte Duftbeziehungen
          </h2>
          <p className="mt-1 max-w-2xl text-[12px] leading-5 text-(--ink-soft)">
            Diese Paare haben zusätzlich eine im DUFYND-Katalog
            dokumentierte Beziehung wie inspiriert, Alternative oder sehr
            naher Duftstil.
          </p>
        </div>

        <section className="mt-5 grid gap-3 sm:grid-cols-2">
          {EXPLICIT_COMPARISON_PAIRS.map((pair) => (
            <a
              key={pair.pair_slug}
              href={`/vergleich/${pair.pair_slug}`}
              className="rounded-2xl border border-[#e0d4bd] bg-(--card) p-4 shadow-(--shadow-sm) transition hover:-translate-y-0.5 hover:border-[#c9ad77] hover:shadow-md"
            >
              <div className="text-[10px] font-semibold uppercase tracking-[0.08em] text-(--ink-soft)">
                {RELATION_LABELS[pair.kind]}
              </div>

              <div className="mt-3 grid grid-cols-[minmax(0,1fr)_auto_minmax(0,1fr)] items-center gap-2 sm:gap-3">
                <div className="min-w-0">
                  <ComparisonThumbnail fragrance={pair.left} />
                  <div className="truncate text-[10.5px] text-(--ink-soft)">
                    {pair.left.brand}
                  </div>
                  <div className="mt-0.5 line-clamp-2 text-[14px] font-semibold leading-5">
                    {pair.left.name}
                  </div>
                </div>

                <div className="rounded-full border border-[#d9c49c] bg-[#f8f0df] px-2 py-1 text-[10px] font-semibold text-[#7e5b20]">
                  vs
                </div>

                <div className="min-w-0 text-right">
                  <ComparisonThumbnail fragrance={pair.right} />
                  <div className="truncate text-[10.5px] text-(--ink-soft)">
                    {pair.right.brand}
                  </div>
                  <div className="mt-0.5 line-clamp-2 text-[14px] font-semibold leading-5">
                    {pair.right.name}
                  </div>
                </div>
              </div>

              <div className="mt-4 border-t border-(--line) pt-3 text-[11px] font-semibold text-(--accent-ink)">
                Vergleich öffnen →
              </div>
            </a>
          ))}
        </section>

        <section className="mt-6 rounded-2xl border border-(--line) bg-(--well)/45 p-4 text-[11px] leading-5 text-(--ink-soft)">
          Begriffe wie „inspiriert“ oder „sehr naher Duftstil“ beschreiben
          eine dokumentierte Duftbeziehung im DUFYND-Katalog. Sie
          bedeuten nicht, dass Rezeptur oder Inhaltsstoffe identisch sind.
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
