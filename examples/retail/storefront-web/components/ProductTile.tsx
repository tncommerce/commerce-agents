// Copyright 2026 Anthropic PBC
// SPDX-License-Identifier: Apache-2.0

"use client";

import { useState } from "react";
import { hasOptions, optionSummary, optionValuesLabel, priceLabel, useStoreFrame } from "web-shared";
import type { Product } from "@/lib/types";
import { trackAnalyticsEvent } from "@/lib/analytics";
import { flyToCart } from "@/lib/flight";
import { attributeChips, productGlyph, productTileClass } from "@/lib/format";
import { STORE_POLICY } from "@/lib/storePolicy";

/** A trailing parenthetical such as "(48-Pack)" is kept unbreakable so the clamp cuts before it. */
export function ProductTitle({ title, className = "" }: { title: string; className?: string }) {
  const match = /^(.*\S)\s+(\([^()]+\))$/.exec(title);
  return (
    <div className={className} title={title}>
      {match ? (
        <>
          {match[1]} <span className="whitespace-nowrap">{match[2]}</span>
        </>
      ) : (
        title
      )}
    </div>
  );
}

function ReturnsPromise({ className = "" }: { className?: string }) {
  return (
    <div className={`text-[11px] text-(--ink-soft) ${className}`}>
      {STORE_POLICY.returnsShort}
    </div>
  );
}

