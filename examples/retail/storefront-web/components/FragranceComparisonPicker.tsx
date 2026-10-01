"use client";

import { useEffect, useMemo, useRef, useState } from "react";

import FragranceOffers from "@/components/FragranceOffers";
import FragranceModel3D from "@/components/FragranceModel3D";
import FragranceVisual from "@/components/FragranceVisual";
import { appendAcquisitionAttribution, trackAnalyticsEvent } from "@/lib/analytics";
import { accordLabel } from "@/lib/accordLabels";
import {
  isVerifiedProductTruthVisual,
  visualWorldFor,
  type StaticFragrance,
} from "@/lib/fragranceCatalog";
import { formatPriceReference } from "@/lib/priceReference";
import { publicShareUrl } from "@/lib/shareUrl";
import ManualShareLink from "@/components/ManualShareLink";
import { targetGroupLabel } from "@/lib/targetLabels";

function formatRating(
  value: number | null,
  provisional = false,
): string {
  if (value == null) return "–";
  const rating = `${value.toLocaleString("de-DE", {
    minimumFractionDigits: 1,
    maximumFractionDigits: 1,
  })}/10`;

  return provisional ? `${rating} · vorläufig` : rating;
}

function formatNumber(
  value: number | null,
  provisional = false,
): string {
  if (value == null) return "–";
  const formatted = value.toLocaleString("de-DE", {
    minimumFractionDigits: 1,
    maximumFractionDigits: 1,
  });
  return provisional ? `${formatted} · vorläufig` : formatted;
}

function ComparisonRow({
  label,
  left,
  right,
}: {
  label: string;
  left: React.ReactNode;
  right: React.ReactNode;
}) {
  return (
    <div
      role="row"
      className="grid grid-cols-[1fr_0.85fr_1fr] items-center gap-2 border-t border-(--line) px-3 py-3 text-[12px] sm:gap-3 sm:px-4"
    >
      <div role="cell" className="text-right font-medium text-(--ink)">
        {left}
      </div>
      <div
        role="rowheader"
        className="text-center text-[10px] font-semibold uppercase tracking-[0.06em] text-(--ink-soft)"
      >
        {label}
      </div>
      <div role="cell" className="font-medium text-(--ink)">
        {right}
      </div>
    </div>
  );
}

function ProfileMeter({
  label,
  left,
  right,
}: {
  label: string;
  left: number | null;
  right: number | null;
}) {
  const width = (value: number | null) =>
    value == null ? 0 : Math.max(0, Math.min(100, value * 10));

  return (
    <div className="grid grid-cols-[1fr_auto_1fr] items-center gap-2 sm:gap-3">
      <div className="flex items-center justify-end gap-2">
        <span className="text-[10.5px] font-semibold tabular-nums text-white/75">
          {formatNumber(left)}
        </span>
        <div className="h-1.5 w-full max-w-28 overflow-hidden rounded-full bg-white/10">
          <div
            className="ml-auto h-full rounded-full bg-[#d9bd82]"
            style={{ width: `${width(left)}%` }}
          />
        </div>
      </div>
      <span className="min-w-16 text-center text-[9px] font-semibold uppercase tracking-[0.08em] text-white/45">
        {label}
      </span>
      <div className="flex items-center gap-2">
        <div className="h-1.5 w-full max-w-28 overflow-hidden rounded-full bg-white/10">
          <div
            className="h-full rounded-full bg-[#d9bd82]"
            style={{ width: `${width(right)}%` }}
          />
        </div>
        <span className="text-[10.5px] font-semibold tabular-nums text-white/75">
          {formatNumber(right)}
        </span>
      </div>
    </div>
  );
}

