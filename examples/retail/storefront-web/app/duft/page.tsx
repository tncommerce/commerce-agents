import type { Metadata } from "next";

import {
  LIVE_FRAGRANCES,
  type StaticFragrance,
} from "@/lib/fragranceCatalog";

export const metadata: Metadata = {
  title: "Parfums entdecken",
  description:
    "Entdecke das SCENTAI Duftsortiment mit Duftprofil, Community-Bewertungen, Haltbarkeit und aktuellen Händlerangeboten.",
  alternates: {
    canonical: "/duft",
  },
};

function ratingLabel(
  fragrance: StaticFragrance,
): string | null {
  if (fragrance.community.rating_10 == null) return null;

  return `${fragrance.community.rating_10.toLocaleString(
    "de-DE",
    {
      minimumFractionDigits: 1,
      maximumFractionDigits: 1,
    },
  )}/10`;
}

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
          <a
            href="/"
            className="rounded-xl border border-(--line) px-3 py-2 text-[12px] font-semibold text-(--ink) transition hover:border-(--ink)"
          >
            Duftberatung öffnen
          </a>
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

        <section className="mt-7 grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
          {fragrances.map((fragrance) => (
            <a
              key={fragrance.product_id}
              href={`/duft/${fragrance.slug}`}
              className="group overflow-hidden rounded-2xl border border-(--line) bg-(--card) shadow-(--shadow-sm) transition hover:-translate-y-0.5 hover:shadow-md"
            >
              <div className="flex h-52 items-center justify-center bg-white p-4">
                {fragrance.image_url ? (
                  // eslint-disable-next-line @next/next/no-img-element
                  <img
                    src={fragrance.image_url}
                    alt={`${fragrance.brand} ${fragrance.name}`}
                    className="h-full w-full object-contain transition duration-200 group-hover:scale-[1.02]"
                  />
                ) : (
                  <div className="text-[12px] font-semibold tracking-[0.16em] text-(--ink-soft)">
                    SCENTAI
                  </div>
                )}
              </div>

              <div className="p-4">
                <div className="text-[10.5px] font-medium uppercase tracking-[0.08em] text-(--ink-soft)">
                  {fragrance.brand}
                </div>
                <h2 className="mt-1 text-[16px] font-semibold leading-5">
                  {fragrance.name}
                </h2>

                <div className="mt-2 flex flex-wrap gap-1.5 text-[10.5px] text-(--ink-soft)">
                  <span>
                    {fragrance.concentration}
                  </span>
                  <span>·</span>
                  <span>{fragrance.volume_ml} ml</span>
                  {ratingLabel(fragrance) ? (
                    <>
                      <span>·</span>
                      <span className="font-semibold text-(--ink)">
                        {ratingLabel(fragrance)}
                      </span>
                    </>
                  ) : null}
                </div>

                <div className="mt-3 flex flex-wrap gap-1.5">
                  {fragrance.accords
                    .slice(0, 3)
                    .map((accord) => (
                      <span
                        key={accord}
                        className="rounded-full bg-(--well) px-2 py-1 text-[10.5px] text-(--ink-soft)"
                      >
                        {accord}
                      </span>
                    ))}
                </div>

                <div className="mt-4 border-t border-(--line) pt-3 text-[11px] font-semibold text-(--accent-ink)">
                  Duftprofil & Angebote ansehen →
                </div>
              </div>
            </a>
          ))}
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
