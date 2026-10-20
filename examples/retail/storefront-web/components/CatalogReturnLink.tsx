"use client";

import { useEffect, useState, type ComponentProps } from "react";
import AcquisitionInternalLink from "./AcquisitionInternalLink";
import { catalogContext, catalogReturnHref } from "@/lib/catalogJourney";

export default function CatalogReturnLink({
  contextLabel = "← Zurück zu deiner Auswahl",
  children,
  ...props
}: ComponentProps<typeof AcquisitionInternalLink> & { contextLabel?: string }) {
  const [context, setContext] = useState("");
  useEffect(() => {
    const readContext = () => setContext(catalogContext(new URLSearchParams(
      new URLSearchParams(window.location.search).get("catalog") || "",
    )));
    readContext();
    window.addEventListener("popstate", readContext);
    return () => window.removeEventListener("popstate", readContext);
  }, []);
  return (
    <AcquisitionInternalLink {...props} href={context ? catalogReturnHref(context) : props.href}>
      {context ? contextLabel : children}
    </AcquisitionInternalLink>
  );
}
