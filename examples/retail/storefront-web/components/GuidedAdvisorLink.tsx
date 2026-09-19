"use client";

import type { ReactNode } from "react";

import {
  advisorStartHref,
  GUIDED_PROMPT_STORAGE_KEY,
  GUIDED_START_STORAGE_KEY,
  normalizeGuidedPrompt,
  type AdvisorStartKey,
} from "@/lib/advisorStarts";

export default function GuidedAdvisorLink({
  start,
  className,
  children,
  prompt,
}: {
  start: AdvisorStartKey;
  className?: string;
  children: ReactNode;
  prompt?: string;
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

          const guidedPrompt = normalizeGuidedPrompt(
            prompt || null,
          );
          if (guidedPrompt) {
            window.sessionStorage.setItem(
              GUIDED_PROMPT_STORAGE_KEY,
              guidedPrompt,
            );
          } else {
            window.sessionStorage.removeItem(
              GUIDED_PROMPT_STORAGE_KEY,
            );
          }
        } catch {
          // Falling back to the homepage is still a valid experience.
        }
      }}
    >
      {children}
    </a>
  );
}
