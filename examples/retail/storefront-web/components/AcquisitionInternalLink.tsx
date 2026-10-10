"use client";

import type { ComponentPropsWithoutRef } from "react";
import { useEffect, useState } from "react";

import {
  appendAcquisitionAttribution,
} from "@/lib/analytics";

type Props = Omit<ComponentPropsWithoutRef<"a">, "href"> & {
  href: string;
};

export default function AcquisitionInternalLink({
  href,
  ...props
}: Props) {
  const [attributedHref, setAttributedHref] = useState(href);

  useEffect(() => {
    setAttributedHref(appendAcquisitionAttribution(href));
  }, [href]);

  return <a {...props} href={attributedHref} />;
}
