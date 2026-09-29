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
  if (window.matchMedia("(prefers-reduced-motion: reduce)").matches) return;

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
  cutoutUrl,
  backdropUrl,
  alt,
  variant = "card",
  className = "",
  priority = false,
  mode = "auto",
}: {
  imageUrl?: string | null;
  cutoutUrl?: string | null;
  backdropUrl?: string | null;
  alt: string;
  variant?: VisualVariant;
  className?: string;
  priority?: boolean;
  mode?: VisualMode;
}) {
  const resolvedImageUrl = cutoutUrl || imageUrl;
  const resolvedMode =
    mode === "auto"
      ? cutoutUrl
        ? "cutout"
        : imageUrl?.includes("/products/pilot/")
          ? "editorial"
          : "cutout"
      : mode;

  const displayAlt =
    resolvedMode === "editorial"
      ? `${alt} – stilisierte DUFYND-Inszenierung`
      : alt;

  if (resolvedMode === "editorial" && imageUrl) {
    return (
      <div
        data-variant={variant}
        className={`dufynd-editorial-depth-stage ${className}`}
        style={{ ...BASE_STYLE }}
        onPointerMove={updatePointer}
        onPointerLeave={resetPointer}
      >
        {imageUrl ? (
          // Decorative fill preserves the editorial palette around the uncropped artwork.
          // eslint-disable-next-line @next/next/no-img-element
          <img src={imageUrl} alt="" aria-hidden loading={priority ? "eager" : "lazy"} decoding="async" className="dufynd-editorial-depth-fill" />
        ) : null}
        <div className="dufynd-editorial-depth-object">
          {/* eslint-disable-next-line @next/next/no-img-element */}
          <img
            src={imageUrl}
            alt={displayAlt}
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
      className={`dufynd-product-stage ${resolvedImageUrl ? "" : "dufynd-product-stage--asset-pending"} ${className}`}
      style={{ ...BASE_STYLE }}
      onPointerMove={updatePointer}
      onPointerLeave={resetPointer}
    >
      {backdropUrl ? (
        <>
          {/* eslint-disable-next-line @next/next/no-img-element */}
          <img
            src={backdropUrl}
            alt=""
            aria-hidden
            loading={priority ? "eager" : "lazy"}
            decoding="async"
            className="dufynd-product-backdrop"
          />
          <div className="dufynd-product-backdrop-shade" aria-hidden />
        </>
      ) : null}

      <div className="dufynd-product-light" aria-hidden />
      <div className="dufynd-product-shadow" aria-hidden />

      <div className="dufynd-product-object">
        <div className="dufynd-product-float">
          {resolvedImageUrl ? (
            // eslint-disable-next-line @next/next/no-img-element
            <img
              src={resolvedImageUrl}
              alt={displayAlt}
              loading={priority ? "eager" : "lazy"}
              fetchPriority={priority ? "high" : "auto"}
              decoding="async"
              className="dufynd-product-image"
            />
          ) : (
            <div
              className="dufynd-product-asset-pending"
              data-dufynd-asset-state="pending"
              role="img"
              aria-label={`${alt} – derzeit kein freigegebenes Produktbild`}
            >
              <div
                aria-hidden
                className="dufynd-product-asset-pending-orbit dufynd-product-asset-pending-orbit--outer"
              />
              <div
                aria-hidden
                className="dufynd-product-asset-pending-orbit dufynd-product-asset-pending-orbit--inner"
              />
              <div className="dufynd-product-asset-pending-copy">
                <span>DUFYND</span>
                <strong>Produktbild in Prüfung</strong>
              </div>
            </div>
          )}
        </div>
      </div>

      <div className="dufynd-product-sheen" aria-hidden />
    </div>
  );
}
