"use client";

import { useState } from "react";
import { publicShareUrl } from "@/lib/shareUrl";

export default function FragranceShareButton({
  brand,
  name,
}: {
  brand: string;
  name: string;
}) {
  const [status, setStatus] = useState("");

  const copyLink = async (url: string) => {
    if (!navigator.clipboard?.writeText) {
      setStatus("Link bitte aus der Adresszeile kopieren");
      return;
    }

    try {
      await navigator.clipboard.writeText(url);
      setStatus("Link kopiert");
    } catch {
      setStatus("Link bitte aus der Adresszeile kopieren");
    }
  };

  const share = async () => {
    const url = publicShareUrl(window.location.href);
    const title = `${brand} ${name} bei DUFYND`;

    setStatus("");

    if (typeof navigator.share === "function") {
      try {
        await navigator.share({
          title,
          text: `Entdecke ${brand} ${name} bei DUFYND.`,
          url,
        });
        setStatus("Geteilt");
        return;
      } catch (error) {
        if (
          error instanceof DOMException &&
          error.name === "AbortError"
        ) {
          return;
        }
      }
    }

    await copyLink(url);
  };

  return (
    <>
      <button
        type="button"
        onClick={() => void share()}
        aria-label={`${brand} ${name} teilen`}
        className="rounded-lg border border-(--line) bg-(--surface) px-2.5 py-1.5 text-[11px] font-semibold text-(--accent-ink) transition hover:border-(--accent)"
      >
        {status === "Link kopiert" ? "Link kopiert ✓" : "Teilen ↗"}
      </button>
      <span role="status" aria-live="polite" className="sr-only">
        {status}
      </span>
    </>
  );
}
