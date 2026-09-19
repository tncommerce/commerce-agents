import type { Metadata } from "next";

import FragranceCatalogBrowser from "@/components/FragranceCatalogBrowser";
import { LIVE_FRAGRANCES } from "@/lib/fragranceCatalog";

export const metadata: Metadata = {
  title: "Parfums entdecken",
  description:
    "Entdecke das SCENTAI Duftsortiment mit Duftprofil, Community-Bewertungen, Haltbarkeit und aktuellen Händlerangeboten.",
  alternates: {
    canonical: "/duft",
  },
};

export default function FragranceIndexPage() {
  const fragrances = [...LIVE_FRAGRANCES].sort(
    (a, b) =>
      b.community.rating_count -
        a.community.rating_count ||
      a.brand.localeCompare(b.brand, "de"),
  );

  return (
    <main className="min-h-screen bg-(--surface) text-(--ink)">
      <header className="border-b border-(--line) bg-(--card)">
        <div className="mx-auto flex max-w-[1080px] items-center justify-between gap-4 px-4 py-4 sm:px-6">
          <a
            href="/"
            className="flex items-center gap-2.5"
            aria-label="Zur SCENTAI Startseite"
          >
            <span className="grid h-8 w-8 place-items-center rounded-lg bg-(--ink) text-[15px] font-bold text-(--surface)">
              S
            </span>
            <span className="text-[17px] font-bold tracking-[-0.02em]">
              SCENTAI
            </span>
          </a>
          <div className="flex items-center gap-2">
            <a
              href="/sammlung"
              className="hidden rounded-xl border border-(--line) px-3 py-2 text-[12px] font-semibold text-(--ink) transition hover:border-(--ink) md:inline-flex"
            >
              Sammlung
            </a>
            <a
              href="/merkliste"
              className="hidden rounded-xl border border-(--line) px-3 py-2 text-[12px] font-semibold text-(--ink) transition hover:border-(--ink) md:inline-flex"
            >
              Merkliste
            </a>
            <a
              href="/vergleich"
              className="hidden rounded-xl border border-(--line) px-3 py-2 text-[12px] font-semibold text-(--ink) transition hover:border-(--ink) sm:inline-flex"
            >
              Vergleiche
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

      <div className="mx-auto max-w-[1080px] px-4 py-7 sm:px-6 sm:py-10">
        <div className="max-w-3xl">
          <div className="text-[11px] font-semibold uppercase tracking-[0.12em] text-(--ink-soft)">
            SCENTAI Duftkatalog
          </div>
          <h1 className="mt-2 text-[32px] font-semibold leading-[1.08] tracking-[-0.035em] sm:text-[42px]">
            Parfums entdecken
          </h1>
          <p className="mt-4 text-[14px] leading-6 text-(--ink-soft)">
            Vergleiche Duftprofile, Community-Erfahrungen und
            Performance. Aktuelle Händlerangebote werden auf den
            jeweiligen Duftseiten separat geprüft.
          </p>
        </div>

        <div className="mt-5 flex flex-wrap gap-2 text-[12px] text-(--ink-soft)">
          <span className="rounded-full border border-(--line) bg-(--card) px-3 py-1.5">
            {fragrances.length} Düfte
          </span>
          <span className="rounded-full border border-(--line) bg-(--card) px-3 py-1.5">
            Community-Bewertungen
          </span>
          <span className="rounded-full border border-(--line) bg-(--card) px-3 py-1.5">
            Händlerangebote nach Aktualität
          </span>
        </div>

        <FragranceCatalogBrowser
          fragrances={fragrances}
        />

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
