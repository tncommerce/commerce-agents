"use client";

import { useEffect, useRef } from "react";

import {
  captureAcquisitionEntry,
  trackAnalyticsEvent,
} from "@/lib/analytics";

export default function AcquisitionAnalytics({
  source,
  trackPageView = true,
}: {
  source: string;
  trackPageView?: boolean;
}) {
  const trackedRef = useRef(false);

  useEffect(() => {
    if (trackedRef.current) return;
    trackedRef.current = true;

    const attribution = captureAcquisitionEntry();
    const landingSource = attribution?.source && attribution.source !== "unknown"
      ? `${source}_${attribution.source}`
      : source;

    if (trackPageView) {
      void trackAnalyticsEvent("page_view", {
        source: landingSource,
        surface: "acquisition_landing",
      });
    }
  }, [source, trackPageView]);

  return null;
}
