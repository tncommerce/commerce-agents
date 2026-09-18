"use client";

import { useEffect, useMemo, useState } from "react";

import { trackAnalyticsEvent } from "@/lib/analytics";
import type { StaticFragrance } from "@/lib/fragranceCatalog";

type AudienceFilter = "all" | "men" | "unisex" | "women";
type ProfileFilter =
  | "all"
  | "freshness"
  | "sweetness"
  | "woodiness"
  | "spiciness";
type SortMode =
  | "popular"
  | "rating"
  | "performance"
  | "brand";

const PAGE_SIZE = 36;

const AUDIENCE_OPTIONS: {
  value: AudienceFilter;
  label: string;
}[] = [
  { value: "all", label: "Alle" },
  { value: "men", label: "Herren" },
  { value: "unisex", label: "Unisex" },
  { value: "women", label: "Damen" },
];

const PROFILE_OPTIONS: {
  value: ProfileFilter;
  label: string;
}[] = [
  { value: "all", label: "Alle Profile" },
  { value: "freshness", label: "Frisch" },
  { value: "sweetness", label: "Süß" },
  { value: "woodiness", label: "Holzig" },
  { value: "spiciness", label: "Würzig" },
];

const SORT_OPTIONS: {
  value: SortMode;
  label: string;
}[] = [
  { value: "popular", label: "Beliebtheit" },
  { value: "rating", label: "Bewertung" },
  { value: "performance", label: "Performance" },
  { value: "brand", label: "Marke A–Z" },
];

const ACCORD_LABELS: Record<string, string> = {
  fresh: "Frisch",
  citrus: "Zitrisch",
  aquatic: "Aquatisch",
  green: "Grün",
  spicy: "Würzig",
  sweet: "Süß",
  synthetic: "Synthetisch",
  fruity: "Fruchtig",
  woody: "Holzig",
  smoky: "Rauchig",
  powdery: "Pudrig",
  floral: "Blumig",
  creamy: "Cremig",
  gourmand: "Gourmand",
  oriental: "Orientalisch",
  aromatic: "Aromatisch",
  leathery: "Ledrig",
  resinous: "Harzig",
};

function optionLabel<T extends string>(
  options: { value: T; label: string }[],
  value: T,
): string {
  return options.find((option) => option.value === value)?.label || value;
}

function ratingLabel(
  fragrance: StaticFragrance,
): string | null {
  if (fragrance.community.rating_10 == null) return null;

  return `${fragrance.community.rating_10.toLocaleString(
    "de-DE",
    {
      minimumFractionDigits: 1,
      maximumFractionDigits: 1,
    },
  )}/10`;
}

function accordLabel(value: string): string {
  return ACCORD_LABELS[value.toLowerCase()] || value;
}

function performanceScore(
  fragrance: StaticFragrance,
): number {
  const values = [
    fragrance.community.longevity_10,
    fragrance.community.projection_10,
  ].filter(
    (value): value is number => value != null,
  );

  if (!values.length) return 0;

  return (
    values.reduce((sum, value) => sum + value, 0) /
    values.length
  );
}

function normalize(value: string): string {
  return value
    .normalize("NFKD")
    .replace(/[\u0300-\u036f]/g, "")
    .toLowerCase()
    .trim();
}

function matchesSearch(
  fragrance: StaticFragrance,
  search: string,
): boolean {
  const needle = normalize(search);

  if (!needle) return true;

  const haystack = normalize(
    [
      fragrance.brand,
      fragrance.name,
      fragrance.concentration,
      ...fragrance.accords,
    ].join(" "),
  );

  return haystack.includes(needle);
}

function matchesProfile(
  fragrance: StaticFragrance,
  profile: ProfileFilter,
): boolean {
  if (profile === "all") return true;

  const value = fragrance.scores[profile];

  return value != null && value >= 7;
}

