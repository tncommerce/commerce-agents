import type { Metadata } from "next";
import AcquisitionAnalytics from "@/components/AcquisitionAnalytics";

import FragranceCatalogBrowser from "@/components/FragranceCatalogBrowser";
import FragranceVisual from "@/components/FragranceVisual";
import {
  isVerifiedProductTruthVisual,
  LIVE_FRAGRANCES,
  visualWorldFor,
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
  const catalogSpotlights = fragrances.slice(0, 3);

  return (
    <main className="dufynd-catalog-page min-h-screen text-(--ink)">
      <AcquisitionAnalytics source="catalog" />
      <header className="dufynd-catalog-header border-b border-(--line)">
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
              className="hidden rounded-xl border border-(--line) px-3 py-2 text-[12px] font-semibold text-(--ink) transition hover:border-(--ink) md:inline-flex"
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
        <nav
          aria-label="Weitere DUFYND Bereiche"
          className="mx-auto flex max-w-[1080px] gap-2 px-4 pb-3 text-[11px] font-semibold sm:px-6 md:hidden"
        >
          {[
            ["/vergleich", "Vergleiche"],
            ["/merkliste", "Merkliste"],
            ["/sammlung", "Sammlung"],
          ].map(([href, label]) => (
            <a
              key={href}
              href={href}
              className="min-w-0 flex-1 rounded-lg border border-(--line) bg-(--card) px-2 py-2 text-center text-(--ink) transition hover:border-(--accent)"
            >
              {label}
            </a>
          ))}
        </nav>
      </header>

      <div className="mx-auto max-w-[1080px] px-4 py-7 sm:px-6 sm:py-10">
        <section
          className="dufynd-catalog-discovery-hero"
          aria-labelledby="dufynd-catalog-discovery-heading"
        >
          <div
            aria-hidden
            className="dufynd-catalog-discovery-atmosphere"
          />
          <div
            aria-hidden
            className="dufynd-catalog-discovery-orbit"
          />
          <div className="dufynd-catalog-discovery-copy">
            <div className="text-[10.5px] font-semibold uppercase tracking-[0.16em] text-white/55">
              DUFYND Duftkatalog
            </div>
            <h1
              id="dufynd-catalog-discovery-heading"
              className="mt-2 max-w-xl text-[34px] font-semibold leading-[1.02] tracking-[-0.045em] text-white sm:text-[46px]"
            >
              Parfums entdecken,
              <span className="block text-white/58">
                bevor du sie riechst.
              </span>
            </h1>
            <p className="mt-4 max-w-xl text-[13px] leading-6 text-white/60 sm:text-[14px]">
              Vergleiche Duftprofile, Community-Erfahrungen, Haltbarkeit
              und Ausstrahlung. Aktuelle Händlerangebote werden auf den
              jeweiligen Duftseiten separat geprüft.
            </p>

            <div className="mt-5 flex flex-wrap gap-2 text-[10.5px] text-white/62 sm:text-[11px]">
              <span className="dufynd-catalog-discovery-pill">
                {fragrances.length} Düfte
              </span>
              <span className="dufynd-catalog-discovery-pill">
                Community-Daten
              </span>
              <span className="dufynd-catalog-discovery-pill">
                aktuelle Händlerchecks
              </span>
            </div>

            <div className="mt-6 flex flex-wrap gap-2.5">
              <a
                href="#dufynd-katalog"
                className="rounded-xl bg-[#d9bd82] px-4 py-2.5 text-[12px] font-semibold text-[#241b0e] shadow-sm transition hover:-translate-y-0.5 hover:bg-[#e4cb98]"
              >
                Katalog öffnen ↓
              </a>
              <a
                href="/"
                className="rounded-xl border border-white/12 bg-white/[0.055] px-4 py-2.5 text-[12px] font-semibold text-white/82 transition hover:border-white/22 hover:bg-white/[0.08]"
              >
                Duftberatung starten
              </a>
            </div>
          </div>

          <div
            className="dufynd-catalog-discovery-stage"
            aria-label="Community-Fokus aus dem aktuellen DUFYND Katalog"
          >
            {catalogSpotlights.map((fragrance, index) => {
              const visual =
                fragrance.presentation_visual ||
                fragrance.preferred_visual;
              const isProductTruth =
                isVerifiedProductTruthVisual(visual);

              return (
                <a
                  key={fragrance.product_id}
                  href={`/duft/${fragrance.slug}`}
                  className="dufynd-catalog-discovery-bottle"
                  data-dufynd-discovery-slot={index + 1}
                  aria-label={`${fragrance.brand} ${fragrance.name} öffnen`}
                >
                  <div className="dufynd-catalog-discovery-bottle-stage">
                    {visual ? (
                      <FragranceVisual
                        imageUrl={visual.url}
                        cutoutUrl={
                          isProductTruth ? visual.url : undefined
                        }
                        backdropUrl={
                          isProductTruth
                            ? fragrance.backdrop_visual?.url
                            : undefined
                        }
                        alt={`${fragrance.brand} ${fragrance.name}`}
                        variant="card"
                        mode={
                          isProductTruth ? "cutout" : "editorial"
                        }
                        world={visualWorldFor(fragrance)}
                        className="h-full w-full"
                        priority={index === 0}
                      />
                    ) : (
                      <div className="grid h-full place-items-center text-[9px] font-semibold tracking-[0.16em] text-white/55">
                        DUFYND
                      </div>
                    )}
                  </div>
                  <div className="dufynd-catalog-discovery-meta">
                    <span>{fragrance.brand}</span>
                    <strong>{fragrance.name}</strong>
                    <em>
                      {fragrance.community.rating_count.toLocaleString(
                        "de-DE",
                      )}{" "}
                      Community-Bewertungen
                    </em>
                  </div>
                </a>
              );
            })}
          </div>
        </section>

        <div
          id="dufynd-katalog"
          className="dufynd-catalog-intro scroll-mt-5 pt-7 sm:pt-9"
        >
          <div className="max-w-3xl">
            <div className="text-[11px] font-semibold uppercase tracking-[0.12em] text-(--ink-soft)">
              Entdecken
            </div>
            <h2 className="mt-2 text-[28px] font-semibold leading-[1.08] tracking-[-0.035em] sm:text-[34px]">
              Finde deinen nächsten Duft
            </h2>
          </div>
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
