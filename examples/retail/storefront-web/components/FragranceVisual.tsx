"use client";

import type { CSSProperties, PointerEvent } from "react";
import type { FragranceVisualWorld } from "@/lib/fragranceCatalog";

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

const WORLD_BACKGROUNDS: Record<FragranceVisualWorld, string> = {
  amber:
    "radial-gradient(circle at 50% 34%, rgba(211,151,54,0.18), transparent 34%), linear-gradient(145deg, #171310 0%, #0b0c0e 100%)",
  mineral:
    "radial-gradient(circle at 50% 34%, rgba(91,151,138,0.18), transparent 34%), linear-gradient(145deg, #101716 0%, #090c0d 100%)",
  ember:
    "radial-gradient(circle at 50% 34%, rgba(177,112,67,0.19), transparent 34%), linear-gradient(145deg, #18110e 0%, #0b0b0d 100%)",
  silk:
    "radial-gradient(circle at 50% 34%, rgba(177,140,153,0.17), transparent 34%), linear-gradient(145deg, #181315 0%, #0c0b0d 100%)",
  noir:
    "radial-gradient(circle at 50% 34%, rgba(154,111,72,0.15), transparent 32%), linear-gradient(145deg, #111214 0%, #07080a 100%)",
};

function stageStyle(world: FragranceVisualWorld): StageStyle {
  return {
    ...BASE_STYLE,
    background: WORLD_BACKGROUNDS[world],
  };
}

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
  world = "amber",
}: {
  imageUrl?: string | null;
  cutoutUrl?: string | null;
  backdropUrl?: string | null;
  alt: string;
  variant?: VisualVariant;
  className?: string;
  priority?: boolean;
  mode?: VisualMode;
  world?: FragranceVisualWorld;
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

  if (!resolvedImageUrl) {
    return (
      <div
        data-variant={variant}
        data-dufynd-visual-state="missing"
        data-dufynd-visual-world={world}
        className={`dufynd-neutral-visual-stage ${className}`}
        role="img"
        aria-label={`${alt} – kein freigegebenes Produktbild`}
      >
        <div
          aria-hidden
          className="dufynd-neutral-visual-atmosphere"
        >
          <span className="dufynd-neutral-visual-ring dufynd-neutral-visual-ring--outer" />
          <span className="dufynd-neutral-visual-ring dufynd-neutral-visual-ring--inner" />
          <span className="dufynd-neutral-visual-glow" />
        </div>
        <div className="dufynd-neutral-visual-copy">
          <span className="dufynd-neutral-visual-brand">
            DUFYND
          </span>
          <strong>{alt}</strong>
          <em>Kein freigegebenes Produktbild</em>
        </div>
      </div>
    );
  }

    if (resolvedMode === "editorial" && imageUrl) {
    return (
      <div
        data-variant={variant}
        data-dufynd-visual-world={world}
        className={`dufynd-editorial-depth-stage ${className}`}
        style={stageStyle(world)}
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
      data-dufynd-visual-world={world}
      className={`dufynd-product-stage ${className}`}
      style={stageStyle(world)}
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
          ) : null}
        </div>
      </div>

      <div className="dufynd-product-sheen" aria-hidden />
    </div>
  );
}
