import type { Metadata } from "next";

import AcquisitionAnalytics from "@/components/AcquisitionAnalytics";
import AcquisitionInternalLink from "@/components/AcquisitionInternalLink";
import LegalFooter from "@/components/LegalFooter";
import SocialFragranceSearch from "@/components/SocialFragranceSearch";
import FragranceVariantLinks from "@/components/FragranceVariantLinks";
import { LIVE_FRAGRANCES } from "@/lib/fragranceCatalog";
import { SITE_INDEXABLE } from "@/lib/site";

export const metadata: Metadata = {
  title: "DUFYND – Duftfinder, Katalog, Alternativen & Geschenkberatung",
  description:
    "Starte bei DUFYND mit Duftfinder, Duftkatalog, Parfum-Alternativen oder Geschenkberatung.",
  alternates: {
    canonical: "/start",
  },
  robots: {
    index: false,
    follow: SITE_INDEXABLE,
    nocache: true,
  },
};

const paths = [
  {
    href: "/duftfinder",
    number: "01",
    eyebrow: "Persönliche Beratung",
    title: "Meinen Duft finden",
    text: "Grenze mit Anlass, Budget, Duftprofil, Haltbarkeit und Ausstrahlung ein, was wirklich zu dir passt.",
    cta: "Duftfinder starten",
  },
  {
    href: "/duft",
    number: "02",
    eyebrow: "Selbst entdecken",
    title: "Duftkatalog",
    text: "Stöbere durch Duftprofile, Community-Daten und verfügbare Händlerangebote in deinem eigenen Tempo.",
    cta: "Katalog entdecken",
  },
  {
    href: "/parfum-alternativen",
    number: "03",
    eyebrow: "Profile vergleichen",
    title: "Alternativen finden",
    text: "Vergleiche ähnliche Duftrichtungen transparent, ohne pauschale 1:1-Versprechen oder erfundene Gleichheit.",
    cta: "Alternativen vergleichen",
  },
  {
    href: "/parfum-geschenkberater",
    number: "04",
    eyebrow: "Für jemand anderen",
    title: "Parfum verschenken",
    text: "Grenze ein Geschenk nach Person, Anlass, Stil und Budget ein, statt nur nach Bekanntheit auszuwählen.",
    cta: "Geschenk finden",
  },
];

