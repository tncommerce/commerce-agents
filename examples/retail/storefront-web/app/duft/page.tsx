import type { Metadata } from "next";
import AcquisitionAnalytics from "@/components/AcquisitionAnalytics";
import AcquisitionInternalLink from "@/components/AcquisitionInternalLink";

import FragranceCatalogBrowser from "@/components/FragranceCatalogBrowser";
import DiscoveryIntro from "@/components/DiscoveryIntro";
import FragranceVariantLinks from "@/components/FragranceVariantLinks";
import {
  LIVE_FRAGRANCES,
} from "@/lib/fragranceCatalog";

export const metadata: Metadata = {
  title: "Parfums entdecken",
  description:
    "Entdecke das DUFYND Duftsortiment mit Duftprofil, Community-Bewertungen, Haltbarkeit und aktuellen Händlerangeboten.",
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
    <main className="dufynd-catalog-page min-h-screen text-(--ink)">
      <AcquisitionAnalytics source="catalog" />
      <header className="dufynd-catalog-header border-b border-(--line)">
        <div className="mx-auto flex max-w-[1080px] items-center justify-between gap-4 px-4 py-4 sm:px-6">
          <AcquisitionInternalLink
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
          </AcquisitionInternalLink>
          <div className="flex items-center gap-2">
            <AcquisitionInternalLink
              href="/sammlung"
              className="hidden rounded-xl border border-(--line) px-3 py-2 text-[12px] font-semibold text-(--ink) transition hover:border-(--ink) md:inline-flex"
            >
              Sammlung
            </AcquisitionInternalLink>
            <AcquisitionInternalLink
              href="/merkliste"
              className="hidden rounded-xl border border-(--line) px-3 py-2 text-[12px] font-semibold text-(--ink) transition hover:border-(--ink) md:inline-flex"
            >
              Merkliste
            </AcquisitionInternalLink>
            <AcquisitionInternalLink
              href="/vergleich"
              className="hidden rounded-xl border border-(--line) px-3 py-2 text-[12px] font-semibold text-(--ink) transition hover:border-(--ink) md:inline-flex"
            >
              Vergleiche
            </AcquisitionInternalLink>
            <AcquisitionInternalLink
              href="/"
              className="rounded-xl border border-(--line) px-3 py-2 text-[12px] font-semibold text-(--ink) transition hover:border-(--ink)"
            >
              Duftberatung öffnen
            </AcquisitionInternalLink>
          </div>
        </div>
        <nav
          aria-label="Weitere DUFYND Bereiche"
          className="mx-auto flex max-w-[1080px] gap-2 px-4 pb-3 text-[11px] font-semibold sm:px-6 md:hidden"
        >
          {[
            ["/vergleich", "Vergleiche"],
            ["/merkliste", "Merkliste"],
            ["/sammlung", "Sammlung"],
          ].map(([href, label]) => (
            <AcquisitionInternalLink
              key={href}
              href={href}
              className="min-w-0 flex-1 rounded-lg border border-(--line) bg-(--card) px-2 py-2 text-center text-(--ink) transition hover:border-(--accent)"
            >
              {label}
            </AcquisitionInternalLink>
          ))}
        </nav>
      </header>

      <div className="mx-auto max-w-[1080px] px-4 py-7 sm:px-6 sm:py-10">
        <DiscoveryIntro catalog />

        <div
          id="dufynd-katalog"
          className="dufynd-catalog-intro scroll-mt-5 pt-7 sm:pt-9"
        >
          <h2 className="text-[24px] font-semibold tracking-[-0.025em]">Der Duftkatalog</h2>
        </div>

        <FragranceCatalogBrowser
          fragrances={fragrances}
        />

        <FragranceVariantLinks />

        <footer className="mt-8 flex flex-wrap gap-x-4 gap-y-2 border-t border-(--line) py-6 text-[11px] text-(--ink-soft)">
          <AcquisitionInternalLink href="/transparenz" className="hover:underline">
            Transparenz
          </AcquisitionInternalLink>
          <AcquisitionInternalLink href="/impressum" className="hover:underline">
            Impressum
          </AcquisitionInternalLink>
          <AcquisitionInternalLink href="/datenschutz" className="hover:underline">
            Datenschutz
          </AcquisitionInternalLink>
        </footer>
      </div>
    </main>
  );
}
