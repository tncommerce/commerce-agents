"use client";

import { useEffect, useState } from "react";

import OfferSectionLink from "@/components/OfferSectionLink";

export default function MobileOfferBar({
  brand,
  name,
  productId,
  triggerId = "dufynd-hero-offer-cta",
}: {
  brand: string;
  name: string;
  productId: string;
  triggerId?: string;
}) {
  const [visible, setVisible] = useState(false);

  useEffect(() => {
    const trigger = document.getElementById(triggerId);
    const offers = document.getElementById("angebote");
    if (!trigger) {
      setVisible(false);
      return;
    }

    const inViewport = (element: Element) => {
      const bounds = element.getBoundingClientRect();
      return (
        bounds.bottom > 0 &&
        bounds.top < window.innerHeight &&
        bounds.right > 0 &&
        bounds.left < window.innerWidth
      );
    };
    const syncFromBounds = () => {
      setVisible(
        !inViewport(trigger) && !(offers && inViewport(offers)),
      );
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

    const observer = new IntersectionObserver(syncFromBounds, {
      threshold: 0.01,
    });
    observer.observe(trigger);
    if (offers) observer.observe(offers);
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
        <OfferSectionLink
          productId={productId}
          source="mobile_offer_bar"
          className="shrink-0 rounded-xl bg-(--accent-strong) px-4 py-2.5 text-[12px] font-semibold text-white"
        >
          Angebote prüfen
        </OfferSectionLink>
      </div>
    </div>
  );
}
