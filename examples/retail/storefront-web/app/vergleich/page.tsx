import type { Metadata } from "next";

import FragranceComparisonPicker from "@/components/FragranceComparisonPicker";
import {
  EXPLICIT_COMPARISON_PAIRS,
  LIVE_FRAGRANCES,
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
  inspired: "Inspiriert",
  alternative: "Alternative",
} as const;

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
        <div className="max-w-3xl">
          <div className="text-[11px] font-semibold uppercase tracking-[0.12em] text-(--ink-soft)">
            DUFYND Vergleiche
          </div>
          <h1 className="mt-2 text-[32px] font-semibold leading-[1.08] tracking-[-0.035em] sm:text-[42px]">
            Parfums direkt vergleichen
          </h1>
          <p className="mt-4 text-[14px] leading-6 text-(--ink-soft)">
            Diese Vergleiche basieren auf dokumentierten Beziehungen im
            DUFYND-Katalog. So kannst du ähnliche Duftstile,
            inspirierte Alternativen und verwandte Profile direkt
            nebeneinander ansehen.
          </p>
        </div>

        <div className="mt-5 inline-flex rounded-full border border-(--line) bg-(--card) px-3 py-1.5 text-[12px] text-(--ink-soft)">
          {EXPLICIT_COMPARISON_PAIRS.length} dokumentierte Vergleiche
        </div>

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
              className="rounded-2xl border border-(--line) bg-(--card) p-4 shadow-(--shadow-sm) transition hover:-translate-y-0.5 hover:shadow-md"
            >
              <div className="text-[10px] font-semibold uppercase tracking-[0.08em] text-(--ink-soft)">
                {RELATION_LABELS[pair.kind]}
              </div>

              <div className="mt-2 grid grid-cols-[1fr_auto_1fr] items-center gap-3">
                <div className="min-w-0">
                  <div className="truncate text-[10.5px] text-(--ink-soft)">
                    {pair.left.brand}
                  </div>
                  <div className="mt-0.5 text-[14px] font-semibold leading-5">
                    {pair.left.name}
                  </div>
                </div>

                <div className="rounded-full bg-(--well) px-2 py-1 text-[10px] font-semibold text-(--ink-soft)">
                  vs.
                </div>

                <div className="min-w-0 text-right">
                  <div className="truncate text-[10.5px] text-(--ink-soft)">
                    {pair.right.brand}
                  </div>
                  <div className="mt-0.5 text-[14px] font-semibold leading-5">
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
