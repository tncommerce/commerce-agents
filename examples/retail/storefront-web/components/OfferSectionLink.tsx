"use client";

import type { ReactNode } from "react";

import { trackAnalyticsEvent } from "@/lib/analytics";

export default function OfferSectionLink({
  productId,
  source,
  className,
  children,
}: {
  productId: string;
  source: string;
  className: string;
  children: ReactNode;
}) {
  return (
    <a
      href="#angebote"
      className={className}
      onClick={() => {
        void trackAnalyticsEvent("offer_section_open", {
          product_id: productId,
          source,
          surface: "fragrance_detail",
        });
      }}
    >
      {children}
    </a>
  );
}
