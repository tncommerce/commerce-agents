"use client";

import { useEffect, useRef } from "react";

import {
  currentAcquisitionAttribution,
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
    const explicitChannel =
      requestedChannel &&
      ALLOWED_CHANNELS.has(requestedChannel)
        ? requestedChannel
        : null;
    const campaignId = params.get("cmp");
    const contentId = params.get("content");

    if (explicitChannel) {
      rememberAcquisitionAttribution({
        source: explicitChannel,
        campaignId,
        contentId,
      });
    } else if (!currentAcquisitionAttribution()) {
      rememberAcquisitionAttribution({
        source: "organic",
        campaignId: null,
        contentId: null,
      });
    }

    const landingSource = explicitChannel
      ? `${source}_${explicitChannel}`
      : source;

    void trackAnalyticsEvent("page_view", {
      source: landingSource,
      surface: "acquisition_landing",
    });
  }, [source]);

  return null;
}
