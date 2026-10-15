"use client";

import { useEffect, useRef } from "react";

import { trackAnalyticsEvent } from "@/lib/analytics";
import { measurementAllowed, subscribeMeasurement } from "@/lib/measurementConsent";

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
  const trackedRef = useRef<string | null>(null);

  useEffect(() => {
    const key = `${productId}:${relatedProductId}:${source}:${surface}`;
    const trackCurrentComparison = () => {
      if (!measurementAllowed()) {
        trackedRef.current = null;
        return;
      }
      if (trackedRef.current === key) return;
      trackedRef.current = key;
      void trackAnalyticsEvent("comparison_start", {
        product_id: productId,
        related_product_id: relatedProductId,
        source,
        surface,
      });
    };
    const unsubscribe = subscribeMeasurement(trackCurrentComparison);
    trackCurrentComparison();
    return unsubscribe;
  }, [productId, relatedProductId, source, surface]);

  return null;
}
