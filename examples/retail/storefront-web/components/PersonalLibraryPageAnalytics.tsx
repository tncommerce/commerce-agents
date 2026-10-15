"use client";

import { useEffect, useRef } from "react";

import AcquisitionAnalytics from "@/components/AcquisitionAnalytics";

import { trackAnalyticsEvent } from "@/lib/analytics";
import { measurementAllowed, subscribeMeasurement } from "@/lib/measurementConsent";

export default function PersonalLibraryPageAnalytics({
  source,
}: {
  source: "wishlist_page" | "collection_page";
}) {
  const trackedRef = useRef<string | null>(null);

  useEffect(() => {
    const trackCurrentPage = () => {
      if (!measurementAllowed()) {
        trackedRef.current = null;
        return;
      }
      if (trackedRef.current === source) return;
      trackedRef.current = source;
      void trackAnalyticsEvent("page_view", {
        source,
        surface: "personal_library_page",
      });
    };
    const unsubscribe = subscribeMeasurement(trackCurrentPage);
    trackCurrentPage();
    return unsubscribe;
  }, [source]);

  return <AcquisitionAnalytics source={source} trackPageView={false} />;
}
