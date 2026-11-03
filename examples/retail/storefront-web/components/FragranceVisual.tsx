"use client";

import { useEffect, useRef, useState, type CSSProperties, type PointerEvent } from "react";
import type { FragranceVisualWorld } from "@/lib/fragranceCatalog";
import approvedOriginals from "@/lib/generated/original-photos.json";
import styles from "./FragranceVisual.module.css";

type VisualVariant = "card" | "hero";
type VisualMode = "auto" | "editorial" | "cutout";

type ApprovedOriginalPhoto = {
  url: string;
  width?: number;
  height?: number;
};

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
// Fallback instead of a permanent spinner when a permitted external photo stalls.
const PHOTO_LOAD_STALL_MS = 7_000;

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
  imageUrl,
  cutoutUrl,
  backdropUrl,
  alt,
  variant = "card",
  className = "",
  priority = false,
  mode = "auto",
  world = "amber",
  sourceSize,
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
  /** Unaltered, hash-bound merchant review photographs; never a cutout effect. */
  sourceSize?: { width: number; height: number };
}) {
  const resolvedImageUrl = cutoutUrl || imageUrl;
  const approvedOriginal = (approvedOriginals as ApprovedOriginalPhoto[]).find(
    (photo) => photo.url === resolvedImageUrl &&
      Number.isInteger(photo.width) && Number.isInteger(photo.height) &&
      Number(photo.width) > 0 && Number(photo.height) > 0,
  );
  const originalSourceSize = sourceSize || (approvedOriginal ? {
    width: approvedOriginal.width!, height: approvedOriginal.height!,
  } : undefined);
  const whiteMatte = WHITE_MATTE_PHOTOGRAPHS.has(resolvedImageUrl || "");
  const catalogClass = variant === "card" ? styles.catalog : "";
  const [failedImageUrl, setFailedImageUrl] = useState<string | null>(null);
  const [failedBackdropUrl, setFailedBackdropUrl] = useState<string | null>(null);
  // Keep a meaningful neutral loading stage until the exact source bitmap is ready.
  // A licensed URL is not proof that the image has loaded in the visitor's browser.
  const [loadedImageUrl, setLoadedImageUrl] = useState<string | null>(null);
  const primaryPhotoRef = useRef<HTMLImageElement | null>(null);
  const imageReady = Boolean(resolvedImageUrl && loadedImageUrl === resolvedImageUrl);
  const imageUnavailable = Boolean(
    resolvedImageUrl && failedImageUrl === resolvedImageUrl,
  );
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

  // Watch the actual image only when near the viewport. Lazy offscreen cards
  // must not become false "unavailable" simply because they have not loaded.
  useEffect(() => {
    const image = primaryPhotoRef.current;
    if (!image || !resolvedImageUrl || imageUnavailable || imageReady) return;
    let timeoutId: number | undefined;
    const startWatch = () => {
      if (timeoutId !== undefined) return;
      timeoutId = window.setTimeout(() => {
        if (image.isConnected && (!image.complete || image.naturalWidth === 0)) {
          setFailedImageUrl(resolvedImageUrl);
        }
      }, PHOTO_LOAD_STALL_MS);
    };
    if (typeof window.IntersectionObserver !== "function") {
      startWatch();
      return () => {
        if (timeoutId !== undefined) window.clearTimeout(timeoutId);
      };
    }
    const observer = new IntersectionObserver((entries) => {
      if (entries.some((entry) => entry.isIntersecting)) {
        startWatch();
        observer.disconnect();
      }
    }, { rootMargin: "300px" });
    observer.observe(image);
    return () => {
      observer.disconnect();
      if (timeoutId !== undefined) window.clearTimeout(timeoutId);
    };
  }, [resolvedImageUrl, imageUnavailable, imageReady]);

  if (!resolvedImageUrl || imageUnavailable) {
    const fallbackCopy = imageUnavailable
      ? "Produktbild derzeit nicht verfügbar"
      : "Kein freigegebenes Produktbild";
    return (
      <div
        data-variant={variant}
        data-dufynd-visual-state={imageUnavailable ? "unavailable" : "missing"}
        data-dufynd-visual-world={world}
        data-dufynd-image-kind="missing"
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

  if (resolvedMode === "editorial" && imageUrl && !originalSourceSize) {
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
              primaryPhotoRef.current = image;
              if (image?.complete && image.naturalWidth === 0) {
                setFailedImageUrl(resolvedImageUrl);
              }
            }}
            onLoad={() => setLoadedImageUrl(resolvedImageUrl || null)}
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

  if (originalSourceSize && resolvedImageUrl) {
    return <div data-dufynd-original-review-photo={sourceSize ? true : undefined}
      data-dufynd-original-photo={!sourceSize ? true : undefined} data-variant={variant}
      className={`${styles.sourcePhoto} ${className}`}>
      {/* Preserve the entire original bitmap and its resolution at 2x display density. */}
      {/* eslint-disable-next-line @next/next/no-img-element */}
      <img ref={primaryPhotoRef} src={resolvedImageUrl} width={originalSourceSize.width} height={originalSourceSize.height}
        style={{
          height: Math.min(variant === "card" ? 180 : 260, originalSourceSize.height / 2),
          maxWidth: `min(86%, ${originalSourceSize.width / 2}px)`,
        }}
        alt={alt} loading={priority ? "eager" : "lazy"} decoding="async"
        onLoad={() => setLoadedImageUrl(resolvedImageUrl || null)}
        onError={() => setFailedImageUrl(resolvedImageUrl)} />
    </div>;
  }

  return (
    <div
      data-variant={variant}
      data-dufynd-visual-world={world}
      data-dufynd-image-kind={cutoutUrl && !whiteMatte ? "cutout" : "photograph"}
      data-dufynd-image-matte={whiteMatte ? "white" : undefined}
      data-dufynd-photo-state={mode === "cutout" ? (imageReady ? "loaded" : "loading") : undefined}
      className={`dufynd-product-stage ${catalogClass} ${className}`}
      style={{
        ...stageStyle(world, variant),
        ...(variant === "card" && whiteMatte ? { background: "#fff" } : {}),
      }}
      onPointerMove={variant === "hero" ? updatePointer : undefined}
      onPointerLeave={variant === "hero" ? resetPointer : undefined}
    >
      {mode === "cutout" && !imageReady ? (
        <div className="dufynd-photo-loading-indicator" aria-hidden="true">
          <span>DUFYND / PRODUKTFOTO</span>
          <strong>Originalaufnahme wird geladen</strong>
          <i />
        </div>
      ) : null}
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
                primaryPhotoRef.current = image;
                if (image?.complete) {
                  if (image.naturalWidth === 0) setFailedImageUrl(resolvedImageUrl);
                  else setLoadedImageUrl(resolvedImageUrl || null);
                }
              }}
              onLoad={() => setLoadedImageUrl(resolvedImageUrl || null)}
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
    </div>
  );
}