export default function FragranceCatalogBrowser({
  fragrances,
}: {
  fragrances: StaticFragrance[];
}) {
  const [search, setSearch] = useState("");
  const [audience, setAudience] =
    useState<AudienceFilter>("all");
  const [profile, setProfile] =
    useState<ProfileFilter>("all");
  const [brand, setBrand] = useState("all");
  const [minimumRating, setMinimumRating] =
    useState("0");
  const [sort, setSort] =
    useState<SortMode>("popular");
  const [mobileFiltersOpen, setMobileFiltersOpen] =
    useState(false);
  const [visibleCount, setVisibleCount] =
    useState(PAGE_SIZE);

  const brands = useMemo(
    () =>
      Array.from(
        new Set(
          fragrances
            .map((fragrance) => fragrance.brand)
            .filter(Boolean),
        ),
      ).sort((a, b) => a.localeCompare(b, "de")),
    [fragrances],
  );

  const filtered = useMemo(() => {
    const minimum = Number(minimumRating);

    return fragrances
      .filter((fragrance) =>
        matchesSearch(fragrance, search),
      )
      .filter(
        (fragrance) =>
          audience === "all" ||
          fragrance.target_groups.includes(audience),
      )
      .filter(
        (fragrance) =>
          brand === "all" ||
          fragrance.brand === brand,
      )
      .filter((fragrance) =>
        matchesProfile(fragrance, profile),
      )
      .filter(
        (fragrance) =>
          !minimum ||
          (fragrance.community.rating_10 ?? 0) >=
            minimum,
      )
      .sort((a, b) => {
        if (sort === "rating") {
          return (
            (b.community.rating_10 ?? 0) -
              (a.community.rating_10 ?? 0) ||
            b.community.rating_count -
              a.community.rating_count
          );
        }

        if (sort === "performance") {
          return (
            performanceScore(b) -
              performanceScore(a) ||
            b.community.rating_count -
              a.community.rating_count
          );
        }

        if (sort === "brand") {
          return (
            a.brand.localeCompare(b.brand, "de") ||
            a.name.localeCompare(b.name, "de")
          );
        }

        return (
          b.community.rating_count -
            a.community.rating_count ||
          (b.community.rating_10 ?? 0) -
            (a.community.rating_10 ?? 0)
        );
      });
  }, [
    audience,
    brand,
    fragrances,
    minimumRating,
    profile,
    search,
    sort,
  ]);

  useEffect(() => {
    setVisibleCount(PAGE_SIZE);
  }, [
    audience,
    brand,
    minimumRating,
    profile,
    search,
    sort,
  ]);

  const activeFilterCount =
    Number(Boolean(search.trim())) +
    Number(audience !== "all") +
    Number(profile !== "all") +
    Number(brand !== "all") +
    Number(minimumRating !== "0");

  const hasActiveFilters = activeFilterCount > 0;
  const hasChanges =
    hasActiveFilters || sort !== "popular";

  const visibleFragrances = filtered.slice(
    0,
    visibleCount,
  );
  const remainingCount =
    filtered.length - visibleFragrances.length;

  const resetFilters = () => {
    setSearch("");
    setAudience("all");
    setProfile("all");
    setBrand("all");
    setMinimumRating("0");
    setSort("popular");
  };

  return (
    <>
      <section
        className="mt-7 rounded-2xl border border-(--line) bg-(--card) p-4 shadow-(--shadow-sm) sm:p-5"
        aria-label="Duftkatalog filtern"
      >
        <div className="grid gap-3 md:grid-cols-[1fr_auto] md:items-end">
          <label className="block">
            <span className="mb-1.5 block text-[11px] font-semibold uppercase tracking-[0.07em] text-(--ink-soft)">
              Duft oder Marke
            </span>
            <input
              type="search"
              value={search}
              onChange={(event) =>
                setSearch(event.target.value)
              }
              placeholder="z. B. Prada, Naxos, Imagination …"
              className="h-11 w-full rounded-xl border border-(--line) bg-(--surface) px-3 text-[13px] text-(--ink) outline-none transition placeholder:text-(--ink-soft)/70 focus:border-(--accent)"
            />
          </label>

          <button
            type="button"
            onClick={() =>
              setMobileFiltersOpen((open) => !open)
            }
            className="flex h-11 items-center justify-between rounded-xl border border-(--line) bg-(--surface) px-3 text-[12px] font-semibold text-(--ink) md:hidden"
            aria-expanded={mobileFiltersOpen}
            aria-controls="catalog-filter-panel"
          >
            <span>
              Filter
              {activeFilterCount
                ? ` (${activeFilterCount})`
                : ""}
            </span>
            <span aria-hidden="true">
              {mobileFiltersOpen ? "−" : "+"}
            </span>
          </button>
        </div>

        <div
          id="catalog-filter-panel"
          className={`${mobileFiltersOpen ? "block" : "hidden"} md:block`}
        >
          <div className="mt-3 grid gap-3 sm:grid-cols-2">
            <label className="block">
              <span className="mb-1.5 block text-[11px] font-semibold uppercase tracking-[0.07em] text-(--ink-soft)">
                Marke
              </span>
              <select
                value={brand}
                onChange={(event) =>
                  setBrand(event.target.value)
                }
                className="h-11 w-full rounded-xl border border-(--line) bg-(--surface) px-3 text-[13px] text-(--ink) outline-none focus:border-(--accent)"
              >
                <option value="all">Alle Marken</option>
                {brands.map((brandName) => (
                  <option
                    key={brandName}
                    value={brandName}
                  >
                    {brandName}
                  </option>
                ))}
              </select>
            </label>

            <label className="block">
              <span className="mb-1.5 block text-[11px] font-semibold uppercase tracking-[0.07em] text-(--ink-soft)">
                Sortierung
              </span>
              <select
                value={sort}
                onChange={(event) =>
                  setSort(
                    event.target.value as SortMode,
                  )
                }
                className="h-11 w-full rounded-xl border border-(--line) bg-(--surface) px-3 text-[13px] text-(--ink) outline-none focus:border-(--accent)"
              >
                {SORT_OPTIONS.map((option) => (
                  <option
                    key={option.value}
                    value={option.value}
                  >
                    {option.label}
                  </option>
                ))}
              </select>
            </label>
          </div>

          <div className="mt-4 grid gap-4 lg:grid-cols-[1fr_1fr_auto]">
            <div>
              <div className="mb-2 text-[11px] font-semibold uppercase tracking-[0.07em] text-(--ink-soft)">
                Zielgruppe
              </div>
              <div className="flex flex-wrap gap-2">
                {AUDIENCE_OPTIONS.map((option) => {
                  const active =
                    audience === option.value;

                  return (
                    <button
                      key={option.value}
                      type="button"
                      onClick={() =>
                        setAudience(option.value)
                      }
                      className={`rounded-full border px-3 py-1.5 text-[12px] font-medium transition ${
                        active
                          ? "border-(--ink) bg-(--ink) text-(--surface)"
                          : "border-(--line) bg-(--surface) text-(--ink-soft) hover:border-(--ink)"
                      }`}
                      aria-pressed={active}
                    >
                      {option.label}
                    </button>
                  );
                })}
              </div>
            </div>

            <div>
              <div className="mb-2 text-[11px] font-semibold uppercase tracking-[0.07em] text-(--ink-soft)">
                Duftprofil
              </div>
              <div className="flex flex-wrap gap-2">
                {PROFILE_OPTIONS.map((option) => {
                  const active =
                    profile === option.value;

                  return (
                    <button
                      key={option.value}
                      type="button"
                      onClick={() =>
                        setProfile(option.value)
                      }
                      className={`rounded-full border px-3 py-1.5 text-[12px] font-medium transition ${
                        active
                          ? "border-(--ink) bg-(--ink) text-(--surface)"
                          : "border-(--line) bg-(--surface) text-(--ink-soft) hover:border-(--ink)"
                      }`}
                      aria-pressed={active}
                    >
                      {option.label}
                    </button>
                  );
                })}
              </div>
            </div>

            <label className="block min-w-[150px]">
              <span className="mb-2 block text-[11px] font-semibold uppercase tracking-[0.07em] text-(--ink-soft)">
                Bewertung
              </span>
              <select
                value={minimumRating}
                onChange={(event) =>
                  setMinimumRating(event.target.value)
                }
                className="h-9 w-full rounded-xl border border-(--line) bg-(--surface) px-3 text-[12px] text-(--ink) outline-none focus:border-(--accent)"
              >
                <option value="0">Alle</option>
                <option value="8">ab 8,0/10</option>
                <option value="8.3">ab 8,3/10</option>
                <option value="8.5">ab 8,5/10</option>
              </select>
            </label>
          </div>
        </div>

        {hasChanges ? (
          <div className="mt-4 flex gap-2 overflow-x-auto border-t border-(--line) pt-3 pb-1">
            {search.trim() ? (
              <button
                type="button"
                onClick={() => setSearch("")}
                className="shrink-0 rounded-full border border-(--line) bg-(--surface) px-3 py-1.5 text-[11px] font-medium text-(--ink)"
                aria-label="Suchfilter entfernen"
              >
                Suche: {search.trim()} ×
              </button>
            ) : null}

            {audience !== "all" ? (
              <button
                type="button"
                onClick={() => setAudience("all")}
                className="shrink-0 rounded-full border border-(--line) bg-(--surface) px-3 py-1.5 text-[11px] font-medium text-(--ink)"
                aria-label="Zielgruppenfilter entfernen"
              >
                {optionLabel(
                  AUDIENCE_OPTIONS,
                  audience,
                )}{" "}
                ×
              </button>
            ) : null}

            {profile !== "all" ? (
              <button
                type="button"
                onClick={() => setProfile("all")}
                className="shrink-0 rounded-full border border-(--line) bg-(--surface) px-3 py-1.5 text-[11px] font-medium text-(--ink)"
                aria-label="Duftprofilfilter entfernen"
              >
                {optionLabel(
                  PROFILE_OPTIONS,
                  profile,
                )}{" "}
                ×
              </button>
            ) : null}

            {brand !== "all" ? (
              <button
                type="button"
                onClick={() => setBrand("all")}
                className="shrink-0 rounded-full border border-(--line) bg-(--surface) px-3 py-1.5 text-[11px] font-medium text-(--ink)"
                aria-label="Markenfilter entfernen"
              >
                {brand} ×
              </button>
            ) : null}

            {minimumRating !== "0" ? (
              <button
                type="button"
                onClick={() => setMinimumRating("0")}
                className="shrink-0 rounded-full border border-(--line) bg-(--surface) px-3 py-1.5 text-[11px] font-medium text-(--ink)"
                aria-label="Bewertungsfilter entfernen"
              >
                ab {minimumRating.replace(".", ",")}/10 ×
              </button>
            ) : null}

            {sort !== "popular" ? (
              <button
                type="button"
                onClick={() => setSort("popular")}
                className="shrink-0 rounded-full border border-(--line) bg-(--surface) px-3 py-1.5 text-[11px] font-medium text-(--ink)"
                aria-label="Sortierung zurücksetzen"
              >
                Sortiert: {optionLabel(SORT_OPTIONS, sort)} ×
              </button>
            ) : null}
          </div>
        ) : null}

        <div className="mt-4 flex flex-wrap items-center justify-between gap-3 border-t border-(--line) pt-3">
          <div
            className="text-[12px] text-(--ink-soft)"
            aria-live="polite"
          >
            <span className="font-semibold text-(--ink)">
              {filtered.length}
            </span>{" "}
            von {fragrances.length} Düften
            {remainingCount > 0 ? (
              <span className="hidden sm:inline">
                {" "}
                · {visibleFragrances.length} angezeigt
              </span>
            ) : null}
          </div>

          {hasChanges ? (
            <button
              type="button"
              onClick={resetFilters}
              className="text-[12px] font-semibold text-(--accent-ink) hover:underline"
            >
              Filter zurücksetzen
            </button>
          ) : null}
        </div>
      </section>

      {filtered.length ? (
        <>
          <section className="mt-5 grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
            {visibleFragrances.map((fragrance) => (
              <a
                key={fragrance.product_id}
                href={`/duft/${fragrance.slug}`}
                onClick={() =>
                  void trackAnalyticsEvent(
                    "product_open",
                    {
                      product_id:
                        fragrance.product_id,
                      source: "catalog_grid",
                    },
                  )
                }
                className="group overflow-hidden rounded-2xl border border-(--line) bg-(--card) shadow-(--shadow-sm) transition hover:-translate-y-0.5 hover:shadow-md"
              >
                <div className="flex h-52 items-center justify-center bg-white p-4">
                  {fragrance.image_url ? (
                    // eslint-disable-next-line @next/next/no-img-element
                    <img
                      src={fragrance.image_url}
                      alt={`${fragrance.brand} ${fragrance.name}`}
                      loading="lazy"
                      decoding="async"
                      className="h-full w-full object-contain transition duration-200 group-hover:scale-[1.02]"
                    />
                  ) : (
                    <div className="text-[12px] font-semibold tracking-[0.16em] text-(--ink-soft)">
                      SCENTAI
                    </div>
                  )}
                </div>

                <div className="p-4">
                  <div className="text-[10.5px] font-medium uppercase tracking-[0.08em] text-(--ink-soft)">
                    {fragrance.brand}
                  </div>
                  <h2 className="mt-1 text-[16px] font-semibold leading-5">
                    {fragrance.name}
                  </h2>

                  <div className="mt-2 flex flex-wrap gap-1.5 text-[10.5px] text-(--ink-soft)">
                    <span>
                      {fragrance.concentration}
                    </span>
                    <span>·</span>
                    <span>
                      {fragrance.volume_ml} ml
                    </span>
                    {ratingLabel(fragrance) ? (
                      <>
                        <span>·</span>
                        <span className="font-semibold text-(--ink)">
                          {ratingLabel(fragrance)}
                        </span>
                      </>
                    ) : null}
                  </div>

                  <div className="mt-3 flex flex-wrap gap-1.5">
                    {fragrance.accords
                      .slice(0, 3)
                      .map((accord) => (
                        <span
                          key={accord}
                          className="rounded-full bg-(--well) px-2 py-1 text-[10.5px] text-(--ink-soft)"
                        >
                          {accordLabel(accord)}
                        </span>
                      ))}
                  </div>

                  <div className="mt-4 border-t border-(--line) pt-3 text-[11px] font-semibold text-(--accent-ink)">
                    Duftprofil & Angebote ansehen →
                  </div>
                </div>
              </a>
            ))}
          </section>

          {remainingCount > 0 ? (
            <div className="mt-6 flex justify-center">
              <button
                type="button"
                onClick={() =>
                  setVisibleCount((count) =>
                    count + PAGE_SIZE,
                  )
                }
                className="rounded-xl border border-(--line) bg-(--card) px-5 py-2.5 text-[12px] font-semibold text-(--ink) shadow-(--shadow-sm) transition hover:border-(--ink)"
              >
                Weitere{" "}
                {Math.min(PAGE_SIZE, remainingCount)}{" "}
                Düfte anzeigen
              </button>
            </div>
          ) : null}
        </>
      ) : (
        <section className="mt-5 rounded-2xl border border-dashed border-(--line) bg-(--card) px-5 py-10 text-center">
          <h2 className="text-[16px] font-semibold text-(--ink)">
            Keine passenden Düfte gefunden
          </h2>
          <p className="mx-auto mt-2 max-w-md text-[13px] leading-5 text-(--ink-soft)">
            Ändere einen Filter oder setze die Auswahl
            zurück. Der SCENTAI Advisor kann auch nach
            mehreren Kriterien gleichzeitig suchen.
          </p>
          <div className="mt-4 flex flex-wrap justify-center gap-2">
            <button
              type="button"
              onClick={resetFilters}
              className="rounded-xl border border-(--line) bg-(--surface) px-4 py-2 text-[12px] font-semibold text-(--ink)"
            >
              Filter zurücksetzen
            </button>
            <a
              href="/"
              className="rounded-xl bg-(--ink) px-4 py-2 text-[12px] font-semibold text-(--surface)"
            >
              Advisor öffnen
            </a>
          </div>
        </section>
      )}
    </>
  );
}
