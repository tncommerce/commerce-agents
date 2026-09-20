// Copyright 2026 Anthropic PBC
// SPDX-License-Identifier: Apache-2.0

"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { formatMoney, optionValuesLabel, useStoreFrame } from "web-shared";
import FragranceOffers from "@/components/FragranceOffers";
import { fetchProduct } from "@/lib/api";
import { trackAnalyticsEvent } from "@/lib/analytics";
import { fragrancePathForProduct } from "@/lib/fragranceSlug";
import type { PriceIntelligence, Product, ProductDetails, ProductsPayload, ReviewAspects } from "@/lib/types";
import ProductTile, { AddButton, customerPriceLabel, DeliveryPromise, OptionLine, ProductImage, ProductRating, Rating } from "../ProductTile";

function PriceIntelligenceRow({ intel }: { intel: PriceIntelligence }) {
  const { series, low, high } = intel;
  const width = 116;
  const height = 26;
  const span = Math.max(high - low, 0.01);
  const points = series
    .map((value, index) => {
      const x = (index / Math.max(series.length - 1, 1)) * (width - 4) + 2;
      const y = height - 3 - ((value - low) / span) * (height - 6);
      return `${x.toFixed(1)},${y.toFixed(1)}`;
    })
    .join(" ");
  const [lastX, lastY] = points.split(" ").pop()!.split(",");
  return (
    <div
      data-price-intelligence
      className="mt-2 flex flex-wrap items-center gap-x-3 gap-y-1 rounded-lg border border-(--line) bg-(--card) px-2.5 py-2"
    >
      <svg
        viewBox={`0 0 ${width} ${height}`}
        className="h-[26px] w-[116px] shrink-0"
        aria-hidden
      >
        <polyline
          points={points}
          fill="none"
          stroke="var(--ink)"
          strokeOpacity="0.45"
          strokeWidth="1.5"
        />
        <circle cx={lastX} cy={lastY} r="2.5" fill="var(--accent)" stroke="var(--ink)" strokeWidth="0.8" />
      </svg>
      <div className="min-w-0">
        <div className="text-[13px] font-semibold text-(--ink)">{intel.verdict}</div>
        <div className="text-[11px] text-(--ink-soft)">
          {intel.position === "low"
            ? "Aktuell nahe am unteren Ende der eigenen Preisspanne"
            : intel.position === "high"
              ? "Aktuell nahe am oberen Ende der eigenen Preisspanne"
              : "Aktuell im üblichen Bereich der eigenen Preisspanne"}
          {" "}· letzte {intel.days} Tage
        </div>
      </div>
    </div>
  );
}

