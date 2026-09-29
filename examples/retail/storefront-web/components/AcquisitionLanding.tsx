import AcquisitionAnalytics from "@/components/AcquisitionAnalytics";
import GuidedAdvisorLink from "@/components/GuidedAdvisorLink";
import LegalFooter from "@/components/LegalFooter";
import FragranceVisual from "@/components/FragranceVisual";
import type { AdvisorStartKey } from "@/lib/advisorStarts";
import {
  isVerifiedProductTruthVisual,
  LIVE_FRAGRANCES,
} from "@/lib/fragranceCatalog";

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
  const fragranceCount = LIVE_FRAGRANCES.length;
  const acquisitionSpotlights = [...LIVE_FRAGRANCES]
    .filter((fragrance) => Boolean(fragrance.preferred_visual?.url))
    .sort(
      (a, b) =>
        b.community.rating_count - a.community.rating_count ||
        a.brand.localeCompare(b.brand, "de"),
    )
    .slice(0, 3);

  return (
    <main className="min-h-screen overflow-hidden bg-[#f5f0e8] text-(--ink)">
      <AcquisitionAnalytics source={analyticsSource} />

      <div className="mx-auto w-full max-w-[1040px] px-4 py-5 sm:px-6 sm:py-8">
        <header className="flex items-center justify-between gap-4">
          <a
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
          </a>

          <a
            href="/duft"
            className="rounded-full border border-(--line) bg-white/60 px-3 py-1.5 text-[11.5px] font-semibold text-(--ink) backdrop-blur-sm transition hover:border-(--ink)"
          >
            {fragranceCount} Düfte
          </a>
        </header>

        <section
          className="dufynd-acquisition-hero relative mt-5 isolate overflow-hidden rounded-[30px] border border-white/10 px-5 py-7 text-[#fffdf8] shadow-[0_28px_80px_-44px_rgba(23,21,19,0.9)] sm:px-8 sm:py-10 lg:px-11 lg:py-11"
          style={{
            background:
              "radial-gradient(circle at 82% 12%, rgba(204, 160, 77, 0.25), transparent 28%), radial-gradient(circle at 8% 90%, rgba(96, 76, 54, 0.17), transparent 32%), linear-gradient(135deg, #171719 0%, #0a0b0d 72%)",
          }}
        >
          <div
            aria-hidden
            className="pointer-events-none absolute -right-[13%] top-[5%] h-[360px] w-[360px] rounded-full border border-[#d7ad5a]/20 opacity-60 shadow-[0_0_100px_rgba(215,173,90,0.08)] sm:h-[480px] sm:w-[480px]"
          />
          <div
            aria-hidden
            className="pointer-events-none absolute right-[10%] top-[17%] h-[240px] w-[240px] rounded-full border border-white/[0.06] opacity-55 sm:h-[330px] sm:w-[330px]"
          />
          <div
            aria-hidden
            className="pointer-events-none absolute inset-0 bg-[linear-gradient(115deg,rgba(255,255,255,0.035),transparent_30%,transparent_72%,rgba(255,255,255,0.02))]"
          />

          <div className="dufynd-acquisition-hero-grid relative z-10 grid gap-7 lg:grid-cols-[1.08fr_0.92fr] lg:items-center">
            <div className="dufynd-acquisition-copy max-w-3xl">
            <div className="inline-flex items-center gap-2 rounded-full border border-white/10 bg-white/[0.05] px-3 py-1.5 text-[10px] font-semibold uppercase tracking-[0.17em] text-[#e6c77f] backdrop-blur-md">
              <span className="h-1.5 w-1.5 rounded-full bg-[#d8ad55] shadow-[0_0_14px_rgba(216,173,85,0.9)]" />
              {eyebrow}
            </div>

            <h1 className="mt-5 max-w-3xl text-[33px] font-semibold leading-[1.01] tracking-[-0.043em] sm:text-[46px] lg:text-[54px]">
              {title}
            </h1>
            <p className="mt-4 max-w-2xl text-[13px] leading-6 text-white/[0.68] sm:text-[14.5px] sm:leading-7">
              {intro}
            </p>

            <div className="mt-6 flex flex-wrap gap-2.5">
              <GuidedAdvisorLink
                start={primaryStart}
                className="rounded-xl bg-[#fffdf8] px-4 py-2.5 text-[12.5px] font-semibold text-[#171513] shadow-[0_12px_30px_-18px_rgba(255,241,210,0.75)] transition hover:-translate-y-0.5"
              >
                {primaryLabel}
              </GuidedAdvisorLink>
              <a
                href="/duft"
                className="rounded-xl border border-white/15 bg-white/[0.055] px-4 py-2.5 text-[12.5px] font-semibold text-white/[0.88] backdrop-blur-md transition hover:-translate-y-0.5 hover:bg-white/[0.09]"
              >
                Katalog entdecken
              </a>
            </div>

            {secondaryStarts.length ? (
              <div className="mt-5 flex flex-wrap gap-2 border-t border-white/[0.08] pt-4">
                {secondaryStarts.map((item) => (
                  <GuidedAdvisorLink
                    key={item.key}
                    start={item.key}
                    className="rounded-full border border-white/10 bg-black/[0.15] px-3 py-1.5 text-[10.5px] font-medium text-white/[0.62] backdrop-blur-sm transition hover:border-white/20 hover:text-white/[0.86]"
                  >
                    {item.label}
                  </GuidedAdvisorLink>
                ))}
              </div>
            ) : null}
            </div>

            {acquisitionSpotlights.length ? (
              <div
                className="dufynd-acquisition-stage"
                aria-label="Auswahl aus dem aktuellen DUFYND Katalog"
              >
                <div
                  aria-hidden
                  className="dufynd-acquisition-stage-glow"
                />
                {acquisitionSpotlights.map((fragrance, index) => {
                  const visual = fragrance.preferred_visual;
                  const isProductTruth =
                    isVerifiedProductTruthVisual(visual);

                  return (
                    <a
                      key={fragrance.product_id}
                      href={`/duft/${fragrance.slug}`}
                      className="dufynd-acquisition-bottle"
                      data-dufynd-acquisition-slot={index + 1}
                      aria-label={`${fragrance.brand} ${fragrance.name} im Katalog öffnen`}
                    >
                      <div className="dufynd-acquisition-bottle-visual">
                        <FragranceVisual
                          imageUrl={visual?.url}
                          cutoutUrl={
                            isProductTruth ? visual?.url : undefined
                          }
                          alt={`${fragrance.brand} ${fragrance.name}`}
                          variant="card"
                          mode={
                            isProductTruth ? "cutout" : "editorial"
                          }
                          className="h-full w-full"
                          priority={index === 0}
                        />
                      </div>
                      <div className="dufynd-acquisition-bottle-meta">
                        <span>{fragrance.brand}</span>
                        <strong>{fragrance.name}</strong>
                      </div>
                    </a>
                  );
                })}
                <div className="dufynd-acquisition-stage-label">
                  <span>Aus dem Katalog</span>
                  <strong>{fragranceCount} Live-Düfte</strong>
                </div>
              </div>
            ) : null}
          </div>
        </section>

        <section
          className="mt-4 grid gap-3 sm:grid-cols-3"
          aria-label="So hilft DUFYND"
        >
          {points.map((point, index) => (
            <article
              key={point.title}
              className="dufynd-acquisition-point group rounded-[22px] border border-(--line) bg-[#fffdf8] p-5 shadow-[0_12px_34px_-28px_rgba(23,21,19,0.55)]"
            >
              <div className="flex items-start justify-between gap-3">
                <span className="text-[10px] font-semibold uppercase tracking-[0.12em] text-[#9a7636]">
                  DUFYND
                </span>
                <span className="text-[10px] font-semibold tracking-[0.12em] text-(--ink-faint)">
                  {String(index + 1).padStart(2, "0")}
                </span>
              </div>
              <h2 className="mt-5 text-[15px] font-semibold leading-5 tracking-[-0.015em]">
                {point.title}
              </h2>
              <p className="mt-2 text-[12px] leading-5 text-(--ink-soft)">
                {point.text}
              </p>
            </article>
          ))}
        </section>

        <section className="mt-4 grid gap-3 rounded-[22px] border border-(--line) bg-white/[0.62] p-4 shadow-(--shadow-sm) backdrop-blur-sm sm:grid-cols-[auto_1fr] sm:items-center sm:p-5">
          <div className="rounded-xl bg-(--ink) px-3 py-2 text-center text-[10px] font-semibold uppercase tracking-[0.12em] text-white">
            Transparent
          </div>
          <p className="text-[11.5px] leading-5 text-(--ink-soft) sm:text-[12px]">
            <strong className="text-(--ink)">
              Empfehlungen vor Provision.
            </strong>{" "}
            {trustNote} Händlerlinks können Partnerlinks sein. Eine mögliche
            Provision beeinflusst nie die Duftempfehlung. Bei preisgleichen,
            vergleichbar aktuellen Händlerangeboten kann sie zwischen
            Partnerlinks entscheiden.{" "}
            <a
              href="/transparenz"
              className="font-semibold text-(--accent-ink) hover:underline"
            >
              So arbeitet DUFYND
            </a>
            .
          </p>
        </section>

        <LegalFooter />
      </div>
    </main>
  );
}
