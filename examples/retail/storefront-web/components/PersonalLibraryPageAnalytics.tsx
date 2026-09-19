"use client";

import { useEffect, useRef } from "react";

import { trackAnalyticsEvent } from "@/lib/analytics";

export default function PersonalLibraryPageAnalytics({
  source,
}: {
  source: "wishlist_page" | "collection_page";
}) {
  const trackedRef = useRef(false);

  useEffect(() => {
    if (trackedRef.current) return;
    trackedRef.current = true;

    void trackAnalyticsEvent("page_view", {
      source,
      surface: "personal_library_page",
    });
  }, [source]);

  return null;
}