export default function SocialStartPage() {
  const fragranceCount = LIVE_FRAGRANCES.length;
  const searchableFragrances = LIVE_FRAGRANCES.map((fragrance) => ({
    product_id: fragrance.product_id,
    slug: fragrance.slug,
    brand: fragrance.brand,
    name: fragrance.name,
    concentration: fragrance.concentration,
    volume_ml: fragrance.volume_ml,
  }));

  return (
    <main className="min-h-screen overflow-hidden bg-[#f5f0e8] text-(--ink)">
      <AcquisitionAnalytics source="social_start" />

      <div className="mx-auto w-full max-w-[1120px] px-4 py-5 sm:px-6 sm:py-8">
        <header className="flex items-center justify-between gap-4">
          <AcquisitionInternalLink
            href="/"
            className="inline-flex items-center gap-2.5"
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

          <AcquisitionInternalLink
            href="/duft"
            className="rounded-full border border-(--line) bg-white/60 px-3 py-1.5 text-[11.5px] font-semibold text-(--ink) backdrop-blur-sm transition hover:border-(--ink)"
          >
            {fragranceCount} Düfte entdecken
          </AcquisitionInternalLink>
        </header>

        <section
          className="relative mt-5 isolate overflow-hidden rounded-[30px] border border-white/10 px-5 py-7 text-[#fffdf8] shadow-[0_28px_80px_-44px_rgba(23,21,19,0.9)] sm:px-8 sm:py-10 lg:px-12 lg:py-12"
          style={{
            background:
              "radial-gradient(circle at 78% 18%, rgba(206, 162, 79, 0.26), transparent 27%), radial-gradient(circle at 14% 92%, rgba(112, 83, 49, 0.18), transparent 31%), linear-gradient(135deg, #171719 0%, #0a0b0d 72%)",
          }}
        >
          <div
            aria-hidden
            className="pointer-events-none absolute -right-[12%] top-[6%] h-[360px] w-[360px] rounded-full border border-[#d7ad5a]/20 opacity-60 shadow-[0_0_100px_rgba(215,173,90,0.08)] sm:h-[500px] sm:w-[500px]"
          />
          <div
            aria-hidden
            className="pointer-events-none absolute right-[8%] top-[17%] h-[250px] w-[250px] rounded-full border border-white/[0.06] opacity-60 sm:h-[350px] sm:w-[350px]"
          />
          <div
            aria-hidden
            className="pointer-events-none absolute inset-0 bg-[linear-gradient(115deg,rgba(255,255,255,0.035),transparent_28%,transparent_72%,rgba(255,255,255,0.02))]"
          />

          <div className="relative z-10 max-w-3xl">
            <div className="inline-flex items-center gap-2 rounded-full border border-white/10 bg-white/[0.05] px-3 py-1.5 text-[10px] font-semibold uppercase tracking-[0.17em] text-[#e6c77f] backdrop-blur-md">
              <span className="h-1.5 w-1.5 rounded-full bg-[#d8ad55] shadow-[0_0_14px_rgba(216,173,85,0.9)]" />
              Dein Einstieg in DUFYND
            </div>

            <h1 className="mt-5 max-w-3xl text-[34px] font-semibold leading-[0.98] tracking-[-0.045em] sm:text-[48px] lg:text-[58px]">
              Finde deinen schnellsten Weg zum passenden Duft.
            </h1>
            <p className="mt-4 max-w-2xl text-[13px] leading-6 text-white/[0.68] sm:text-[15px] sm:leading-7">
              Kommst du aus einem Short, einer Suche oder mit einem konkreten
              Parfum im Kopf? Starte direkt dort, wo dein Bedarf liegt:
              persönliche Beratung, freies Entdecken, Alternativen oder
              Geschenkideen.
            </p>

            <div className="mt-6 flex flex-wrap gap-2.5">
              <AcquisitionInternalLink
                href="/duftfinder"
                className="rounded-xl bg-[#fffdf8] px-4 py-2.5 text-[12.5px] font-semibold text-[#171513] shadow-[0_12px_30px_-18px_rgba(255,241,210,0.75)] transition hover:-translate-y-0.5"
              >
                Duftfinder starten
              </AcquisitionInternalLink>
              <AcquisitionInternalLink
                href="/duft"
                className="rounded-xl border border-white/15 bg-white/[0.055] px-4 py-2.5 text-[12.5px] font-semibold text-white/[0.88] backdrop-blur-md transition hover:-translate-y-0.5 hover:bg-white/[0.09]"
              >
                Katalog entdecken
              </AcquisitionInternalLink>
            </div>

            <div className="mt-7 flex flex-wrap gap-x-4 gap-y-2 border-t border-white/[0.08] pt-4 text-[10.5px] font-medium text-white/[0.48]">
              <span>Duftprofil statt Hype</span>
              <span>Community-Daten</span>
              <span>Transparente Händlerangebote</span>
            </div>
          </div>
        </section>

        <section
          aria-labelledby="dufynd-social-direct-search-heading"
          className="relative z-20 mt-4 rounded-[22px] border border-(--line) bg-white/[0.72] p-4 shadow-(--shadow-sm) backdrop-blur-sm sm:p-5"
        >
          <div className="grid gap-3 lg:grid-cols-[0.8fr_1.2fr] lg:items-center">
            <div>
              <div className="text-[9.5px] font-semibold uppercase tracking-[0.14em] text-(--accent-ink)">
                Konkreten Duft im Kopf?
              </div>
              <h2
                id="dufynd-social-direct-search-heading"
                className="mt-1 text-[17px] font-semibold tracking-[-0.02em] text-(--ink)"
              >
                Duft oder Marke direkt suchen
              </h2>
              <p className="mt-1 text-[11.5px] leading-5 text-(--ink-soft)">
                Spring direkt aus dem Short zur passenden Katalogsuche.
              </p>
            </div>

            <SocialFragranceSearch fragrances={searchableFragrances} />
          </div>
          <FragranceVariantLinks />
        </section>

        <section
          className="mt-4 grid gap-3 sm:grid-cols-2 lg:grid-cols-4"
          aria-label="DUFYND Wege"
        >
          {paths.map((item) => (
            <AcquisitionInternalLink
              key={item.href}
              href={item.href}
              className="group relative flex min-h-[210px] flex-col overflow-hidden rounded-[22px] border border-(--line) bg-[#fffdf8] p-5 shadow-[0_12px_34px_-28px_rgba(23,21,19,0.55)] transition duration-200 hover:-translate-y-0.5 hover:border-[#b88934]/45 hover:shadow-[0_18px_42px_-28px_rgba(23,21,19,0.62)]"
            >
              <div className="flex items-start justify-between gap-3">
                <div className="text-[10px] font-semibold uppercase tracking-[0.13em] text-(--ink-soft)">
                  {item.eyebrow}
                </div>
                <span className="text-[10px] font-semibold tracking-[0.12em] text-[#a37a31]">
                  {item.number}
                </span>
              </div>

              <h2 className="mt-5 text-[20px] font-semibold leading-6 tracking-[-0.025em]">
                {item.title}
              </h2>
              <p className="mt-2 text-[12px] leading-5 text-(--ink-soft)">
                {item.text}
              </p>

              <div className="mt-auto pt-5">
                <span className="inline-flex items-center gap-2 text-[11.5px] font-semibold text-(--accent-ink)">
                  {item.cta}
                  <span
                    aria-hidden
                    className="transition-transform group-hover:translate-x-0.5"
                  >
                    →
                  </span>
                </span>
              </div>
            </AcquisitionInternalLink>
          ))}
        </section>

        <section className="mt-4 grid gap-3 rounded-[22px] border border-(--line) bg-white/[0.62] p-4 shadow-(--shadow-sm) backdrop-blur-sm sm:grid-cols-[auto_1fr] sm:items-center sm:p-5">
          <div className="rounded-xl bg-(--ink) px-3 py-2 text-center text-[10px] font-semibold uppercase tracking-[0.12em] text-white">
            Transparent
          </div>
          <p className="text-[11.5px] leading-5 text-(--ink-soft) sm:text-[12px]">
            <strong className="text-(--ink)">Empfehlungen vor Provision.</strong>{" "}
            DUFYND soll zuerst den passenden Duft oder die passende Richtung
            finden. Händlerlinks können Partnerlinks sein; eine mögliche
            Provision beeinflusst nie die Duftempfehlung. Bei preisgleichen,
            vergleichbar aktuellen Angeboten kann sie zwischen Partnerlinks
            entscheiden.{" "}
            <AcquisitionInternalLink
              href="/transparenz"
              className="font-semibold text-(--accent-ink) hover:underline"
            >
              So arbeitet DUFYND
            </AcquisitionInternalLink>
            .
          </p>
        </section>

        <LegalFooter />
      </div>
    </main>
  );
}
