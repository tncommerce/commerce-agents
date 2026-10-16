"use client";

import { useEffect, useRef, useState, type PointerEvent } from "react";
import type { PerfumeSpatialController } from "./perfumeSpatialRenderer";
import styles from "./PerfumeObject.module.css";

type DeviceNavigator = Navigator & { deviceMemory?: number; connection?: { saveData?: boolean; effectiveType?: string } };

/** Original procedural glass study. The same scene is prerendered for the no-WebGL path. */
export default function PerfumeObject({ className = "" }: { className?: string }) {
  const host = useRef<HTMLDivElement>(null);
  const controller = useRef<PerfumeSpatialController | null>(null);
  const exploredRef = useRef(false);
  const [explored, setExplored] = useState(false);
  const [state, setState] = useState<"loading" | "ready" | "fallback">("loading");
  const [reason, setReason] = useState("");

  useEffect(() => {
    const target = host.current;
    if (!target) return;
    let cancelled = false;
    let started = false;
    let paused = false;
    let visible = false;
    let idle: number | ReturnType<typeof setTimeout> = 0;
    const motion = window.matchMedia("(prefers-reduced-motion: reduce)");
    const device = navigator as DeviceNavigator;
    const fallback = (why: string) => {
      paused = true;
      if ("cancelIdleCallback" in window) window.cancelIdleCallback(idle as number);
      clearTimeout(idle);
      controller.current?.dispose();
      controller.current = null;
      if (!cancelled) {
        setReason(why);
        setState("fallback");
      }
    };
    const restricted = motion.matches ? "reduced-motion"
      : device.connection?.saveData ? "save-data"
      : device.deviceMemory !== undefined && device.deviceMemory <= 2 ? "low-memory"
      : device.hardwareConcurrency !== undefined && device.hardwareConcurrency <= 2 ? "low-cores"
      : /^(slow-2g|2g)$/.test(device.connection?.effectiveType || "") ? "slow-connection"
      : "";
    if (restricted) {
      setReason(restricted);
      setState("fallback");
      return;
    }
    const start = async () => {
      if (started || cancelled || paused || !visible || motion.matches) return;
      started = true;
      const probe = document.createElement("canvas");
      const gl = probe.getContext("webgl2", { failIfMajorPerformanceCaveat: false });
      if (!gl) { fallback("no-webgl"); return; }
      const gpuInfo = gl.getExtension("WEBGL_debug_renderer_info");
      const softwareRenderer = gpuInfo && /SwiftShader|llvmpipe|software|Microsoft Basic Render/i.test(String(gl.getParameter(gpuInfo.UNMASKED_RENDERER_WEBGL)));
      gl.getExtension("WEBGL_lose_context")?.loseContext();
      if (softwareRenderer) { fallback("software-renderer"); return; }
      if (!gpuInfo) {
        const performanceProbe = document.createElement("canvas");
        const safeContext = performanceProbe.getContext("webgl2", { failIfMajorPerformanceCaveat: true });
        if (!safeContext) { fallback("major-performance-caveat"); return; }
        safeContext.getExtension("WEBGL_lose_context")?.loseContext();
      }
      try {
        const { createPerfumeSpatialRenderer } = await import("./perfumeSpatialRenderer");
        if (cancelled || paused || motion.matches) return;
        if (!visible) { started = false; return; }
        const instance = await createPerfumeSpatialRenderer(target, {
          reducedMotion: false,
          isVisible: () => visible && !document.hidden,
          onContextLost: () => fallback("context-lost"),
        });
        if (cancelled || paused || motion.matches) { instance.dispose(); return; }
        controller.current = instance;
        controller.current.setVisible(visible);
        controller.current.setExplored(exploredRef.current, true);
        setState("ready");
      } catch {
        fallback("initialization-failed");
      }
    };
    const observer = new IntersectionObserver(([entry]) => {
      visible = entry.isIntersecting;
      controller.current?.setVisible(visible);
      if (!visible) {
        if ("cancelIdleCallback" in window) window.cancelIdleCallback(idle as number);
        clearTimeout(idle);
      }
      if (visible && !started && !paused) {
        if ("requestIdleCallback" in window) {
          idle = window.requestIdleCallback(() => void start(), { timeout: 1400 });
        } else idle = setTimeout(() => void start(), 180);
      }
    }, { threshold: .05 });
    observer.observe(target);
    const motionChanged = () => { if (motion.matches) fallback("reduced-motion"); };
    motion.addEventListener("change", motionChanged);
    return () => {
      cancelled = true;
      observer.disconnect();
      motion.removeEventListener("change", motionChanged);
      if ("cancelIdleCallback" in window) window.cancelIdleCallback(idle as number);
      clearTimeout(idle);
      controller.current?.dispose();
      controller.current = null;
    };
  }, []);

  function point(event: PointerEvent<HTMLDivElement>) {
    if (event.pointerType === "touch" || !window.matchMedia("(hover: hover) and (pointer: fine)").matches) return;
    const bounds = event.currentTarget.getBoundingClientRect();
    const x = Math.max(-1, Math.min(1, (event.clientX - bounds.left) / bounds.width * 2 - 1));
    const y = Math.max(-1, Math.min(1, (event.clientY - bounds.top) / bounds.height * 2 - 1));
    controller.current?.setPointer(x, y);
  }

  function toggle() {
    const next = !explored;
    exploredRef.current = next;
    setExplored(next);
    controller.current?.setExplored(next);
  }

  return (
    <figure className={`${styles.figure} ${className}`} data-perfume-object="original" data-dufynd-bottle="original"
      data-explored={explored ? "true" : "false"} data-spatial-state={state} data-fallback-reason={reason}>
      <noscript><style>{"[data-dufynd-bottle-control]{display:none}"}</style></noscript>
      <div className={styles.scene} onPointerMove={point} onPointerLeave={() => controller.current?.setPointer(0, 0)}>
        {/* eslint-disable-next-line @next/next/no-img-element */}
        <img className={styles.poster} src={explored ? "/assets/atelier/perfume-study-open.webp" : "/assets/atelier/perfume-study-closed.webp"}
          width={700} height={660} fetchPriority="high" decoding="async" data-dufynd-spatial-poster="true"
          alt={explored ? "Geöffnete DUFYND Flakonstudie: Kappe, Sprühkopf, Glas und bernsteinfarbene Flüssigkeit." : "Originale DUFYND Flakonstudie aus klarem Glas, bernsteinfarbener Flüssigkeit und champagnerfarbenem Metall."} />
        <div ref={host} className={styles.canvas} data-dufynd-spatial-canvas="true" aria-hidden="true" />
        <span className={styles.studyLabel} aria-hidden="true">DUFYND · Étude 01</span>
      </div>
      <figcaption className={styles.controls}>
        <span className={styles.caption}>Glas. Licht. Parfum.</span>
        <button type="button" className={styles.control} aria-pressed={explored}
          aria-label={explored ? "Flakon schließen" : "Flakon erkunden: räumlich öffnen"}
          onClick={toggle} data-perfume-explore="true" data-dufynd-bottle-control="true">
          <svg width="18" height="18" viewBox="0 0 18 18" fill="none" aria-hidden="true">
            <path d="M9 4v10M4 9h10" stroke="currentColor" strokeWidth="1.1" className={styles.controlIcon} />
            <circle cx="9" cy="9" r="8" stroke="currentColor" strokeOpacity=".35" />
          </svg>
          {explored ? "Flakon schließen" : "Flakon erkunden"}
        </button>
      </figcaption>
    </figure>
  );
}
