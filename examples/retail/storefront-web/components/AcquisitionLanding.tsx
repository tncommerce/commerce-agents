import AcquisitionAnalytics from "@/components/AcquisitionAnalytics";
import GuidedAdvisorLink from "@/components/GuidedAdvisorLink";
import LegalFooter from "@/components/LegalFooter";
import type { AdvisorStartKey } from "@/lib/advisorStarts";

type SecondaryStart = {
  key: AdvisorStartKey;
  label: string;
};

export default function AcquisitionLanding({
  analyticsSource,
  eyebrow,
  title,
  intro,
  primaryStart,
  primaryLabel,
  secondaryStarts = [],
  points,
  trustNote,
}: {
  analyticsSource: string;
  eyebrow: string;
  title: string;
  intro: string;
  primaryStart: AdvisorStartKey;
  primaryLabel: string;
  secondaryStarts?: SecondaryStart[];
  points: Array<{
    title: string;
    text: string;
  }>;
  trustNote: string;
}) {
  return (
    <main className="min-h-screen bg-(--ground) px-4 py-8 text-(--ink) sm:px-6 sm:py-12">
      <AcquisitionAnalytics source={analyticsSource} />
      <div className="mx-auto max-w-4xl">
        <a
          href="/"
          className="inline-flex items-center gap-2 text-[13px] font-semibold text-(--accent-ink) hover:underline"
        >
          <span
            aria-hidden
            className="grid h-7 w-7 place-items-center rounded-lg bg-(--ink) text-[13px] font-bold text-white"
          >
            S
          </span>
          DUFYND
        </a>

        <section className="mt-6 rounded-3xl border border-(--line) bg-(--card) p-5 shadow-(--shadow-sm) sm:p-8">
          <div className="text-[11px] font-semibold uppercase tracking-[0.11em] text-(--ink-soft)">
            {eyebrow}
          </div>
          <h1 className="mt-2 max-w-3xl text-[32px] font-semibold leading-[1.08] tracking-[-0.035em] sm:text-[44px]">
            {title}
          </h1>
          <p className="mt-4 max-w-2xl text-[15px] leading-7 text-(--ink-2)">
            {intro}
          </p>

          <div className="mt-6 flex flex-wrap gap-2.5">
            <GuidedAdvisorLink
              start={primaryStart}
              className="rounded-xl bg-(--accent-strong) px-4 py-2.5 text-[13px] font-semibold text-white transition hover:brightness-95"
            >
              {primaryLabel}
            </GuidedAdvisorLink>
            <a
              href="/duft"
              className="rounded-xl border border-(--line-strong) bg-(--surface) px-4 py-2.5 text-[13px] font-semibold text-(--ink) transition hover:border-(--accent)"
            >
              Erst im Katalog stöbern
            </a>
          </div>

          {secondaryStarts.length ? (
            <div className="mt-4 flex flex-wrap gap-2">
              {secondaryStarts.map((item) => (
                <GuidedAdvisorLink
                  key={item.key}
                  start={item.key}
                  className="rounded-full border border-(--line) bg-(--well)/45 px-3 py-1.5 text-[11.5px] font-medium text-(--accent-ink) hover:border-(--accent)"
                >
                  {item.label}
                </GuidedAdvisorLink>
              ))}
            </div>
          ) : null}
        </section>

        <section className="mt-5 grid gap-3 sm:grid-cols-3">
          {points.map((point) => (
            <article
              key={point.title}
              className="rounded-2xl border border-(--line) bg-(--card) p-4 shadow-(--shadow-sm)"
            >
              <h2 className="text-[14px] font-semibold">
                {point.title}
              </h2>
              <p className="mt-1.5 text-[12.5px] leading-5 text-(--ink-soft)">
                {point.text}
              </p>
            </article>
          ))}
        </section>

        <section className="mt-5 rounded-2xl border border-(--line) bg-(--well)/45 p-4 text-[12.5px] leading-6 text-(--ink-2)">
          <strong className="text-(--ink)">
            Empfehlungen vor Provision.
          </strong>{" "}
          {trustNote} Händlerlinks können Partnerlinks sein. Eine
          mögliche Provision beeinflusst weder die Duftempfehlung noch
          die Reihenfolge der Händlerangebote.{" "}
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
