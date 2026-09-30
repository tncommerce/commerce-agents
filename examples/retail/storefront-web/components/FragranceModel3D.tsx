"use client";

import { createElement, useEffect, useState } from "react";

import FragranceVisual from "./FragranceVisual";

import { ensureModelViewer } from "@/lib/modelViewerLoader";

function safeModelSource(modelUrl?: string | null): string | null {
  const candidate = modelUrl?.trim();
  if (!candidate) return null;

  const hasGlbPath = (value: string) => {
    try {
      return new URL(value, "https://dufynd.invalid")
        .pathname.toLowerCase()
        .endsWith(".glb");
    } catch {
      return false;
    }
  };

  if (!hasGlbPath(candidate)) return null;

  // Local, version-controlled GLB assets are preferred for DUFYND pilots.
  // Reject protocol-relative URLs so "//example.com/model.glb" cannot bypass
  // the external-source policy.
  if (candidate.startsWith("/") && !candidate.startsWith("//")) {
    return candidate;
  }

  try {
    const url = new URL(candidate);
    return url.protocol === "https:" ? url.toString() : null;
  } catch {
    return null;
  }
}

export default function FragranceModel3D({
  modelUrl,
  imageUrl,
  cutoutUrl,
  backdropUrl,
  alt,
  className = "",
  priority = false,
}: {
  modelUrl?: string | null;
  imageUrl?: string | null;
  cutoutUrl?: string | null;
  backdropUrl?: string | null;
  alt: string;
  className?: string;
  priority?: boolean;
}) {
  const [viewerReady, setViewerReady] = useState(false);
  const [loadedModel, setLoadedModel] = useState<string | null>(null);
  const [failedModel, setFailedModel] = useState<string | null>(null);
  const [reducedMotion, setReducedMotion] = useState(false);
  const safeModelUrl = safeModelSource(modelUrl);

  useEffect(() => {
    const media = window.matchMedia("(prefers-reduced-motion: reduce)");
    const sync = () => setReducedMotion(media.matches);
    sync();
    media.addEventListener?.("change", sync);
    return () => media.removeEventListener?.("change", sync);
  }, []);

  useEffect(() => {
    if (!safeModelUrl) return;
    let active = true;

    ensureModelViewer()
      .then(() => {
        if (active) setViewerReady(Boolean(customElements.get("model-viewer")));
      })
      .catch(() => {
        if (active) setViewerReady(false);
      });

    return () => {
      active = false;
    };
  }, [safeModelUrl]);

  if (!safeModelUrl || !viewerReady || failedModel === safeModelUrl) {
    return (
      <FragranceVisual
        imageUrl={imageUrl}
        cutoutUrl={cutoutUrl}
        backdropUrl={backdropUrl}
        alt={alt}
        variant="hero"
        mode={cutoutUrl ? "cutout" : "editorial"}
        className={className}
        priority={priority}
      />
    );
  }

  return (
    <div className={`dufynd-model-stage ${className}`}>
      <div className="dufynd-model-halo" aria-hidden />
      {createElement("model-viewer", {
        key: safeModelUrl,
        src: safeModelUrl,
        onload: () => setLoadedModel(safeModelUrl),
        onerror: () => setFailedModel(safeModelUrl),
        poster: cutoutUrl || imageUrl || undefined,
        alt,
        "camera-controls": "",
        "disable-pan": "",
        "interaction-prompt": "none",
        "touch-action": "pan-y",
        "auto-rotate": reducedMotion ? undefined : "",
        "auto-rotate-delay": reducedMotion ? undefined : "1400",
        "rotation-per-second": reducedMotion ? undefined : "7deg",
        "camera-orbit": "16deg 78deg 2.8m",
        "min-camera-orbit": "auto 68deg 2.3m",
        "max-camera-orbit": "auto 86deg 3.5m",
        exposure: "1.05",
        "shadow-intensity": "0.95",
        "shadow-softness": "0.8",
        loading: priority ? "eager" : "lazy",
        reveal: "auto",
        className: "dufynd-model-viewer",
      })}
      {loadedModel === safeModelUrl ? (
        <div className="dufynd-model-hint" aria-hidden>
          Ziehen zum Drehen
        </div>
      ) : null}
    </div>
  );
}
