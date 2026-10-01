"use client";

import { useRef, useState } from "react";
import ManualShareLink from "@/components/ManualShareLink";
import { publicShareUrl } from "@/lib/shareUrl";

export default function FragranceShareButton({
  brand,
  name,
}: {
  brand: string;
  name: string;
}) {
  const [status, setStatus] = useState("");
  const [manualUrl, setManualUrl] = useState("");
  const shareRequestRef = useRef(0);

  const copyLink = async (url: string, request: number) => {
    if (request !== shareRequestRef.current) return;
    if (!navigator.clipboard?.writeText) {
      setManualUrl(url);
      setStatus("Automatisches Kopieren nicht möglich. Kopiere den Link unten.");
      return;
    }

    try {
      await navigator.clipboard.writeText(url);
      if (request !== shareRequestRef.current) return;
      setStatus("Link kopiert");
    } catch {
      if (request !== shareRequestRef.current) return;
      setManualUrl(url);
      setStatus("Automatisches Kopieren nicht möglich. Kopiere den Link unten.");
    }
  };

  const share = async () => {
    const request = ++shareRequestRef.current;
    const url = publicShareUrl(window.location.href);
    const title = `${brand} ${name} bei DUFYND`;

    setStatus("");
    setManualUrl("");

    if (typeof navigator.share === "function") {
      try {
        await navigator.share({
          title,
          text: `Entdecke ${brand} ${name} bei DUFYND.`,
          url,
        });
        if (request !== shareRequestRef.current) return;
        setStatus("Geteilt");
        return;
      } catch (error) {
        if (request !== shareRequestRef.current) return;
        if (
          error instanceof DOMException &&
          error.name === "AbortError"
        ) {
          return;
        }
      }
    }

    await copyLink(url, request);
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
      <ManualShareLink url={manualUrl} />
    </>
  );
}
