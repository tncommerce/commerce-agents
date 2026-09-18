"use client";

import { useEffect } from "react";

import LegalFooter from "@/components/LegalFooter";

export default function ErrorPage({
  error,
  reset,
}: {
  error: Error & { digest?: string };
  reset: () => void;
}) {
  useEffect(() => {
    // Keep the failure visible to hosting logs without exposing details to users.
    console.error("SCENTAI route error", error);
  }, [error]);

  return (
    <main className="min-h-screen bg-(--ground) px-4 py-12 text-(--ink) sm:px-6">
      <div className="mx-auto max-w-xl">
        <section className="rounded-3xl border border-(--line) bg-(--card) p-6 shadow-(--shadow-sm) sm:p-8">
          <div className="text-[11px] font-semibold uppercase tracking-[0.12em] text-(--ink-soft)">
            SCENTAI
          </div>
          <h1 className="mt-2 text-3xl font-semibold tracking-[-0.03em]">
            Diese Ansicht konnte gerade nicht geladen werden.
          </h1>
          <p className="mt-3 text-[14px] leading-6 text-(--ink-soft)">
            Deine Anfrage ist nicht verloren. Versuche die Ansicht erneut oder nutze den Duftkatalog.
          </p>
          <div className="mt-6 flex flex-wrap gap-2">
            <button
              type="button"
              onClick={reset}
              className="rounded-xl bg-(--accent) px-4 py-2.5 text-[13px] font-semibold text-white"
            >
              Erneut versuchen
            </button>
            <a
              href="/duft"
              className="rounded-xl border border-(--line) bg-(--card) px-4 py-2.5 text-[13px] font-semibold text-(--ink)"
            >
              Duftkatalog öffnen
            </a>
          </div>
        </section>
        <LegalFooter />
      </div>
    </main>
  );
}
