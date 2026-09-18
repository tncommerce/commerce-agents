"use client";

import { useEffect, useRef } from "react";

import { trackAnalyticsEvent } from "@/lib/analytics";

export default function ComparisonAnalytics({
  productId,
  relatedProductId,
  source = "comparison_page",
  surface = "documented_comparison",
}: {
  productId: string;
  relatedProductId: string;
  source?: string;
  surface?: string;
}) {
  const trackedRef = useRef(false);

  useEffect(() => {
    if (trackedRef.current) return;
    trackedRef.current = true;

    void trackAnalyticsEvent("comparison_start", {
      product_id: productId,
      related_product_id: relatedProductId,
      source,
      surface,
    });
  }, [productId, relatedProductId, source, surface]);

  return null;
}