function ProductMiniHeader({
  fragrance,
  side,
}: {
  fragrance: StaticFragrance;
  side: "left" | "right";
}) {
  const productTruthVisual = fragrance.preferred_visual;
  const productTruthIsVerified =
    isVerifiedProductTruthVisual(productTruthVisual);
  const presentationVisual =
    fragrance.presentation_visual || productTruthVisual;
  const presentationIsProductTruth =
    isVerifiedProductTruthVisual(presentationVisual);

  return (
    <a
      href={appendAcquisitionAttribution(`/duft/${fragrance.slug}`)}
      className="dufynd-comparison-product-card overflow-hidden rounded-2xl border border-(--line) bg-(--card) shadow-(--shadow-sm)"
      data-dufynd-comparison-side={side}
    >
      {fragrance.model_3d_url ? (
        <FragranceModel3D
          modelUrl={fragrance.model_3d_url}
          imageUrl={
            productTruthIsVerified
              ? undefined
              : productTruthVisual?.url
          }
          cutoutUrl={
            productTruthIsVerified
              ? productTruthVisual?.url
              : undefined
          }
          backdropUrl={
            productTruthIsVerified
              ? fragrance.backdrop_visual?.url
              : undefined
          }
          alt={`${fragrance.brand} ${fragrance.name}`}
          className="dufynd-comparison-product-visual h-40 w-full"
        />
      ) : (
        <FragranceVisual
          imageUrl={presentationVisual?.url}
          cutoutUrl={
            presentationIsProductTruth
              ? presentationVisual?.url
              : undefined
          }
          backdropUrl={
            presentationIsProductTruth
              ? fragrance.backdrop_visual?.url
              : undefined
          }
          alt={`${fragrance.brand} ${fragrance.name}`}
          variant="card"
          mode={
            presentationIsProductTruth
              ? "cutout"
              : "editorial"
          }
          world={visualWorldFor(fragrance)}
          className="dufynd-comparison-product-visual h-40 w-full"
        />
      )}
      <div className="p-3.5">
        <div className="text-[10px] font-semibold uppercase tracking-[0.08em] text-(--ink-soft)">
          {fragrance.brand}
        </div>
        <div className="mt-1 text-[15px] font-semibold leading-5 text-(--ink)">
          {fragrance.name}
        </div>
        <div className="mt-1 text-[10.5px] text-(--ink-soft)">
          {fragrance.concentration} · {fragrance.volume_ml} ml
        </div>
      </div>
    </a>
  );
}

