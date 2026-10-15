"use client";

import { useEffect, useRef } from "react";

import {
  captureAcquisitionEntry,
  trackAnalyticsEvent,
} from "@/lib/analytics";
import {
  measurementAllowed,
  subscribeMeasurement,
} from "@/lib/measurementConsent";

export default function AcquisitionAnalytics({
  source,
  trackPageView = true,
}: {
  source: string;
  trackPageView?: boolean;
}) {
  const trackedKeyRef = useRef<string | null>(null);

  useEffect(() => {
    const key = `${source}:${trackPageView ? "page" : "no-page"}`;
    const trackCurrentPage = () => {
      if (
        !trackPageView ||
        trackedKeyRef.current === key ||
        !measurementAllowed()
      ) {
        return;
      }

      const attribution = captureAcquisitionEntry();
      const landingSource =
        attribution?.source && attribution.source !== "unknown"
          ? `${source}_${attribution.source}`
          : source;

      trackedKeyRef.current = key;
      void trackAnalyticsEvent("page_view", {
        source: landingSource,
        surface: "acquisition_landing",
      });
    };

    trackCurrentPage();
    return subscribeMeasurement(trackCurrentPage);
  }, [source, trackPageView]);

  return null;
}
