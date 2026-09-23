"use client";

import { useEffect } from "react";

const MAX_ROTATE_X = 5.5;
const MAX_ROTATE_Y = 7.5;

export default function DufyndDepthInteraction() {
  useEffect(() => {
    const reducedMotion = window.matchMedia(
      "(prefers-reduced-motion: reduce)",
    ).matches;

    if (reducedMotion) return;

    const stages = Array.from(
      document.querySelectorAll<HTMLElement>(".dufynd-depth-stage"),
    );

    const updateScrollDepth = () => {
      const viewportCenter = window.innerHeight / 2;
      const travel = Math.max(1, window.innerHeight * 0.7);

      for (const stage of stages) {
        const rect = stage.getBoundingClientRect();
        const center = rect.top + rect.height / 2;
        const progress = Math.min(
          1,
          Math.max(-1, (viewportCenter - center) / travel),
        );

        stage.style.setProperty(
          "--dufynd-stage-y",
          `${(progress * 6).toFixed(2)}px`,
        );
        stage.style.setProperty(
          "--dufynd-surface-y",
          `${(progress * 10).toFixed(2)}px`,
        );
        stage.style.setProperty(
          "--dufynd-bg-y",
          `${(progress * -14).toFixed(2)}px`,
        );
        stage.style.setProperty(
          "--dufynd-ambient-opacity",
          `${(0.72 + (1 - Math.abs(progress)) * 0.18).toFixed(2)}`,
        );
      }
    };

    let scrollFrame = 0;
    const onScroll = () => {
      cancelAnimationFrame(scrollFrame);
      scrollFrame = requestAnimationFrame(updateScrollDepth);
    };

    window.addEventListener("scroll", onScroll, { passive: true });
    window.addEventListener("resize", onScroll);
    updateScrollDepth();

    const cleanups = stages.map((stage) => {
      let frame = 0;

      const apply = (event: PointerEvent) => {
        if (event.pointerType === "touch") return;

        const rect = stage.getBoundingClientRect();
        const px = Math.min(
          1,
          Math.max(0, (event.clientX - rect.left) / rect.width),
        );
        const py = Math.min(
          1,
          Math.max(0, (event.clientY - rect.top) / rect.height),
        );

        cancelAnimationFrame(frame);
        frame = requestAnimationFrame(() => {
          const rotateX = (0.5 - py) * MAX_ROTATE_X * 2;
          const rotateY = (px - 0.5) * MAX_ROTATE_Y * 2;

          stage.style.setProperty("--dufynd-rx", `${rotateX.toFixed(2)}deg`);
          stage.style.setProperty("--dufynd-ry", `${rotateY.toFixed(2)}deg`);
          stage.style.setProperty("--dufynd-glow-x", `${(px * 100).toFixed(1)}%`);
          stage.style.setProperty("--dufynd-glow-y", `${(py * 100).toFixed(1)}%`);
          stage.style.setProperty("--dufynd-shadow-x", `${((px - 0.5) * -18).toFixed(1)}px`);
          stage.style.setProperty("--dufynd-shadow-y", `${(10 + py * 8).toFixed(1)}px`);
          stage.dataset.depthActive = "true";
        });
      };

      const reset = () => {
        cancelAnimationFrame(frame);
        stage.style.setProperty("--dufynd-rx", "0deg");
        stage.style.setProperty("--dufynd-ry", "0deg");
        stage.style.setProperty("--dufynd-glow-x", "50%");
        stage.style.setProperty("--dufynd-glow-y", "42%");
        stage.style.setProperty("--dufynd-shadow-x", "0px");
        stage.style.setProperty("--dufynd-shadow-y", "12px");
        delete stage.dataset.depthActive;
      };

      stage.addEventListener("pointermove", apply, { passive: true });
      stage.addEventListener("pointerleave", reset);
      stage.addEventListener("pointercancel", reset);

      return () => {
        cancelAnimationFrame(frame);
        stage.removeEventListener("pointermove", apply);
        stage.removeEventListener("pointerleave", reset);
        stage.removeEventListener("pointercancel", reset);
      };
    });

    return () => {
      cancelAnimationFrame(scrollFrame);
      window.removeEventListener("scroll", onScroll);
      window.removeEventListener("resize", onScroll);
      cleanups.forEach((cleanup) => cleanup());
    };
  }, []);

  return null;
}
