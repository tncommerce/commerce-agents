"use client";

import { useEffect, useRef } from "react";

import { trackAnalyticsEvent } from "@/lib/analytics";

const ALLOWED_CHANNELS = new Set([
  "tiktok",
  "instagram",
  "youtube",
  "organic",
  "newsletter",
  "partner",
]);

export default function AcquisitionAnalytics({
  source,
}: {
  source: string;
}) {
  const trackedRef = useRef(false);

  useEffect(() => {
    if (trackedRef.current) return;
    trackedRef.current = true;

    const params = new URLSearchParams(
      window.location.search,
    );
    const channel = params.get("src");
    const acquisitionSource =
      channel && ALLOWED_CHANNELS.has(channel)
        ? `${source}_${channel}`
        : source;

    void trackAnalyticsEvent("page_view", {
      source: acquisitionSource,
      surface: "acquisition_landing",
    });
  }, [source]);

  return null;
}
