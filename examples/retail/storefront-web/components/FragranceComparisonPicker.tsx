"use client";

import { useMemo, useState } from "react";

import FragranceOffers from "@/components/FragranceOffers";
import type { StaticFragrance } from "@/lib/fragranceCatalog";

function formatRating(value: number | null): string {
  if (value == null) return "–";
  return `${value.toLocaleString("de-DE", {
    minimumFractionDigits: 1,
    maximumFractionDigits: 1,
  })}/10`;
}

function formatNumber(value: number | null): string {
  if (value == null) return "–";
  return value.toLocaleString("de-DE", {
    minimumFractionDigits: 1,
    maximumFractionDigits: 1,
  });
}

function formatPrice(value: number | null): string {
  if (value == null) return "–";
  return new Intl.NumberFormat("de-DE", {
    style: "currency",
    currency: "EUR",
  }).format(value);
}

function targetLabel(value: string): string {
  return {
    men: "Herren",
    women: "Damen",
    unisex: "Unisex",
  }[value] || value;
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
    <div className="grid grid-cols-[1fr_0.85fr_1fr] items-center gap-2 border-t border-(--line) px-3 py-3 text-[12px] sm:gap-3 sm:px-4">
      <div className="text-right font-medium text-(--ink)">
        {left}
      </div>
      <div className="text-center text-[10px] font-semibold uppercase tracking-[0.06em] text-(--ink-soft)">
        {label}
      </div>
      <div className="font-medium text-(--ink)">
        {right}
      </div>
    </div>
  );
}

function ProductMiniHeader({
  fragrance,
}: {
  fragrance: StaticFragrance;
}) {
  return (
    <a
      href={`/duft/${fragrance.slug}`}
      className="overflow-hidden rounded-2xl border border-(--line) bg-(--card) shadow-(--shadow-sm) transition hover:border-(--ink)"
    >
      <div className="flex h-40 items-center justify-center bg-white p-4">
        {fragrance.image_url ? (
          // eslint-disable-next-line @next/next/no-img-element
          <img
            src={fragrance.image_url}
            alt={`${fragrance.brand} ${fragrance.name}`}
            className="h-full w-full object-contain"
            loading="lazy"
            decoding="async"
          />
        ) : (
          <span className="text-[11px] font-semibold tracking-[0.14em] text-(--ink-soft)">
            SCENTAI
          </span>
        )}
      </div>
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

  return (
    <section className="mt-8 rounded-3xl border border-(--line) bg-(--card) p-4 shadow-(--shadow-sm) sm:p-5">
      <div className="max-w-2xl">
        <div className="text-[10.5px] font-semibold uppercase tracking-[0.1em] text-(--ink-soft)">
          Freier Vergleich
        </div>
        <h2 className="mt-1 text-[22px] font-semibold tracking-[-0.02em]">
          Zwei Düfte selbst auswählen
        </h2>
        <p className="mt-2 text-[12px] leading-5 text-(--ink-soft)">
          Vergleiche beliebige Live-Düfte nach denselben SCENTAI-Daten.
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
            onChange={(event) => setLeftId(event.target.value)}
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
            onChange={(event) => setRightId(event.target.value)}
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
          <div className="grid gap-3 sm:grid-cols-2">
            <ProductMiniHeader fragrance={left} />
            <ProductMiniHeader fragrance={right} />
          </div>

          <div className="mt-4 overflow-hidden rounded-2xl border border-(--line) bg-(--surface)">
            <div className="grid grid-cols-[1fr_0.85fr_1fr] gap-2 bg-(--well)/55 px-3 py-3 text-[10.5px] sm:gap-3 sm:px-4">
              <div className="text-right font-semibold">
                {left.name}
              </div>
              <div className="text-center font-semibold uppercase tracking-[0.06em] text-(--ink-soft)">
                Vergleich
              </div>
              <div className="font-semibold">
                {right.name}
              </div>
            </div>

            <ComparisonRow
              label="Community"
              left={formatRating(left.community.rating_10)}
              right={formatRating(right.community.rating_10)}
            />
            <ComparisonRow
              label="Haltbarkeit"
              left={formatNumber(left.community.longevity_10)}
              right={formatNumber(right.community.longevity_10)}
            />
            <ComparisonRow
              label="Ausstrahlung"
              left={formatNumber(left.community.projection_10)}
              right={formatNumber(right.community.projection_10)}
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
              left={left.target_groups.map(targetLabel).join(", ") || "–"}
              right={right.target_groups.map(targetLabel).join(", ") || "–"}
            />
            <ComparisonRow
              label="Preisreferenz"
              left={formatPrice(left.market.reference_price_eur)}
              right={formatPrice(right.market.reference_price_eur)}
            />
          </div>

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
                      {accord}
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
              compact
            />
            <FragranceOffers
              productId={right.product_id}
              heading={`Angebote für ${right.name}`}
              trackProductOpen={false}
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
