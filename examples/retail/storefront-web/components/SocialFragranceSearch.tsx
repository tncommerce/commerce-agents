"use client";

import { FormEvent, useMemo, useState } from "react";

type SearchableFragrance = {
  slug: string;
  brand: string;
  name: string;
};

function normalize(value: string): string {
  return value
    .normalize("NFD")
    .replace(/[\u0300-\u036f]/g, "")
    .toLocaleLowerCase("de-DE")
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

  function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();

    if (matches[0]) {
      window.location.assign(`/duft/${matches[0].slug}`);
      return;
    }

    const trimmed = query.trim();
    window.location.assign(
      trimmed
        ? `/duft?q=${encodeURIComponent(trimmed)}`
        : "/duft",
    );
  }

  return (
    <div className="dufynd-social-fragrance-search mt-5 max-w-xl">
      <div className="mb-2 flex items-center justify-between gap-3">
        <span className="text-[10px] font-semibold uppercase tracking-[0.12em] text-white/52">
          Du kennst den Duft schon?
        </span>
        <span className="text-[9.5px] text-white/34">
          Direkt öffnen
        </span>
      </div>

      <form
        onSubmit={submit}
        className="relative"
        role="search"
      >
        <div className="flex items-center gap-2 rounded-2xl border border-white/12 bg-black/20 p-1.5 shadow-[0_14px_34px_-24px_rgba(0,0,0,0.9)] backdrop-blur-md">
          <input
            type="search"
            value={query}
            onChange={(event) => setQuery(event.target.value)}
            aria-label="Duft oder Marke direkt öffnen"
            placeholder="z. B. 1 Million, Naxos, Libre …"
            autoComplete="off"
            className="min-w-0 flex-1 bg-transparent px-3 py-2 text-[12.5px] text-white outline-none placeholder:text-white/30"
          />
          <button
            type="submit"
            className="shrink-0 rounded-xl bg-[#d9bd82] px-3.5 py-2 text-[11px] font-semibold text-[#241b0e] transition hover:bg-[#e4cb98]"
          >
            Öffnen
          </button>
        </div>

        {normalizedQuery ? (
          <div
            className="dufynd-social-fragrance-results mt-2 overflow-hidden rounded-2xl border border-white/10 bg-[#0b0c0e]/92 p-1.5 shadow-[0_22px_48px_-26px_rgba(0,0,0,0.92)] backdrop-blur-xl"
            aria-live="polite"
          >
            {matches.length ? (
              matches.map((fragrance) => (
                <a
                  key={fragrance.slug}
                  href={`/duft/${fragrance.slug}`}
                  className="flex items-center justify-between gap-3 rounded-xl px-3 py-2.5 transition hover:bg-white/[0.06]"
                >
                  <span className="min-w-0">
                    <span className="block truncate text-[9px] font-semibold uppercase tracking-[0.08em] text-white/38">
                      {fragrance.brand}
                    </span>
                    <strong className="mt-0.5 block truncate text-[12px] font-semibold text-white/86">
                      {fragrance.name}
                    </strong>
                  </span>
                  <span
                    aria-hidden
                    className="shrink-0 text-[12px] text-[#d9bd82]"
                  >
                    →
                  </span>
                </a>
              ))
            ) : (
              <a
                href={`/duft?q=${encodeURIComponent(query.trim())}`}
                className="flex items-center justify-between gap-3 rounded-xl px-3 py-2.5 text-[11px] text-white/58 transition hover:bg-white/[0.06]"
              >
                <span>Im gesamten Katalog nach „{query.trim()}“ suchen</span>
                <span aria-hidden className="text-[#d9bd82]">
                  →
                </span>
              </a>
            )}
          </div>
        ) : null}
      </form>
    </div>
  );
}