function ReviewAspectsRow({ synthesis }: { synthesis: ReviewAspects }) {
  return (
    <div data-review-aspects className="mt-2">
      <div className="text-[11px] font-semibold uppercase tracking-wide text-(--ink-soft)">
        Aus {synthesis.review_count.toLocaleString("de-DE")} Kundenbewertungen
      </div>
      <div className="mt-1.5 flex flex-wrap gap-1.5">
        {synthesis.aspects.map((aspect) => (
          <div
            key={aspect.name}
            className="rounded-lg border border-(--line) bg-(--card) px-2 py-1"
            title={`${aspect.name}: ${aspect.positive_pct}% positiv bei ${aspect.mentions.toLocaleString("de-DE")} Nennungen`}
          >
            <div className="flex items-baseline gap-1.5 text-[13px]">
              <span className="font-medium text-(--ink)">{aspect.name}</span>
              <span
                className={`font-semibold ${
                  aspect.positive_pct >= 70 ? "text-(--ok)" : "text-(--warn)"
                }`}
              >
                {aspect.positive_pct}%
              </span>
              <span className="text-[11px] text-(--ink-soft)">
                {aspect.mentions.toLocaleString("de-DE")} Nennungen
              </span>
            </div>
            <div className="mt-1 h-1 w-full overflow-hidden rounded-full bg-(--well)">
              <div
                className={`h-full rounded-full ${
                  aspect.positive_pct >= 70 ? "bg-(--ok)" : "bg-(--warn)"
                }`}
                style={{ width: `${aspect.positive_pct}%` }}
              />
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}

/** The variants of a product with options; picking one hands the add to the assistant. */
function VariantList({ family, variants }: { family: Product; variants: Product[] }) {
  const { ask } = useStoreFrame();
  const pricesDiffer = variants.some((variant) => variant.price !== variants[0]?.price);
  return (
    <ul className="mt-2 flex flex-wrap gap-1.5" aria-label="Optionen">
      {variants.map((variant) => {
        const label = optionValuesLabel(variant);
        const available = variant.in_stock !== false;
        return (
          <li key={variant.product_id}>
            <button
              type="button"
              disabled={!available}
              onClick={() => ask(`Add the ${family.title} in ${label} (${variant.product_id}) to my cart.`)}
              className="rounded-full border border-(--line) bg-(--card) px-2.5 py-1 text-[12px] text-(--ink) transition-colors hover:border-(--ink) disabled:cursor-not-allowed disabled:text-(--ink-soft)/70 disabled:line-through"
            >
              {label}
              {pricesDiffer ? <span className="text-(--ink-soft)"> · {formatMoney(variant.price, variant.currency)}</span> : null}
            </button>
          </li>
        );
      })}
    </ul>
  );
}

function ProductDetail({
  product,
  reason,
  onAdd,
  onClose,
}: {
  product: Product;
  reason?: string | null;
  onAdd?: (product: Product) => boolean | void | Promise<boolean | void>;
  onClose: () => void;
}) {
  const [details, setDetails] = useState<ProductDetails | null>(null);
  useEffect(() => {
    let mounted = true;
    void fetchProduct(product.product_id).then((value) => {
      if (mounted) setDetails(value);
    });
    return () => {
      mounted = false;
    };
  }, [product.product_id]);

  const full = details ?? product;
  const specs = details?.specs ?? {};
  const isDufynd = String(full.product_id).startsWith("SC-");
  return (
    <div className="ac-reveal mb-1 mt-3 rounded-xl border border-(--line) bg-(--well)/40 p-3">
      <div className="flex items-start gap-3">
        <div className="relative shrink-0">
          <ProductImage product={full} className="h-24 w-28 rounded-lg" />
          {onAdd && !String(full.product_id).startsWith("SC-") && full.in_stock !== false ? <AddButton product={full} onAdd={onAdd} /> : null}
        </div>
        <div className="min-w-0 flex-1">
          <div className="flex items-start justify-between gap-2">
            <div>
              <div className="text-[11px] uppercase tracking-wide text-(--ink-soft)/80">
                {full.brand}
              </div>
              <div className="text-sm font-semibold leading-snug">{full.title}</div>
              <OptionLine product={full} />
              <div className="mt-0.5 flex items-center gap-2">
                <span className="text-sm font-bold">{customerPriceLabel(full)}</span>
                {String(full.product_id).startsWith("SC-") ? (
                  <ProductRating product={full} />
                ) : (
                  <Rating rating={full.rating} count={full.review_count} />
                )}
                {full.in_stock === false ? (
                  <span className="rounded-full bg-(--ink)/85 px-2 py-0.5 text-[11px] font-medium text-(--surface)">
                    Nicht auf Lager
                  </span>
                ) : null}
              </div>
              <DeliveryPromise product={full} className="mt-0.5" />
            </div>
            <button
              onClick={onClose}
              aria-label="Details schließen"
              className="shrink-0 rounded-md px-1.5 text-base leading-none text-(--ink-soft) hover:text-(--ink)"
            >
              ×
            </button>
          </div>
        </div>
      </div>

      {reason ? (
        <p className="mt-2 text-[13px] leading-snug text-(--ink)">{reason}</p>
      ) : null}
      {details === null ? (
        <p className="mt-2 animate-pulse text-[13px] text-(--ink-soft)">Details werden geladen…</p>
      ) : (
        <div className="ac-reveal">
          {details.price_intelligence ? (
            <PriceIntelligenceRow intel={details.price_intelligence} />
          ) : null}
          {details.review_aspects?.aspects?.length ? (
            <ReviewAspectsRow synthesis={details.review_aspects} />
          ) : null}
          {details.long_description ? (
            <p className="mt-2 text-[13px] leading-relaxed text-(--ink)">
              {details.long_description}
            </p>
          ) : null}
          {details.variants?.length ? <VariantList family={details} variants={details.variants} /> : null}
          {Object.keys(specs).length ? (
            <dl className="mt-2 grid grid-cols-2 gap-x-4 gap-y-1 sm:grid-cols-3">
              {Object.entries(specs).map(([key, value]) => (
                <div key={key} className="text-[13px]">
                  <dt className="font-semibold capitalize text-(--ink-soft)">
                    {key.replaceAll("_", " ")}
                  </dt>
                  <dd className="text-(--ink)">{value}</dd>
                </div>
              ))}
            </dl>
          ) : null}
          {details.review_highlights?.length ? (
            <div className="mt-2 space-y-1">
              {details.review_highlights.slice(0, 3).map((highlight) => (
                <p key={highlight} className="text-[13px] italic leading-snug text-(--ink-soft)">
                  “{highlight}”
                </p>
              ))}
            </div>
          ) : null}
        </div>
      )}

      {isDufynd ? (
        <>
          <div className="mt-3 flex flex-wrap gap-2">
            <a
              href={fragrancePathForProduct(full)}
              className="rounded-lg bg-(--ink) px-3 py-2 text-[12px] font-semibold text-(--surface)"
            >
              Vollständige Duftseite öffnen
            </a>
            <a
              href={`/vergleich?left=${encodeURIComponent(full.product_id)}`}
              className="rounded-lg border border-(--line) bg-(--card) px-3 py-2 text-[12px] font-semibold text-(--ink)"
            >
              Mit anderem Duft vergleichen
            </a>
          </div>

          <div className="mt-3">
            <FragranceOffers
              productId={full.product_id}
              trackProductOpen={false}
              analyticsSurface="advisor_inline_detail"
              compact
            />
          </div>
        </>
      ) : null}
    </div>
  );
}

function MobileProductResult({
  product,
  reason,
  expanded,
  onToggle,
  onAdd,
}: {
  product: Product;
  reason?: string | null;
  expanded: boolean;
  onToggle: () => void;
  onAdd?: (product: Product) => boolean | void | Promise<boolean | void>;
}) {
  return (
    <div className="overflow-hidden rounded-xl border border-(--line) bg-(--card)">
      <button
        type="button"
        onClick={onToggle}
        aria-expanded={expanded}
        className="flex w-full items-center gap-3 p-2.5 text-left"
      >
        <ProductImage product={product} className="h-20 w-20 shrink-0 rounded-lg" />
        <div className="min-w-0 flex-1">
          <div className="truncate text-[10.5px] font-medium uppercase tracking-[0.08em] text-(--ink-soft)/75">
            {product.brand}
          </div>
          <div className="mt-0.5 line-clamp-2 text-[14px] font-semibold leading-snug text-(--ink)">
            {product.title}
          </div>
          <div className="mt-1 flex flex-wrap items-baseline gap-x-2 gap-y-0.5">
            <span className="text-[14px] font-bold text-(--ink)">{customerPriceLabel(product)}</span>
            <ProductRating product={product} compact />
          </div>
          <div className="mt-1 text-[11.5px] font-medium text-(--accent-ink)">
            {expanded ? "Details schließen" : "Details ansehen"} {expanded ? "↑" : "→"}
          </div>
        </div>
      </button>
      {expanded ? (
        <div className="border-t border-(--line) px-2 pb-2">
          <ProductDetail
            product={product}
            reason={reason}
            onAdd={onAdd}
            onClose={onToggle}
          />
        </div>
      ) : null}
    </div>
  );
}

export default function ProductCarousel({
  payload,
  onAdd,
  partial,
}: {
  payload: ProductsPayload;
  onAdd?: (product: Product) => boolean | void | Promise<boolean | void>;
  partial?: boolean;
}) {
  const { ask } = useStoreFrame();
  const layout = payload.layout ?? "carousel";
  const items = payload.items ?? [];
  const [expandedId, setExpandedId] = useState<string | null>(null);
  // Keep the last product mounted while the panel folds shut, so collapse animates.
  const [renderedId, setRenderedId] = useState<string | null>(null);
  const autoOpenedProductRef = useRef<string | null>(null);
  const viewedRecommendationsRef = useRef<Set<string>>(new Set());
  const collapseRef = useRef<HTMLDivElement>(null);

  const scrollerRef = useRef<HTMLDivElement>(null);
  const [overflow, setOverflow] = useState({ left: false, right: false });
  const syncOverflow = useCallback(() => {
    const node = scrollerRef.current;
    if (!node) return;
    setOverflow({
      left: node.scrollLeft > 4,
      right: node.scrollLeft + node.clientWidth < node.scrollWidth - 4,
    });
  }, []);
  useEffect(() => {
    syncOverflow();
    const node = scrollerRef.current;
    if (!node || typeof ResizeObserver === "undefined") return;
    const observer = new ResizeObserver(syncOverflow);
    observer.observe(node);
    return () => observer.disconnect();
  }, [syncOverflow, items.length, partial]);

  useEffect(() => {
    items.forEach(({ product }, index) => {
      if (!String(product.product_id).startsWith("SC-")) return;

      const itemPosition = index + 1;
      const key = `${product.product_id}:${itemPosition}`;
      if (viewedRecommendationsRef.current.has(key)) return;

      viewedRecommendationsRef.current.add(key);
      void trackAnalyticsEvent("advisor_recommendation_view", {
        product_id: product.product_id,
        source: "advisor",
        surface: "advisor_recommendation",
        item_position: itemPosition,
      });
    });
  }, [items]);

  // A single DUFYND product is typically a detail-intent result. Open its detail
  // panel once automatically so merchant offers are immediately discoverable.
  useEffect(() => {
    if (partial || items.length !== 1) return;

    const productId = items[0]?.product.product_id;
    if (!productId || !String(productId).startsWith("SC-")) return;
    if (autoOpenedProductRef.current === productId) return;

    autoOpenedProductRef.current = productId;
    void trackAnalyticsEvent("advisor_product_open", {
      product_id: productId,
      source: "auto_open",
      surface: "advisor_recommendation",
      item_position: 1,
    });
    setRenderedId(productId);
    setExpandedId(productId);
  }, [items, partial]);
  const nudge = (direction: 1 | -1) => {
    const node = scrollerRef.current;
    node?.scrollBy({ left: direction * (node.clientWidth - 80), behavior: "smooth" });
  };

  useEffect(() => {
    if (expandedId) {
      setRenderedId(expandedId);
      // Bring the unfolding panel into view once it has height.
      const timer = window.setTimeout(
        () => collapseRef.current?.scrollIntoView({ behavior: "smooth", block: "nearest" }),
        180,
      );
      return () => window.clearTimeout(timer);
    }
  }, [expandedId]);

  const rendered = items.find(({ product }) => product.product_id === renderedId);
  const open = expandedId != null && expandedId === renderedId;

  const toggle = (product: Product) =>
    setExpandedId((current) => (current === product.product_id ? null : product.product_id));

  return (
    <section className="rounded-2xl border border-(--line) bg-(--card) p-3 shadow-(--shadow-sm)">
      {payload.title ? (
        <h3 className="mb-3 text-[15px] font-semibold text-(--ink)">{payload.title}</h3>
      ) : null}
      <div className="space-y-2 sm:hidden">
        {items.map(({ product, reason }, index) => (
          <MobileProductResult
            key={product.product_id}
            product={product}
            reason={reason}
            expanded={expandedId === product.product_id}
            onToggle={() => {
              if (expandedId !== product.product_id) {
                void trackAnalyticsEvent("advisor_product_open", {
                  product_id: product.product_id,
                  source: "recommendation_card",
                  surface: "advisor_recommendation",
                  item_position: index + 1,
                });
              }
              toggle(product);
            }}
            onAdd={onAdd}
          />
        ))}
        {partial ? <div className="ac-skeleton h-20 rounded-xl" /> : null}
        {!partial && items.length >= 4 ? (
          <button
            type="button"
            onClick={() =>
              ask(
                "Zeige mir weitere passende Düfte unter denselben Bedingungen. Wiederhole keine bereits gezeigten Düfte.",
              )
            }
            className="w-full rounded-xl border border-(--line) bg-(--card) px-3 py-2.5 text-[13px] font-semibold text-(--ink) transition hover:border-(--accent)"
          >
            Weitere passende Düfte anzeigen
          </button>
        ) : null}
      </div>

      <div className="relative hidden sm:block">
        <div
          ref={scrollerRef}
          onScroll={layout === "carousel" ? syncOverflow : undefined}
          className={
            layout === "grid"
              ? "grid grid-cols-2 gap-3 sm:grid-cols-3"
              : layout === "list"
                ? "flex flex-col gap-3"
                : "panel-scroll flex gap-3 overflow-x-auto pb-1"
          }
        >
          {items.map(({ product }, index) => (
            <div key={product.product_id} className="ac-reveal shrink-0">
              <ProductTile
                product={product}
                onAdd={onAdd}
                onOpen={() => {
                  if (expandedId !== product.product_id) {
                    void trackAnalyticsEvent("advisor_product_open", {
                      product_id: product.product_id,
                      source: "recommendation_card",
                      surface: "advisor_recommendation",
                      item_position: index + 1,
                    });
                  }
                  toggle(product);
                }}
                selected={product.product_id === expandedId}
              />
            </div>
          ))}
          {partial ? <div className="ac-skeleton h-[150px] w-48 shrink-0 rounded-xl" /> : null}
        </div>
        {overflow.left ? (
          <>
            <div
              aria-hidden
              className="pointer-events-none absolute inset-y-0 left-0 w-10 bg-linear-to-r from-white to-transparent"
            />
            <button
              onClick={() => nudge(-1)}
              aria-label="Zu vorherigen Produkten scrollen"
              className="absolute left-0 top-1/2 -translate-y-1/2 rounded-full border border-(--line) bg-(--card) px-2 py-1 text-sm text-(--ink) shadow-md transition hover:border-(--accent)"
            >
              ‹
            </button>
          </>
        ) : null}
        {overflow.right ? (
          <>
            <div
              aria-hidden
              className="pointer-events-none absolute inset-y-0 right-0 w-10 bg-gradient-to-l from-white to-transparent"
            />
            <button
              onClick={() => nudge(1)}
              aria-label="Zu weiteren Produkten scrollen"
              className="absolute right-0 top-1/2 -translate-y-1/2 rounded-full border border-(--line) bg-(--card) px-2 py-1 text-sm text-(--ink) shadow-md transition hover:border-(--accent)"
            >
              ›
            </button>
          </>
        ) : null}
      </div>
      <div className="hidden sm:block">
      <div
        ref={collapseRef}
        className={`ac-collapse ${open ? "ac-collapse-open" : ""}`}
        onTransitionEnd={(event) => {
          if (event.propertyName === "grid-template-rows" && !expandedId) setRenderedId(null);
        }}
        aria-hidden={!open}
      >
        <div className="ac-collapse-inner">
          {rendered ? (
            <ProductDetail
              key={rendered.product.product_id}
              product={rendered.product}
              reason={rendered.reason}
              onAdd={onAdd}
              onClose={() => setExpandedId(null)}
            />
          ) : null}
        </div>
      </div>
      </div>
    </section>
  );
}
