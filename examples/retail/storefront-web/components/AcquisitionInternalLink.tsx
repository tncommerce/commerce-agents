"use client";

import type { ComponentPropsWithoutRef, SyntheticEvent } from "react";
import { useEffect, useState } from "react";

import {
  appendAcquisitionAttribution,
} from "@/lib/analytics";

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
    setAttributedHref(appendAcquisitionAttribution(href));
  }, [href]);

  // The session can settle after the mount effect. Refresh the actual anchor
  // before native navigation, including keyboard and open-in-new-tab gestures.
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
