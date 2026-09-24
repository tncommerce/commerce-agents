"use client";

import { createElement, useEffect, useState } from "react";

import FragranceVisual from "./FragranceVisual";

const MODEL_VIEWER_SRC =
  "https://unpkg.com/@google/model-viewer@4.3.1/dist/model-viewer.min.js";

function ensureModelViewer(): Promise<void> {
  if (typeof window === "undefined") return Promise.resolve();
  if (customElements.get("model-viewer")) return Promise.resolve();

  const existing = document.querySelector<HTMLScriptElement>(
    'script[data-dufynd-model-viewer="true"]',
  );

  if (existing) {
    return new Promise((resolve, reject) => {
      existing.addEventListener("load", () => resolve(), { once: true });
      existing.addEventListener("error", () => reject(new Error("3D viewer failed to load")), {
        once: true,
      });
    });
  }

  return new Promise((resolve, reject) => {
    const script = document.createElement("script");
    script.type = "module";
    script.src = MODEL_VIEWER_SRC;
    script.dataset.dufyndModelViewer = "true";
    script.onload = () => resolve();
    script.onerror = () => reject(new Error("3D viewer failed to load"));
    document.head.appendChild(script);
  });
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

  useEffect(() => {
    if (!modelUrl) return;
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
