"use client";

import { FormEvent, useMemo, useState } from "react";

import {
  trackAnalyticsEvent,
  trackCatalogSearch,
} from "@/lib/analytics";

type SearchableFragrance = {
  product_id: string;
  slug: string;
  brand: string;
  name: string;
};

function normalize(value: string): string {
  return value
    .normalize("NFKD")
    .replace(/[\u0300-\u036f]/g, "")
    .toLocaleLowerCase("de-DE")
    .replace(/ß/g, "ss")
    .replace(/[^a-z0-9]+/g, " ")
    .replace(/\s+/g, " ")
    .trim();
}

export default function SocialFragranceSearch({
  fragrances,
}: {
  fragrances: SearchableFragrance[];
}) {
  const [query, setQuery] = useState("");
  const normalizedQuery = normalize(query);

  const matches = useMemo(() => {
    if (!normalizedQuery) return [];

    return fragrances
      .filter((fragrance) =>
        normalize(`${fragrance.brand} ${fragrance.name}`).includes(
          normalizedQuery,
        ),
      )
      .slice(0, 5);
  }, [fragrances, normalizedQuery]);

  function recordSearch() {
    void trackCatalogSearch(query, matches.length);
  }

  function openFragrance(fragrance: SearchableFragrance, position: number) {
    recordSearch();
    void trackAnalyticsEvent("product_open", {
      product_id: fragrance.product_id,
      source: "social_start_direct_search",
      surface: "social_start_search",
      item_position: position,
    });
  }

  function submit(event: FormEvent<HTMLFormElement>) {
    if (!matches[0]) {
      recordSearch();
      return;
    }

    event.preventDefault();
    openFragrance(matches[0], 1);
    window.location.assign(`/duft/${matches[0].slug}`);
  }

  return (
    <form
      action="/duft"
      method="get"
      role="search"
      aria-label="DUFYND Social Duftsuche"
      className="relative min-w-0"
      onSubmit={submit}
    >
      <div className="flex min-w-0 flex-col gap-2 sm:flex-row">
        <label htmlFor="dufynd-social-search" className="sr-only">
          Duft oder Marke suchen
        </label>
        <input
          id="dufynd-social-search"
          name="q"
          type="search"
          maxLength={80}
          value={query}
          onChange={(event) => setQuery(event.target.value)}
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

      {normalizedQuery ? (
        <div
          className="absolute left-0 right-0 top-full z-30 mt-2 overflow-hidden rounded-2xl border border-(--line) bg-[#fffdf8]/95 p-1.5 shadow-[0_20px_44px_-26px_rgba(23,21,19,0.72)] backdrop-blur-xl"
          aria-live="polite"
          data-dufynd-social-live-results
        >
          {matches.length ? (
            matches.map((fragrance, index) => (
              <a
                key={fragrance.product_id}
                href={`/duft/${fragrance.slug}`}
                onClick={() => openFragrance(fragrance, index + 1)}
                className="flex items-center justify-between gap-3 rounded-xl px-3 py-2.5 transition hover:bg-(--well)"
              >
                <span className="min-w-0">
                  <span className="block truncate text-[9px] font-semibold uppercase tracking-[0.08em] text-(--ink-faint)">
                    {fragrance.brand}
                  </span>
                  <strong className="mt-0.5 block truncate text-[12px] font-semibold text-(--ink)">
                    {fragrance.name}
                  </strong>
                </span>
                <span
                  aria-hidden
                  className="shrink-0 text-[12px] font-semibold text-(--accent-ink)"
                >
                  →
                </span>
              </a>
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
