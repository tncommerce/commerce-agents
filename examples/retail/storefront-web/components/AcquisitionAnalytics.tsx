"use client";

import { useEffect, useRef } from "react";

import { trackAnalyticsEvent } from "@/lib/analytics";

export default function AcquisitionAnalytics({
  source,
}: {
  source: string;
}) {
  const trackedRef = useRef(false);

  useEffect(() => {
    if (trackedRef.current) return;
    trackedRef.current = true;

    void trackAnalyticsEvent("page_view", {
      source,
      surface: "acquisition_landing",
    });
  }, [source]);

  return null;
}
