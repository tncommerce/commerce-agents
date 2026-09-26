import type { Metadata } from "next";

import AcquisitionAnalytics from "@/components/AcquisitionAnalytics";
import LegalFooter from "@/components/LegalFooter";

export const metadata: Metadata = {
  title: "DUFYND – Duftfinder, Alternativen & Geschenkberatung",
  description:
    "Starte bei DUFYND mit Duftfinder, Parfum-Alternativen oder Geschenkberatung.",
  alternates: {
    canonical: "/start",
  },
};

const paths = [
  {
    href: "/duftfinder",
    eyebrow: "Für dich selbst",
    title: "Duftfinder",
    text: "Sag, was du magst, wann du den Duft tragen willst und welches Budget du hast. DUFYND hilft dir, passende Profile einzugrenzen.",
    cta: "Duft finden",
  },
  {
    href: "/parfum-alternativen",
    eyebrow: "Original & ähnliche Profile",
    title: "Parfum-Alternativen",
    text: "Vergleiche Düfte anhand ihres Profils und finde Alternativen, ohne pauschale 1:1-Versprechen.",
    cta: "Alternativen vergleichen",
  },
  {
    href: "/parfum-geschenkberater",
    eyebrow: "Für jemand anderen",
    title: "Geschenkberater",
    text: "Grenze ein passendes Parfum nach Person, Anlass, Stil und Budget ein, statt nur nach Bekanntheit zu kaufen.",
    cta: "Geschenk finden",
  },
];

export default function SocialStartPage() {
  return (
    <main className="min-h-screen bg-(--ground) px-4 py-8 text-(--ink) sm:px-6 sm:py-12">
      <AcquisitionAnalytics source="social_start" />
      <div className="mx-auto max-w-4xl">
        <a
          href="/"
          className="inline-flex items-center gap-2 text-[13px] font-semibold text-(--accent-ink) hover:underline"
        >
          <span
            aria-hidden
            className="grid h-7 w-7 place-items-center rounded-lg bg-(--ink) text-[13px] font-bold text-white"
          >
            D
          </span>
          DUFYND
        </a>

        <section className="mt-6 rounded-3xl border border-(--line) bg-(--card) p-5 shadow-(--shadow-sm) sm:p-8">
          <div className="text-[11px] font-semibold uppercase tracking-[0.11em] text-(--ink-soft)">
            Dein Einstieg
          </div>
          <h1 className="mt-2 max-w-3xl text-[32px] font-semibold leading-[1.08] tracking-[-0.035em] sm:text-[44px]">
            Welcher Duftweg passt gerade zu dir?
          </h1>
          <p className="mt-4 max-w-2xl text-[15px] leading-7 text-(--ink-2)">
            DUFYND hilft dir nicht nur beim Finden eines Parfums. Du kannst
            deinen eigenen Duft suchen, Alternativen vergleichen oder ein
            Geschenk eingrenzen – transparent und ohne Empfehlungen nach
            Provision zu sortieren.
          </p>
        </section>

        <section className="mt-5 grid gap-3 md:grid-cols-3">
          {paths.map((item) => (
            <a
              key={item.href}
              href={item.href}
              className="group rounded-2xl border border-(--line) bg-(--card) p-5 shadow-(--shadow-sm) transition hover:-translate-y-0.5 hover:border-(--accent)"
            >
              <div className="text-[10.5px] font-semibold uppercase tracking-[0.1em] text-(--ink-soft)">
                {item.eyebrow}
              </div>
              <h2 className="mt-2 text-[20px] font-semibold tracking-[-0.02em]">
                {item.title}
              </h2>
              <p className="mt-2 text-[12.5px] leading-5 text-(--ink-soft)">
                {item.text}
              </p>
              <span className="mt-5 inline-flex text-[12.5px] font-semibold text-(--accent-ink) group-hover:underline">
                {item.cta} →
              </span>
            </a>
          ))}
        </section>

        <section className="mt-5 rounded-2xl border border-(--line) bg-(--well)/45 p-4 text-[12.5px] leading-6 text-(--ink-2)">
          <strong className="text-(--ink)">Empfehlungen vor Provision.</strong>{" "}
          DUFYND soll zuerst den passenden Duft oder die passende Richtung
          finden. Händlerlinks können Partnerlinks sein; eine mögliche
          Provision beeinflusst nie die Duftempfehlung. Bei gleichem Gesamtpreis
          und vergleichbarer Aktualität kann ein Partnerlink bevorzugt werden;
          zwischen solchen Links kann die höhere Provision entscheiden.{" "}
          <a
            href="/transparenz"
            className="font-semibold text-(--accent-ink) hover:underline"
          >
            So arbeitet DUFYND
          </a>
          .
        </section>

        <LegalFooter />
      </div>
    </main>
  );
}
