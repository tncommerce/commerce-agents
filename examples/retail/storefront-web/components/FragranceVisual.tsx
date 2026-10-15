"use client";

import { useState, type CSSProperties, type PointerEvent } from "react";
import type { FragranceVisualWorld } from "@/lib/fragranceCatalog";
import styles from "./FragranceVisual.module.css";
import catalogPackshots from "../../data/dufynd_catalog_packshots.json";

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

// These reviewed studio photographs have an opaque white matte, even when a
// caller supplies them through the legacy cutout slot. Do not shadow the bitmap
// rectangle or alter the licensed pixels to make it look transparent.
const WHITE_MATTE_PHOTOGRAPHS = new Set([
  "https://www.topparfuemerie.de/media/catalog/product/8/2/825869_3700578501998_051.png",
  "https://fooddrinkssuppliers.com/media/cosmetics/3605533286555.webp",
]);

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

function stageStyle(
  world: FragranceVisualWorld,
  variant: VisualVariant,
): StageStyle {
  return {
    ...BASE_STYLE,
    // Comparable catalogue cards share a neutral surface. Hero art is unchanged.
    background: variant === "card" ? "#f5f3ee" : WORLD_BACKGROUNDS[world],
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
  catalogProductId,
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
  /** Opt catalog surfaces into exact, rights-cleared original photographs. */
  catalogProductId?: string;
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
  const catalogPhoto = variant === "card" && catalogProductId
    ? catalogPackshots.entries.find((entry) => entry.product_id === catalogProductId)
    : undefined;
  const catalogPhotoPolicy = variant === "card" && Boolean(catalogProductId);
  const resolvedImageUrl = catalogPhotoPolicy ? catalogPhoto?.image_url : cutoutUrl || imageUrl;
  const whiteMatte = WHITE_MATTE_PHOTOGRAPHS.has(resolvedImageUrl || "");
  const catalogClass = variant === "card" ? styles.catalog : "";
  const [failedImageUrl, setFailedImageUrl] = useState<string | null>(null);
  const [failedBackdropUrl, setFailedBackdropUrl] = useState<string | null>(null);
  const imageUnavailable = Boolean(
    resolvedImageUrl && failedImageUrl === resolvedImageUrl,
  );
  const resolvedMode = catalogPhotoPolicy ? "cutout" :
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

  if (!resolvedImageUrl || imageUnavailable) {
    const fallbackCopy = imageUnavailable
      ? "Produktbild derzeit nicht verfügbar"
      : catalogPhotoPolicy ? "Produktfoto nicht verfügbar" : "Kein freigegebenes Produktbild";
    return (
      <div
        data-variant={variant}
        data-dufynd-visual-state={imageUnavailable ? "unavailable" : "missing"}
        data-dufynd-visual-world={world}
        data-dufynd-image-kind="missing"
        data-dufynd-photo-status={catalogPhotoPolicy ? "hold" : undefined}
        data-dufynd-product-id={catalogProductId}
        className={`dufynd-neutral-visual-stage ${catalogClass} ${className}`}
        role="img"
        aria-label={`${alt} – ${fallbackCopy}`}
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
          <em>{fallbackCopy}</em>
        </div>
      </div>
    );
  }

  if (resolvedMode === "editorial" && imageUrl) {
    return (
      <div
        data-variant={variant}
        data-dufynd-visual-world={world}
        data-dufynd-image-kind="editorial"
        className={`dufynd-editorial-depth-stage ${catalogClass} ${className}`}
        style={stageStyle(world, variant)}
        onPointerMove={variant === "hero" ? updatePointer : undefined}
        onPointerLeave={variant === "hero" ? resetPointer : undefined}
      >
        {variant === "hero" && imageUrl ? (
          // Decorative fill preserves the editorial palette around the uncropped artwork.
          // eslint-disable-next-line @next/next/no-img-element
          <img src={imageUrl} alt="" aria-hidden loading={priority ? "eager" : "lazy"} decoding="async" className="dufynd-editorial-depth-fill" />
        ) : null}
        <div className="dufynd-editorial-depth-object">
          {/* eslint-disable-next-line @next/next/no-img-element */}
          <img
            src={imageUrl}
            ref={(image) => {
              if (image?.complete && image.naturalWidth === 0) {
                setFailedImageUrl(resolvedImageUrl);
              }
            }}
            onError={() => setFailedImageUrl(resolvedImageUrl)}
            alt={displayAlt}
            loading={priority ? "eager" : "lazy"}
            fetchPriority={priority ? "high" : "auto"}
            decoding="async"
            className="dufynd-editorial-depth-image"
          />
        </div>
        {variant === "card" ? (
          <span className={styles.editorialLabel}>Inszenierung</span>
        ) : null}
        <div className="dufynd-editorial-depth-vignette" aria-hidden />
        <div className="dufynd-editorial-depth-glint" aria-hidden />
      </div>
    );
  }

  return (
    <div
      data-variant={variant}
      data-dufynd-visual-world={world}
      data-dufynd-image-kind={!catalogPhotoPolicy && cutoutUrl && !whiteMatte ? "cutout" : "photograph"}
      data-dufynd-photo-status={catalogPhotoPolicy ? "approved" : undefined}
      data-dufynd-product-id={catalogProductId}
      data-dufynd-image-matte={whiteMatte ? "white" : undefined}
      className={`dufynd-product-stage ${catalogClass} ${className}`}
      style={{
        ...stageStyle(world, variant),
        ...(variant === "card" && (whiteMatte || catalogPhotoPolicy) ? { background: "#fff" } : {}),
      }}
      onPointerMove={variant === "hero" ? updatePointer : undefined}
      onPointerLeave={variant === "hero" ? resetPointer : undefined}
    >
      {variant === "hero" && backdropUrl && failedBackdropUrl !== backdropUrl ? (
        <>
          {/* eslint-disable-next-line @next/next/no-img-element */}
          <img
            src={backdropUrl}
            ref={(image) => {
              if (image?.complete && image.naturalWidth === 0) {
                setFailedBackdropUrl(backdropUrl);
              }
            }}
            onError={() => setFailedBackdropUrl(backdropUrl)}
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
              ref={(image) => {
                if (image?.complete && image.naturalWidth === 0) {
                  setFailedImageUrl(resolvedImageUrl);
                }
              }}
              onError={() => setFailedImageUrl(resolvedImageUrl)}
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
      {catalogPhoto?.attribution_text && catalogPhoto.license_name ? (
        <span className={styles.photoAttribution} data-dufynd-image-attribution>
          Bild: {catalogPhoto.attribution_text} · {catalogPhoto.license_name}
        </span>
      ) : null}
    </div>
  );
}