export default function FragranceComparisonPicker({
  fragrances,
}: {
  fragrances: StaticFragrance[];
}) {
  const sorted = useMemo(
    () =>
      [...fragrances].sort(
        (a, b) =>
          a.brand.localeCompare(b.brand, "de") ||
          a.name.localeCompare(b.name, "de"),
      ),
    [fragrances],
  );

  const [leftId, setLeftId] = useState("");
  const [rightId, setRightId] = useState("");
  const [urlReady, setUrlReady] = useState(false);
  const [copyStatus, setCopyStatus] = useState("");
  const [manualUrl, setManualUrl] = useState("");
  const copyRequestRef = useRef(0);
  const trackedPairRef = useRef<string | null>(null);

  useEffect(() => {
    const params = new URLSearchParams(window.location.search);
    const requestedLeft = params.get("left") || "";
    const requestedRight = params.get("right") || "";

    if (
      requestedLeft &&
      sorted.some(
        (fragrance) =>
          fragrance.product_id === requestedLeft,
      )
    ) {
      setLeftId(requestedLeft);
    }

    if (
      requestedRight &&
      requestedRight !== requestedLeft &&
      sorted.some(
        (fragrance) =>
          fragrance.product_id === requestedRight,
      )
    ) {
      setRightId(requestedRight);
    }
    setUrlReady(true);
  }, [sorted]);

  useEffect(() => {
    if (!urlReady) return;

    const url = new URL(window.location.href);
    if (leftId) url.searchParams.set("left", leftId);
    else url.searchParams.delete("left");
    if (rightId) url.searchParams.set("right", rightId);
    else url.searchParams.delete("right");

    const nextUrl = `${url.pathname}${url.search}${url.hash}`;
    const currentUrl = `${window.location.pathname}${window.location.search}${window.location.hash}`;
    if (nextUrl !== currentUrl) {
      window.history.replaceState(window.history.state, "", nextUrl);
    }
  }, [leftId, rightId, urlReady]);

  const copyComparisonLink = async () => {
    const request = ++copyRequestRef.current;
    const url = new URL(window.location.href);
    url.searchParams.set("left", leftId);
    url.searchParams.set("right", rightId);
    const shareUrl = publicShareUrl(url.href);
    setCopyStatus("");
    setManualUrl("");
    try {
      await navigator.clipboard.writeText(shareUrl);
      if (request !== copyRequestRef.current) return;
      setCopyStatus("Link kopiert");
    } catch {
      if (request !== copyRequestRef.current) return;
      setManualUrl(shareUrl);
      setCopyStatus("Automatisches Kopieren nicht möglich. Kopiere den Link unten.");
    }
  };

  const left =
    sorted.find(
      (fragrance) => fragrance.product_id === leftId,
    ) || null;
  const right =
    sorted.find(
      (fragrance) => fragrance.product_id === rightId,
    ) || null;

  const validPair =
    left != null &&
    right != null &&
    left.product_id !== right.product_id;

  useEffect(() => {
    if (!validPair || !left || !right) return;

    const pairKey = `${left.product_id}|${right.product_id}`;
    if (trackedPairRef.current === pairKey) return;

    trackedPairRef.current = pairKey;
    void trackAnalyticsEvent("comparison_start", {
      product_id: left.product_id,
      related_product_id: right.product_id,
      source: "comparison_hub",
      surface: "free_comparison",
    });
  }, [left, right, validPair]);

  return (
    <section className="dufynd-comparison-picker mt-8 rounded-3xl border border-(--line) bg-(--card) p-4 shadow-(--shadow-sm) sm:p-5">
      <div className="max-w-2xl">
        <div className="text-[10.5px] font-semibold uppercase tracking-[0.1em] text-(--ink-soft)">
          Freier Vergleich
        </div>
        <h2 className="mt-1 text-[22px] font-semibold tracking-[-0.02em]">
          Zwei Düfte selbst auswählen
        </h2>
        <p className="mt-2 text-[12px] leading-5 text-(--ink-soft)">
          Vergleiche beliebige Live-Düfte nach denselben DUFYND-Daten.
          Eine freie Gegenüberstellung bedeutet nicht automatisch, dass
          zwischen den Düften eine dokumentierte Duftbeziehung besteht.
        </p>
      </div>

      <div className="mt-5 grid gap-3 sm:grid-cols-2">
        <label>
          <span className="mb-1.5 block text-[11px] font-semibold uppercase tracking-[0.06em] text-(--ink-soft)">
            Duft 1
          </span>
          <select
            value={leftId}
            onChange={(event) => {
              setLeftId(event.target.value);
              copyRequestRef.current += 1;
              setCopyStatus("");
              setManualUrl("");
            }}
            className="h-11 w-full rounded-xl border border-(--line) bg-(--surface) px-3 text-[12px] text-(--ink) outline-none focus:border-(--accent)"
          >
            <option value="">Duft auswählen …</option>
            {sorted.map((fragrance) => (
              <option
                key={fragrance.product_id}
                value={fragrance.product_id}
                disabled={fragrance.product_id === rightId}
              >
                {fragrance.brand} – {fragrance.name}
              </option>
            ))}
          </select>
        </label>

        <label>
          <span className="mb-1.5 block text-[11px] font-semibold uppercase tracking-[0.06em] text-(--ink-soft)">
            Duft 2
          </span>
          <select
            value={rightId}
            onChange={(event) => {
              setRightId(event.target.value);
              copyRequestRef.current += 1;
              setCopyStatus("");
              setManualUrl("");
            }}
            className="h-11 w-full rounded-xl border border-(--line) bg-(--surface) px-3 text-[12px] text-(--ink) outline-none focus:border-(--accent)"
          >
            <option value="">Duft auswählen …</option>
            {sorted.map((fragrance) => (
              <option
                key={fragrance.product_id}
                value={fragrance.product_id}
                disabled={fragrance.product_id === leftId}
              >
                {fragrance.brand} – {fragrance.name}
              </option>
            ))}
          </select>
        </label>
      </div>

      {validPair && left && right ? (
        <div className="mt-6">
          <div className="mb-4 flex flex-wrap items-center gap-3">
            <button
              type="button"
              onClick={() => void copyComparisonLink()}
              className="rounded-xl border border-(--line) bg-(--surface) px-4 py-2.5 text-[12px] font-semibold text-(--ink) transition hover:border-(--accent)"
            >
              Vergleichslink kopieren
            </button>
            <span role="status" className="text-[11px] text-(--ink-soft)">
              {copyStatus}
            </span>
            <ManualShareLink url={manualUrl} />
          </div>
          <div className="dufynd-comparison-live-stage grid gap-3 sm:grid-cols-2">
            <div
              aria-hidden
              className="dufynd-comparison-axis"
            >
              <span>vs</span>
            </div>
            <ProductMiniHeader fragrance={left} side="left" />
            <ProductMiniHeader fragrance={right} side="right" />
          </div>

          <div
            role="table"
            aria-label={`Freier Duftvergleich ${left.name} und ${right.name}`}
            className="dufynd-comparison-table mt-4 overflow-hidden rounded-2xl border border-(--line) bg-(--surface)"
          >
            <div
              role="row"
              className="grid grid-cols-[1fr_0.85fr_1fr] gap-2 bg-(--well)/55 px-3 py-3 text-[10.5px] sm:gap-3 sm:px-4"
            >
              <div role="columnheader" className="text-right font-semibold">
                {left.name}
              </div>
              <div
                role="columnheader"
                className="text-center font-semibold uppercase tracking-[0.06em] text-(--ink-soft)"
              >
                Merkmal
              </div>
              <div role="columnheader" className="font-semibold">
                {right.name}
              </div>
            </div>

            <ComparisonRow
              label="Community"
              left={formatRating(
                  left.community.rating_10,
                  left.community.provisional,
                )}
              right={formatRating(
                  right.community.rating_10,
                  right.community.provisional,
                )}
            />
            <ComparisonRow
              label="Haltbarkeit"
              left={formatNumber(
                left.community.longevity_10,
                left.community.provisional,
              )}
              right={formatNumber(
                right.community.longevity_10,
                right.community.provisional,
              )}
            />
            <ComparisonRow
              label="Ausstrahlung"
              left={formatNumber(
                left.community.projection_10,
                left.community.provisional,
              )}
              right={formatNumber(
                right.community.projection_10,
                right.community.provisional,
              )}
            />
            <ComparisonRow
              label="Frische"
              left={formatNumber(left.scores.freshness)}
              right={formatNumber(right.scores.freshness)}
            />
            <ComparisonRow
              label="Süße"
              left={formatNumber(left.scores.sweetness)}
              right={formatNumber(right.scores.sweetness)}
            />
            <ComparisonRow
              label="Holzigkeit"
              left={formatNumber(left.scores.woodiness)}
              right={formatNumber(right.scores.woodiness)}
            />
            <ComparisonRow
              label="Würze"
              left={formatNumber(left.scores.spiciness)}
              right={formatNumber(right.scores.spiciness)}
            />
            <ComparisonRow
              label="Zielgruppe"
              left={targetGroupLabel(left.target_groups) || "–"}
              right={targetGroupLabel(right.target_groups) || "–"}
            />
            <ComparisonRow
              label="Preis-Richtwert"
              left={formatPriceReference(left.market.reference_price_eur, left.market.checked_at)}
              right={formatPriceReference(right.market.reference_price_eur, right.market.checked_at)}
            />
          </div>
          <p className="mt-2 text-[11px] leading-5 text-(--ink-soft)">
            Historische Marktbeobachtung zum angegebenen Stand, kein aktuelles Kaufangebot.
            Verfügbare Händlerangebote werden auf den Duftseiten separat geprüft.
          </p>

          <section className="dufynd-comparison-dna-stage relative mt-4 overflow-hidden rounded-2xl border border-[#d9bd82]/20 bg-[#15120f] p-4 text-white shadow-[0_18px_55px_-34px_rgba(36,24,8,0.9)] sm:p-5">
            <div
              aria-hidden
              className="pointer-events-none absolute inset-0 bg-[radial-gradient(circle_at_50%_0%,rgba(217,189,130,0.15),transparent_45%)]"
            />
            <div className="relative">
              <div className="flex flex-wrap items-end justify-between gap-2">
                <div>
                  <div className="text-[9.5px] font-semibold uppercase tracking-[0.14em] text-[#d9bd82]">
                    Duft-DNA auf einen Blick
                  </div>
                  <h3 className="mt-1 text-[16px] font-semibold tracking-[-0.02em] text-[#fffaf0]">
                    Profilstärken direkt nebeneinander
                  </h3>
                </div>
                <span className="text-[9.5px] text-white/45">Skala 0–10</span>
              </div>
              <div className="mt-4 space-y-3" aria-label="Visueller Duftprofilvergleich">
                <ProfileMeter label="Frische" left={left.scores.freshness} right={right.scores.freshness} />
                <ProfileMeter label="Süße" left={left.scores.sweetness} right={right.scores.sweetness} />
                <ProfileMeter label="Holzig" left={left.scores.woodiness} right={right.scores.woodiness} />
                <ProfileMeter label="Würzig" left={left.scores.spiciness} right={right.scores.spiciness} />
              </div>
              <div className="mt-4 grid grid-cols-2 gap-3 border-t border-white/10 pt-3 text-[10px] text-white/55">
                <div className="truncate text-right font-medium text-white/75">{left.name}</div>
                <div className="truncate font-medium text-white/75">{right.name}</div>
              </div>
            </div>
          </section>

          <div className="mt-4 grid gap-3 sm:grid-cols-2">
            {[left, right].map((fragrance) => (
              <div
                key={fragrance.product_id}
                className="rounded-2xl border border-(--line) bg-(--well)/35 p-4"
              >
                <div className="text-[12px] font-semibold">
                  {fragrance.name}: Akkorde
                </div>
                <div className="mt-2 flex flex-wrap gap-1.5">
                  {fragrance.accords.slice(0, 5).map((accord) => (
                    <span
                      key={accord}
                      className="rounded-full bg-(--card) px-2.5 py-1 text-[10.5px] text-(--ink-soft)"
                    >
                      {accordLabel(accord)}
                    </span>
                  ))}
                </div>
              </div>
            ))}
          </div>

          <div className="mt-4 grid gap-3 lg:grid-cols-2">
            <FragranceOffers
              productId={left.product_id}
              heading={`Angebote für ${left.name}`}
              trackProductOpen={false}
              analyticsSurface="free_comparison"
              compact
            />
            <FragranceOffers
              productId={right.product_id}
              heading={`Angebote für ${right.name}`}
              trackProductOpen={false}
              analyticsSurface="free_comparison"
              compact
            />
          </div>
        </div>
      ) : (
        <div className="mt-5 rounded-2xl border border-dashed border-(--line) bg-(--well)/30 px-4 py-6 text-center text-[12px] text-(--ink-soft)">
          Wähle zwei unterschiedliche Düfte aus, um den Vergleich zu starten.
        </div>
      )}
    </section>
  );
}
