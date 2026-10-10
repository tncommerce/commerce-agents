"use client";

import { FormEvent, useMemo, useRef, useState } from "react";

import {
  fragranceSearchIdentity,
  matchesRequestedVariant,
  normalizeFragranceSearch as normalize,
} from "@/lib/fragranceSearchIdentity";

import AcquisitionInternalLink from "@/components/AcquisitionInternalLink";
import {
  appendAcquisitionAttribution,
  trackAnalyticsEvent,
  trackCatalogSearch,
} from "@/lib/analytics";

type SearchableFragrance = {
  product_id: string;
  slug: string;
  brand: string;
  name: string;
  concentration: string;
  volume_ml: number;
};

export default function SocialFragranceSearch({
  fragrances,
}: {
  fragrances: SearchableFragrance[];
}) {
  const [query, setQuery] = useState("");
  const [resultsOpen, setResultsOpen] = useState(false);
  const inputRef = useRef<HTMLInputElement>(null);
  const normalizedQuery = normalize(query);

  const matches = useMemo(() => {
    if (!normalizedQuery) return [];

    return fragrances
      .filter((fragrance) =>
        matchesRequestedVariant(fragrance, query) &&
        normalizedQuery.split(" ").every((token) => fragranceSearchIdentity(fragrance).includes(token)),
      )
      .slice(0, 5);
  }, [fragrances, normalizedQuery, query]);

  function recordSearch() {
    return trackCatalogSearch(query, matches.length);
  }

  function openFragrance(fragrance: SearchableFragrance, position: number) {
    recordSearch();
    return trackAnalyticsEvent("product_open", {
      product_id: fragrance.product_id,
      source: "social_start_direct_search",
      surface: "social_start_search",
      item_position: position,
    });
  }

  const navigatingRef = useRef(false);

  async function navigate(href: string, tracking: Promise<void>) {
    if (navigatingRef.current) return;
    navigatingRef.current = true;
    let timeout: ReturnType<typeof setTimeout> | undefined;
    try {
      // A static-host document navigation otherwise discards queued events.
      // Analytics outages must never trap the visitor on the search page.
      await Promise.race([
        tracking.catch(() => {}),
        new Promise<void>((resolve) => { timeout = setTimeout(resolve, 500); }),
      ]);
    } finally {
      clearTimeout(timeout);
      navigatingRef.current = false;
      window.location.assign(href);
    }
  }

  function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!matches[0]) {
      const tracking = recordSearch();
      const target = new URL(appendAcquisitionAttribution("/duft"), window.location.origin);
      target.searchParams.set("q", query);
      void navigate(target.toString(), tracking);
      return;
    }

    void navigate(appendAcquisitionAttribution(`/duft/${matches[0].slug}`), openFragrance(matches[0], 1));
  }

  return (
    <form
      action="/duft"
      method="get"
      role="search"
      aria-label="DUFYND Social Duftsuche"
      className="relative min-w-0"
      onSubmit={submit}
      onKeyDown={(event) => {
        if (event.key === "Escape" && resultsOpen && normalizedQuery) {
          event.preventDefault();
          inputRef.current?.focus();
          setResultsOpen(false);
        }
      }}
      onBlur={(event) => {
        if (!event.currentTarget.contains(event.relatedTarget)) setResultsOpen(false);
      }}
    >
      <div className="flex min-w-0 flex-col gap-2 sm:flex-row">
        <label htmlFor="dufynd-social-search" className="sr-only">
          Duft oder Marke suchen
        </label>
        <input
          id="dufynd-social-search"
          ref={inputRef}
          name="q"
          type="search"
          maxLength={80}
          value={query}
          onChange={(event) => {
            setQuery(event.target.value);
            setResultsOpen(true);
          }}
          onFocus={() => setResultsOpen(true)}
          placeholder="z. B. 1 Million, Naxos oder Libre"
          autoComplete="off"
          className="min-w-0 flex-1 rounded-xl border border-(--line) bg-[#fffdf8] px-3.5 py-2.5 text-[12.5px] text-(--ink) outline-none transition placeholder:text-(--ink-faint) focus:border-(--accent)"
        />
        <button
          type="submit"
          className="shrink-0 rounded-xl bg-(--ink) px-4 py-2.5 text-[12px] font-semibold text-white transition hover:opacity-90"
        >
          {matches.length ? "Direkt öffnen" : "Direkt suchen"}
        </button>
      </div>

      {normalizedQuery && resultsOpen ? (
        <div
          className="absolute left-0 right-0 top-full z-30 mt-2 overflow-hidden rounded-2xl border border-(--line) bg-[#fffdf8]/95 p-1.5 shadow-[0_20px_44px_-26px_rgba(23,21,19,0.72)] backdrop-blur-xl"
          aria-live="polite"
          data-dufynd-social-live-results
        >
          {matches.length ? (
            matches.map((fragrance, index) => (
              <AcquisitionInternalLink
                key={fragrance.product_id}
                href={`/duft/${fragrance.slug}`}
                onClick={(event) => {
                  const tracking = openFragrance(fragrance, index + 1);
                  if (event.button === 0 && !event.metaKey && !event.ctrlKey && !event.shiftKey && !event.altKey) {
                    event.preventDefault();
                    void navigate(appendAcquisitionAttribution(`/duft/${fragrance.slug}`), tracking);
                  }
                }}
                className="flex items-center justify-between gap-3 rounded-xl px-3 py-2.5 transition hover:bg-(--well)"
              >
                <span className="min-w-0">
                  <span className="block truncate text-[9px] font-semibold uppercase tracking-[0.08em] text-(--ink-faint)">
                    {fragrance.brand}
                  </span>
                  <strong className="mt-0.5 block truncate text-[12px] font-semibold text-(--ink)">
                    {fragrance.name}
                  </strong>
                  <span className="block text-[10px] text-(--ink-soft)">
                    {fragrance.concentration} · {fragrance.volume_ml} ml
                  </span>
                </span>
                <span
                  aria-hidden
                  className="shrink-0 text-[12px] font-semibold text-(--accent-ink)"
                >
                  →
                </span>
              </AcquisitionInternalLink>
            ))
          ) : (
            <div className="rounded-xl px-3 py-2.5 text-[11px] leading-5 text-(--ink-soft)">
              Kein direkter Treffer. Mit „Direkt suchen“ öffnest du die
              vollständige Katalogsuche.
            </div>
          )}
        </div>
      ) : null}
    </form>
  );
}
