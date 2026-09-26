"use client";

import { useEffect, useState } from "react";

export default function MobileOfferBar({
  brand,
  name,
  heroId = "dufynd-fragrance-hero",
}: {
  brand: string;
  name: string;
  heroId?: string;
}) {
  const [visible, setVisible] = useState(false);

  useEffect(() => {
    const hero = document.getElementById(heroId);
    if (!hero || typeof IntersectionObserver === "undefined") {
      setVisible(true);
      return;
    }

    const observer = new IntersectionObserver(
      ([entry]) => setVisible(!entry.isIntersecting),
      { threshold: 0.08 },
    );
    observer.observe(hero);
    return () => observer.disconnect();
  }, [heroId]);

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
