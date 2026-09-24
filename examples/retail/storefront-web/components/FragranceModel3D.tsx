"use client";

import { createElement, useEffect, useState } from "react";

import FragranceVisual from "./FragranceVisual";

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

  useEffect(() => {
    if (!modelUrl) return;
    let active = true;

    import("@google/model-viewer")
      .then(() => {
        if (active) setViewerReady(true);
      })
      .catch(() => {
        if (active) setViewerReady(false);
      });

    return () => {
      active = false;
    };
  }, [modelUrl]);

  if (!modelUrl || !viewerReady) {
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
        src: modelUrl,
        poster: cutoutUrl || imageUrl || undefined,
        alt,
        "camera-controls": "",
        "disable-pan": "",
        "interaction-prompt": "none",
        "touch-action": "pan-y",
        "auto-rotate": "",
        "auto-rotate-delay": "1400",
        "rotation-per-second": "7deg",
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
    </div>
  );
}
