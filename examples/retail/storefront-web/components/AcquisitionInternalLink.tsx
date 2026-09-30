"use client";

import type { ComponentPropsWithoutRef } from "react";
import { useEffect, useState } from "react";

import {
  appendAcquisitionAttribution,
  rememberAcquisitionAttribution,
} from "@/lib/analytics";

const ALLOWED_CHANNELS = new Set([
  "tiktok",
  "instagram",
  "youtube",
  "organic",
  "newsletter",
  "partner",
]);

type Props = Omit<ComponentPropsWithoutRef<"a">, "href"> & {
  href: string;
};

export default function AcquisitionInternalLink({
  href,
  ...props
}: Props) {
  const [attributedHref, setAttributedHref] = useState(href);

  useEffect(() => {
    const params = new URLSearchParams(window.location.search);
    const source = params.get("src");

    if (source && ALLOWED_CHANNELS.has(source)) {
      rememberAcquisitionAttribution({
        source,
        campaignId: params.get("cmp"),
        contentId: params.get("content"),
      });
    }

    setAttributedHref(appendAcquisitionAttribution(href));
  }, [href]);

  return <a {...props} href={attributedHref} />;
}
