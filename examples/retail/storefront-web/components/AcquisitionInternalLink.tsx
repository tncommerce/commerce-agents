"use client";

import type { ComponentPropsWithoutRef, SyntheticEvent } from "react";
import { useEffect, useState } from "react";

import { appendAcquisitionAttribution } from "@/lib/analytics";
import { subscribeMeasurement } from "@/lib/measurementConsent";

type Props = Omit<ComponentPropsWithoutRef<"a">, "href"> & {
  href: string;
};

export default function AcquisitionInternalLink({
  href,
  onClick,
  onAuxClick,
  onPointerDown,
  onFocus,
  ...props
}: Props) {
  const [attributedHref, setAttributedHref] = useState(href);

  useEffect(() => {
    const refreshHref = () => setAttributedHref(appendAcquisitionAttribution(href));
    const unsubscribe = subscribeMeasurement(refreshHref);
    refreshHref();
    return unsubscribe;
  }, [href]);

  // Consent and session can settle after mount. Also refresh before native
  // navigation, including keyboard and open-in-new-tab gestures.
  const refresh = (event: SyntheticEvent<HTMLAnchorElement>) => {
    event.currentTarget.href = appendAcquisitionAttribution(href);
  };
  return <a {...props} href={attributedHref}
    onClick={(event) => { refresh(event); onClick?.(event); }}
    onAuxClick={(event) => { refresh(event); onAuxClick?.(event); }}
    onPointerDown={(event) => { refresh(event); onPointerDown?.(event); }}
    onFocus={(event) => { refresh(event); onFocus?.(event); }}
  />;
}
