"use client";

import type { CSSProperties, PointerEvent } from "react";

type VisualVariant = "card" | "hero";
type VisualMode = "auto" | "editorial" | "cutout";

type StageStyle = CSSProperties & {
  "--dufynd-rx": string;
  "--dufynd-ry": string;
  "--dufynd-mx": string;
  "--dufynd-my": string;
};

const BASE_STYLE: StageStyle = {
  "--dufynd-rx": "0deg",
  "--dufynd-ry": "0deg",
  "--dufynd-mx": "50%",
  "--dufynd-my": "34%",
};

function updatePointer(event: PointerEvent<HTMLDivElement>) {
  if (event.pointerType === "touch") return;

  const bounds = event.currentTarget.getBoundingClientRect();
  const x = Math.min(1, Math.max(0, (event.clientX - bounds.left) / bounds.width));
  const y = Math.min(1, Math.max(0, (event.clientY - bounds.top) / bounds.height));

  event.currentTarget.style.setProperty(
    "--dufynd-ry",
    `${((x - 0.5) * 8).toFixed(2)}deg`,
  );
  event.currentTarget.style.setProperty(
    "--dufynd-rx",
    `${((0.5 - y) * 6).toFixed(2)}deg`,
  );
  event.currentTarget.style.setProperty(
    "--dufynd-mx",
    `${(x * 100).toFixed(1)}%`,
  );
  event.currentTarget.style.setProperty(
    "--dufynd-my",
    `${(y * 100).toFixed(1)}%`,
  );
}

function resetPointer(event: PointerEvent<HTMLDivElement>) {
  event.currentTarget.style.setProperty("--dufynd-rx", "0deg");
  event.currentTarget.style.setProperty("--dufynd-ry", "0deg");
  event.currentTarget.style.setProperty("--dufynd-mx", "50%");
  event.currentTarget.style.setProperty("--dufynd-my", "34%");
}

export default function FragranceVisual({
  imageUrl,
  alt,
  variant = "card",
  className = "",
  priority = false,
  mode = "auto",
}: {
  imageUrl?: string | null;
  alt: string;
  variant?: VisualVariant;
  className?: string;
  priority?: boolean;
  mode?: VisualMode;
}) {
  const resolvedMode =
    mode === "auto"
      ? imageUrl?.includes("/products/pilot/")
        ? "editorial"
        : "cutout"
      : mode;

  if (resolvedMode === "editorial" && imageUrl) {
    return (
      <div
        data-variant={variant}
        className={`dufynd-editorial-depth-stage ${className}`}
        style={{ ...BASE_STYLE }}
        onPointerMove={updatePointer}
        onPointerLeave={resetPointer}
      >
        <div className="dufynd-editorial-depth-object">
          {/* eslint-disable-next-line @next/next/no-img-element */}
          <img
            src={imageUrl}
            alt={alt}
            loading={priority ? "eager" : "lazy"}
            fetchPriority={priority ? "high" : "auto"}
            decoding="async"
            className="dufynd-editorial-depth-image"
          />
        </div>
        <div className="dufynd-editorial-depth-vignette" aria-hidden />
        <div className="dufynd-editorial-depth-glint" aria-hidden />
      </div>
    );
  }

  return (
    <div
      data-variant={variant}
      className={`dufynd-product-stage ${className}`}
      style={{ ...BASE_STYLE }}
      onPointerMove={updatePointer}
      onPointerLeave={resetPointer}
    >
      <div className="dufynd-product-light" aria-hidden />
      <div className="dufynd-product-shadow" aria-hidden />

      <div className="dufynd-product-object">
        <div className="dufynd-product-float">
          {imageUrl ? (
            // eslint-disable-next-line @next/next/no-img-element
            <img
              src={imageUrl}
              alt={alt}
              loading={priority ? "eager" : "lazy"}
              fetchPriority={priority ? "high" : "auto"}
              decoding="async"
              className="dufynd-product-image"
            />
          ) : (
            <div className="dufynd-product-placeholder" aria-hidden>
              <div className="h-3 w-10 rounded-t bg-(--ink)/80" />
              <div className="h-3 w-7 bg-(--ink)/60" />
              <div className="grid h-24 w-20 place-items-center rounded-[22px] border border-white/80 bg-white/80 shadow-lg backdrop-blur-sm">
                <span className="text-[9px] font-semibold tracking-[0.18em] text-(--ink)/70">
                  DUFYND
                </span>
              </div>
            </div>
          )}
        </div>
      </div>

      <div className="dufynd-product-sheen" aria-hidden />
    </div>
  );
}