export function ProductImage({ product, className = "" }: { product: Product; className?: string }) {
  if (product.image_url) {
    const isScentai = String(product.product_id).startsWith("SC-");

    // eslint-disable-next-line @next/next/no-img-element
    return (
      <div
        className={`flex items-center justify-center overflow-hidden ${
          isScentai ? "bg-white" : ""
        } ${className}`}
      >
        <img
          src={product.image_url}
          alt={product.title}
          className={
            isScentai
              ? "h-full w-full scale-[1.25] object-contain"
              : "h-full w-full object-cover"
          }
        />
      </div>
    );
  }
  const isScentai = String(product.product_id).startsWith("SC-");

  if (isScentai) {
    return (
      <div
        className={`relative flex items-center justify-center overflow-hidden ${productTileClass(product.product_id)} ${className}`}
        aria-hidden
      >
        <div className="absolute inset-0 bg-[radial-gradient(circle_at_center,rgba(255,255,255,0.8),transparent_70%)]" />

        <div className="relative flex flex-col items-center">
          <div className="h-3 w-9 rounded-t-sm bg-(--ink)/80" />
          <div className="h-3 w-6 bg-(--ink)/65" />

          <div className="flex h-20 w-16 items-center justify-center rounded-[18px] border border-white/80 bg-white/70 shadow-md backdrop-blur-sm">
            <span className="text-[9px] font-semibold tracking-[0.18em] text-(--ink)/75">
              SCENTAI
            </span>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div
      className={`flex items-center justify-center text-5xl ${productTileClass(product.product_id)} ${className}`}
      aria-hidden
    >
      {productGlyph(product)}
    </div>
  );
}

/** `attributes.delivery` is stamped by the backend. */
export function DeliveryPromise({
  product,
  className = "",
}: {
  product: Product;
  className?: string;
}) {
  const promise = product.attributes?.delivery;
  if (product.category === "fragrance" || !promise || product.in_stock === false) return null;
  return (
    <div className={`text-[11px] font-medium text-(--ok) ${className}`}>{promise}</div>
  );
}

/** `attributes.low_stock` is the inventory count the merchant portal shows. */
function LowStockChip({ product, className = "" }: { product: Product; className?: string }) {
  const count = product.attributes?.low_stock;
  if (!count || product.in_stock === false) return null;
  return (
    <span
      className={`whitespace-nowrap rounded-full bg-(--warn-soft) px-2 py-0.5 text-[11px] font-semibold text-(--warn) ${className}`}
    >
      Only {count} left
    </span>
  );
}

export function Rating({ rating, count }: { rating?: number | null; count?: number | null }) {
  if (rating == null) return null;
  // A one-line rating keeps sibling cards' price rows aligned.
  return (
    <span className="whitespace-nowrap text-[13px] text-(--ink-soft)">
      <span className="text-(--star)">★</span> {rating.toFixed(1)}
      {count ? (
        <span className="text-[11px] text-(--ink-soft)/80"> ({count.toLocaleString()})</span>
      ) : null}
    </span>
  );
}
    export function ProductRating({
      product,
      compact = false,
    }: {
      product: Product;
      compact?: boolean;
    }) {
      const communityRating = product.attributes?.community_rating_10;
      const ratingSource = product.attributes?.rating_source;
      const value = communityRating ? Number(communityRating) : null;

      if (value !== null && Number.isFinite(value)) {
        return (
          <span className="whitespace-nowrap text-[13px] text-(--ink-soft)">
            <span className="font-semibold text-(--ink)">
              {value.toLocaleString("de-DE", {
                minimumFractionDigits: 1,
                maximumFractionDigits: 1,
              })}/10
            </span>
            {ratingSource ? (
              <span className="text-[11px]"> · {ratingSource}</span>
            ) : null}
            {!compact && product.review_count ? (
              <span className="text-[11px] text-(--ink-soft)/80">
                {" "}({product.review_count.toLocaleString("de-DE")})
              </span>
            ) : null}
          </span>
        );
      }

      return (
        <Rating
          rating={product.rating}
          count={compact ? undefined : product.review_count}
        />
      );
    }
export function customerPriceLabel(product: Product): string {
  const base = priceLabel(product);
  const source = product.attributes?.price_source;

  if (String(product.product_id).startsWith("SC-")) {
    if (source === "current_merchant_offer") return `ab ${base}`;
    if (source === "market_reference") return `ca. ${base}`;
  }

  return base;
}

/** What a variant chose, or what a product with options still needs chosen; empty otherwise. */
function optionText(product: Product): string {
  return optionValuesLabel(product) || optionSummary(product);
}

export function OptionLine({ product, className = "" }: { product: Product; className?: string }) {
  const text = optionText(product);
  if (!text) return null;
  return <div className={`truncate text-[11px] text-(--ink-soft) ${className}`}>{text}</div>;
}

/**
 * An onAdd that resolves `false` means the server rejected the write. A product with options
 * is not added from the card: the button hands the choice to the assistant, which settles the
 * option with the customer and adds the variant.
 */
export function AddButton({
  product,
  onAdd,
}: {
  product: Product;
  onAdd: (product: Product) => boolean | void | Promise<boolean | void>;
}) {
  const [phase, setPhase] = useState<"idle" | "busy" | "done" | "error">("idle");
  const { ask } = useStoreFrame();
  if (hasOptions(product)) {
    return (
      <button
        type="button"
        onClick={(event) => {
          event.stopPropagation();
          ask(`Add the ${product.title} (${product.product_id}) to my cart.`);
        }}
        aria-label={`Choose options for ${product.title}`}
        className="pointer-events-auto absolute bottom-2 right-2 flex h-8 w-8 items-center justify-center rounded-full bg-(--ink) text-lg font-semibold leading-none text-(--surface) shadow-(--shadow-sm) transition-all hover:scale-105"
      >
        +
      </button>
    );
  }
  return (
    <button
      type="button"
      onClick={async (event) => {
        event.stopPropagation();
        if (phase !== "idle") return;
        const source = event.currentTarget.parentElement ?? event.currentTarget;
        setPhase("busy");
        const added = (await onAdd(product)) !== false;
        setPhase(added ? "done" : "error");
        // Animate only after the server confirmed the write.
        if (added) flyToCart(product, source);
        window.setTimeout(() => setPhase("idle"), added ? 1200 : 1600);
      }}
      aria-label={`Add ${product.title} to cart`}
      className={`pointer-events-auto absolute bottom-2 right-2 flex h-8 w-8 items-center justify-center rounded-full text-lg font-semibold leading-none text-(--surface) shadow-(--shadow-sm) transition-all hover:scale-105 ${
        phase === "done" ? "bg-(--ok)" : phase === "error" ? "bg-(--warn)" : "bg-(--ink)"
      } ${phase === "busy" ? "animate-pulse" : ""}`}
    >
      {phase === "done" ? "✓" : phase === "error" ? "!" : "+"}
    </button>
  );
}

export default function ProductTile({
  product,
  compact = false,
  fluid = false,
  selected = false,
  onAdd,
  onOpen,
}: {
  product: Product;
  compact?: boolean;
  /** Fills its grid cell instead of the carousel's fixed width. */
  fluid?: boolean;
  selected?: boolean;
  onAdd?: (product: Product) => boolean | void | Promise<boolean | void>;
  onOpen?: (product: Product) => void;
}) {
  const clickable = Boolean(onOpen);
  const isScentai = String(product.product_id).startsWith("SC-");
  const openProduct = () => {
    if (isScentai) {
      void trackAnalyticsEvent("product_open", {
        product_id: product.product_id,
        source: "product_card",
      });
    }
    onOpen?.(product);
  };
  const chips = compact ? [] : attributeChips(product);
  const imageHeight = compact
    ? "h-16"
    : isScentai
      ? "h-36"
      : fluid
        ? "h-40"
        : "h-36";
  return (
    <div
      className={`relative flex shrink-0 flex-col overflow-hidden border bg-(--card) transition-[box-shadow,border-color,transform] duration-200 ${
        isScentai
          ? "rounded-2xl shadow-sm hover:-translate-y-0.5 hover:shadow-md"
          : "rounded-xl shadow-(--shadow-sm) hover:shadow-md"
      } ${
        fluid ? "w-full" : compact ? "w-36" : "w-48"
      } ${selected ? "border-(--ink)" : "border-(--line)"}`}
    >
      <div
        onClick={clickable ? openProduct : undefined}
        onKeyDown={clickable ? (event) => event.key === "Enter" && openProduct() : undefined}
        role={clickable ? "button" : undefined}
        tabIndex={clickable ? 0 : undefined}
        className={`flex flex-1 flex-col rounded-xl focus-visible:outline-2 focus-visible:-outline-offset-2 focus-visible:outline-(--accent) ${
          clickable ? "cursor-pointer" : ""
        }`}
      >
        <div className="relative">
          <div className={`flex items-center justify-center w-full ${imageHeight} bg-white`}>
            <ProductImage product={product} className="h-full w-full" />
          </div>
          {product.in_stock === false ? (
            <span className="absolute right-1.5 top-1.5 rounded-full bg-(--ink)/85 px-2 py-0.5 text-[11px] font-medium text-(--surface)">
              Out of stock
            </span>
          ) : (
            <LowStockChip product={product} className="absolute right-1.5 top-1.5" />
          )}
        </div>
        <div className={isScentai ? "flex flex-1 flex-col gap-1 p-3.5" : "flex flex-1 flex-col gap-0.5 p-2.5"}>
          <div className={isScentai ? "text-[10.5px] font-medium uppercase tracking-[0.08em] text-(--ink-soft)/75" : "text-[11px] uppercase tracking-wide text-(--ink-soft)/80"}>{product.brand}</div>
          <ProductTitle
            title={product.title}
            className={`line-clamp-2 font-medium leading-snug ${isScentai ? "text-[14.5px]" : "text-[13px]"} ${compact ? "" : isScentai ? "h-10" : "h-9"}`}
          />
          {compact ? null : optionText(product) ? (
            <OptionLine product={product} className="h-[18px] pt-0.5 leading-4" />
          ) : (
            /* Fixed height keeps sibling cards aligned. */
            <div className="flex h-[18px] flex-wrap gap-1 overflow-hidden pt-0.5" aria-hidden={chips.length === 0}>
              {chips.map((chip) => (
                <span
                  key={chip}
                  className="whitespace-nowrap rounded-full bg-(--well) px-1.5 py-px text-[11px] leading-4 text-(--ink-soft)"
                >
                  {chip}
                </span>
              ))}
            </div>
          )}
          <div className={isScentai ? "mt-auto flex items-end justify-between gap-2 border-t border-(--line)/70 pt-2.5" : "mt-auto flex items-center justify-between gap-1 pt-0.5"}>
            <span className="text-sm font-semibold">{customerPriceLabel(product)}</span>
            <ProductRating product={product} compact={compact} />
          </div>
          <DeliveryPromise product={product} />
          {!compact && product.in_stock !== false ? <ReturnsPromise /> : null}
          {!compact && isScentai && clickable ? (
            <div className="mt-1 text-[11px] font-medium text-(--ink-soft)">
              {product.attributes?.price_source === "current_merchant_offer"
                ? "Details & Händlerangebote ansehen →"
                : "Details ansehen →"}
            </div>
          ) : null}
        </div>
      </div>
      {onAdd && !isScentai && product.in_stock !== false ? (
        // Over the image but a sibling of the clickable area, so one control is not nested in another.
        <div className={`pointer-events-none absolute inset-x-0 top-0 ${imageHeight}`}>
          <AddButton product={product} onAdd={onAdd} />
        </div>
      ) : null}
    </div>
  );
}

export function ProductRow({
  product,
  onAdd,
  onOpen,
}: {
  product: Product;
  onAdd?: (product: Product) => boolean | void | Promise<boolean | void>;
  onOpen?: (product: Product) => void;
}) {
  const clickable = Boolean(onOpen);
  const openProduct = () => {
    if (String(product.product_id).startsWith("SC-")) {
      void trackAnalyticsEvent("product_open", {
        product_id: product.product_id,
        source: "product_row",
      });
    }
    onOpen?.(product);
  };

  return (
    <div
      onClick={clickable ? openProduct : undefined}
      onKeyDown={clickable ? (event) => event.key === "Enter" && openProduct() : undefined}
      role={clickable ? "button" : undefined}
      tabIndex={clickable ? 0 : undefined}
      className={`flex w-full items-center gap-3 rounded-xl border border-(--line) bg-(--card) p-2 shadow-(--shadow-sm) transition-shadow hover:shadow-md ${clickable ? "cursor-pointer" : ""}`}
    >
      <div className="relative shrink-0">
        <ProductImage
          product={product}
          className={`h-14 w-16 rounded-lg ${product.in_stock === false ? "opacity-50" : ""}`}
        />
        {onAdd && product.in_stock !== false ? (
          <AddButton product={product} onAdd={onAdd} />
        ) : null}
      </div>
      <div className="min-w-0 flex-1">
        <div className="text-[11px] uppercase tracking-wide text-(--ink-soft)/80">{product.brand}</div>
        <ProductTitle
          title={product.title}
          className="line-clamp-1 text-[13px] font-medium leading-snug"
        />
        <OptionLine product={product} />
        <div className="flex items-center gap-2">
          <span className="text-sm font-semibold">{customerPriceLabel(product)}</span>
          <ProductRating product={product} compact />
          {product.in_stock === false ? (
            <span className="rounded-full bg-(--ink)/85 px-2 py-0.5 text-[11px] font-medium text-(--surface)">
              Out of stock
            </span>
          ) : (
            <LowStockChip product={product} />
          )}
        </div>
        <DeliveryPromise product={product} />
        {clickable ? (
          <div className="mt-0.5 text-[11px] font-medium text-(--accent-ink)">
            Details ansehen →
          </div>
        ) : null}
      </div>
    </div>
  );
}
