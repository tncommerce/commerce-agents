"use client";

import { useEffect, useState } from "react";

export default function MobileOfferBar({
  brand,
  name,
  triggerId = "dufynd-hero-offer-cta",
}: {
  brand: string;
  name: string;
  triggerId?: string;
}) {
  const [visible, setVisible] = useState(false);

  useEffect(() => {
    const trigger = document.getElementById(triggerId);
    if (!trigger) {
      setVisible(false);
      return;
    }

    const syncFromBounds = () => {
      const bounds = trigger.getBoundingClientRect();
      const inViewport =
        bounds.bottom > 0 &&
        bounds.top < window.innerHeight &&
        bounds.right > 0 &&
        bounds.left < window.innerWidth;
      setVisible(!inViewport);
    };

    syncFromBounds();

    if (typeof IntersectionObserver === "undefined") {
      window.addEventListener("scroll", syncFromBounds, { passive: true });
      window.addEventListener("resize", syncFromBounds);
      return () => {
        window.removeEventListener("scroll", syncFromBounds);
        window.removeEventListener("resize", syncFromBounds);
      };
    }

    const observer = new IntersectionObserver(
      ([entry]) => setVisible(!entry.isIntersecting),
      { threshold: 0.01 },
    );
    observer.observe(trigger);
    return () => observer.disconnect();
  }, [triggerId]);

  if (!visible) return null;

  return (
    <div className="dufynd-mobile-offer-bar fixed inset-x-0 bottom-0 z-40 border-t border-(--line) bg-(--card)/94 px-3 pt-2.5 shadow-[0_-10px_30px_rgba(23,21,19,0.10)] backdrop-blur-xl sm:hidden">
      <div className="mx-auto flex max-w-[420px] items-center gap-3">
        <div className="min-w-0 flex-1">
          <div className="truncate text-[11px] font-semibold text-(--ink)">
            {brand} {name}
          </div>
          <div className="text-[10px] text-(--ink-soft)">
            Kaufoptionen prüfen
          </div>
        </div>
        <a
          href="#angebote"
          className="shrink-0 rounded-xl bg-(--accent-strong) px-4 py-2.5 text-[12px] font-semibold text-white"
        >
          Angebote prüfen
        </a>
      </div>
    </div>
  );
}
