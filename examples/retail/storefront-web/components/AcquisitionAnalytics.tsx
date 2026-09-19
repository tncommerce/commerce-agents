"use client";

import { useEffect, useRef } from "react";

import {
  rememberAcquisitionAttribution,
  trackAnalyticsEvent,
} from "@/lib/analytics";

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
    const requestedChannel = params.get("src");
    const channel =
      requestedChannel &&
      ALLOWED_CHANNELS.has(requestedChannel)
        ? requestedChannel
        : "organic";
    const campaignId = params.get("cmp");
    const contentId = params.get("content");

    rememberAcquisitionAttribution({
      source: channel,
      campaignId,
      contentId,
    });

    void trackAnalyticsEvent("page_view", {
      source: `${source}_${channel}`,
      surface: "acquisition_landing",
    });
  }, [source]);

  return null;
}
