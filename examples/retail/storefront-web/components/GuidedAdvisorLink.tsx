"use client";

import type { ReactNode } from "react";

import {
  advisorStartHref,
  GUIDED_START_STORAGE_KEY,
  type AdvisorStartKey,
} from "@/lib/advisorStarts";

export default function GuidedAdvisorLink({
  start,
  className,
  children,
}: {
  start: AdvisorStartKey;
  className?: string;
  children: ReactNode;
}) {
  return (
    <a
      href={advisorStartHref(start)}
      className={className}
      onClick={() => {
        try {
          window.sessionStorage.setItem(
            GUIDED_START_STORAGE_KEY,
            start,
          );
        } catch {
          // Falling back to the homepage is still a valid experience.
        }
      }}
    >
      {children}
    </a>
  );
}
