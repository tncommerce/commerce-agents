"use client";

import { useEffect, useMemo, useRef, useState } from "react";

import FragranceSaveControls from "@/components/FragranceSaveControls";
import FragranceVisual from "@/components/FragranceVisual";
import { accordLabel } from "@/lib/accordLabels";
import {
  safeCatalogSearchTerm,
  trackAnalyticsEvent,
  trackCatalogSearch,
} from "@/lib/analytics";
import {
  isVerifiedProductTruthVisual,
  type StaticFragrance,
} from "@/lib/fragranceCatalog";
import { noteLabel } from "@/lib/noteLabels";
import { targetLabel } from "@/lib/targetLabels";

type AudienceFilter = "all" | "men" | "unisex" | "women";
type ProfileFilter =
  | "all"
  | "freshness"
  | "sweetness"
  | "woodiness"
  | "spiciness";

type DiscoveryProfile = Exclude<ProfileFilter, "all">;
type SortMode =
  | "popular"
  | "profile"
  | "rating"
  | "performance"
  | "brand";

const PAGE_SIZE = 12;

const AUDIENCE_OPTIONS: {
  value: AudienceFilter;
  label: string;
}[] = [
  { value: "all", label: "Alle" },
  { value: "men", label: targetLabel("men") },
  { value: "unisex", label: targetLabel("unisex") },
  { value: "women", label: targetLabel("women") },
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

const PROFILE_DISCOVERY: {
  value: DiscoveryProfile;
  label: string;
  mood: string;
  notes: string;
}[] = [
  {
    value: "freshness",
    label: "Frisch",
    mood: "Klar & energiegeladen",
    notes: "Zitrisch · aromatisch · luftig",
  },
  {
    value: "sweetness",
    label: "Süß",
    mood: "Warm & einnehmend",
    notes: "Vanille · gourmand · cremig",
  },
  {
    value: "woodiness",
    label: "Holzig",
    mood: "Trocken & souverän",
    notes: "Hölzer · Vetiver · erdig",
  },
  {
    value: "spiciness",
    label: "Würzig",
    mood: "Markant & intensiv",
    notes: "Gewürze · Amber · warm",
  },
];

const SORT_OPTIONS: {
  value: SortMode;
  label: string;
}[] = [
  { value: "popular", label: "Community-Aktivität" },
  { value: "profile", label: "Passend zum Duftprofil" },
  { value: "rating", label: "Bewertung" },
  { value: "performance", label: "Haltbarkeit & Ausstrahlung" },
  { value: "brand", label: "Marke A–Z" },
];

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

  const rating = `${fragrance.community.rating_10.toLocaleString(
    "de-DE",
    {
      minimumFractionDigits: 1,
      maximumFractionDigits: 1,
    },
  )}/10`;

  return fragrance.community.provisional
    ? `${rating} · vorläufig`
    : rating;
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
    .replace(/ß/g, "ss")
    .replace(/[^a-z0-9]+/g, " ")
    .replace(/\s+/g, " ")
    .trim();
}

const TARGET_SEARCH_TERMS: Record<string, string[]> = {
  men: ["men", "male", "mann", "maenner", "herren"],
  women: ["women", "female", "frau", "frauen", "damen"],
  unisex: ["unisex"],
};

const PROFILE_SEARCH_TERMS: Record<
  Exclude<ProfileFilter, "all">,
  string[]
> = {
  freshness: ["freshness", "fresh", "frisch"],
  sweetness: ["sweetness", "sweet", "suess", "suss"],
  woodiness: ["woodiness", "woody", "wood", "holzig"],
  spiciness: ["spiciness", "spicy", "spice", "wuerzig", "wurzig"],
};

function searchTokens(search: string): string[] {
  return normalize(search)
    .split(/\s+/)
    .filter(Boolean);
}

function searchDocument(
  fragrance: StaticFragrance,
): string {
  const targetTerms = fragrance.target_groups.flatMap(
    (target) =>
      TARGET_SEARCH_TERMS[target.toLowerCase()] || [target],
  );

  const profileTerms = (
    Object.keys(PROFILE_SEARCH_TERMS) as Exclude<
      ProfileFilter,
      "all"
    >[]
  ).flatMap((profile) =>
    (fragrance.scores[profile] ?? 0) >= 7
      ? PROFILE_SEARCH_TERMS[profile]
      : [],
  );

  const accordTerms = fragrance.accords.flatMap(
    (accord) => [
      accord,
      accordLabel(accord),
    ],
  );

  return normalize(
    [
      fragrance.brand,
      fragrance.name,
      fragrance.title,
      fragrance.concentration,
      ...targetTerms,
      ...profileTerms,
      ...accordTerms,
      ...fragrance.notes.top,
      ...fragrance.notes.heart,
      ...fragrance.notes.base,
      ...fragrance.notes.key,
      ...fragrance.notes.supporting,
      ...[
        ...fragrance.notes.top,
        ...fragrance.notes.heart,
        ...fragrance.notes.base,
        ...fragrance.notes.key,
        ...fragrance.notes.supporting,
      ].map(noteLabel),
    ].join(" "),
  );
}

function searchScore(
  fragrance: StaticFragrance,
  search: string,
): number {
  const tokens = searchTokens(search);

  if (!tokens.length) return 0;

  const document = searchDocument(fragrance);

  if (!tokens.every((token) => document.includes(token))) {
    return -1;
  }

  const brand = normalize(fragrance.brand);
  const name = normalize(fragrance.name);
  const title = normalize(fragrance.title);
  const phrase = normalize(search);

  let score = 0;

  if (brand === phrase || name === phrase) score += 30;
  if (name.startsWith(phrase)) score += 16;
  if (brand.startsWith(phrase)) score += 14;
  if (title.includes(phrase)) score += 10;

  for (const token of tokens) {
    if (name.split(/\s+/).some((word) => word.startsWith(token))) {
      score += 7;
    }
    if (brand.split(/\s+/).some((word) => word.startsWith(token))) {
      score += 6;
    }
    if (
      fragrance.accords.some((accord) =>
        normalize(
          `${accord} ${accordLabel(accord)}`,
        ).includes(token),
      )
    ) {
      score += 3;
    }
    if (
      fragrance.target_groups.some((target) =>
        normalize(
          (
            TARGET_SEARCH_TERMS[target.toLowerCase()] ||
            [target]
          ).join(" "),
        ).includes(token),
      )
    ) {
      score += 3;
    }
  }

  return score;
}

function matchesSearch(
  fragrance: StaticFragrance,
  search: string,
): boolean {
  return searchScore(fragrance, search) >= 0;
}

function relaxedSearchQuery(search: string): string | null {
  const tokens = search.trim().split(/\s+/).filter(Boolean);

  if (tokens.length <= 1) return null;

  return tokens.slice(0, -1).join(" ");
}

function matchesProfile(
  fragrance: StaticFragrance,
  profile: ProfileFilter,
): boolean {
  if (profile === "all") return true;

  const value = fragrance.scores[profile];

  return value != null && value >= 7;
}

const SCENT_DNA_PROFILES: {
  key: DiscoveryProfile;
  label: string;
}[] = [
  { key: "freshness", label: "Frisch" },
  { key: "sweetness", label: "Süß" },
  { key: "woodiness", label: "Holzig" },
  { key: "spiciness", label: "Würzig" },
];

function scentDnaScore(
  fragrance: StaticFragrance,
  profile: DiscoveryProfile,
): number {
  return Math.max(
    0,
    Math.min(10, fragrance.scores[profile] ?? 0),
  );
}

function catalogLink({
  search,
  audience,
  profile,
  brand,
  minimumRating,
  sort,
}: {
  search: string;
  audience: AudienceFilter;
  profile: ProfileFilter;
  brand: string;
  minimumRating: string;
  sort: SortMode;
}): URL {
  const url = new URL(window.location.href);
  const setFilter = (key: string, value: string, defaultValue: string) => {
    if (value !== defaultValue) url.searchParams.set(key, value);
    else url.searchParams.delete(key);
  };

  setFilter("q", search.trim().slice(0, 80), "");
  setFilter("profil", profile, "all");
  setFilter("zielgruppe", audience, "all");
  setFilter("marke", brand, "all");
  setFilter("bewertung", minimumRating, "0");
  setFilter("sort", sort, "popular");
  return url;
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
  const [urlReady, setUrlReady] = useState(false);
  const [copyStatus, setCopyStatus] = useState("");
  const [compareSelection, setCompareSelection] = useState<string[]>([]);
  const lastTrackedSearchRef = useRef("");
  const initialSearchAppliedRef = useRef(false);
  const resultsRef = useRef<HTMLHeadingElement>(null);
  const jumpToResultsRef = useRef(false);

  const selectProfile = (
    nextProfile: ProfileFilter,
    jumpToResults = false,
  ) => {
    jumpToResultsRef.current = jumpToResults;
    setProfile(nextProfile);
    if (nextProfile === "all") {
      if (sort === "profile") setSort("popular");
      return;
    }

    setSort("profile");
  };

  useEffect(() => {
    if (!jumpToResultsRef.current || profile === "all") return;
    jumpToResultsRef.current = false;
    resultsRef.current?.focus({ preventScroll: true });
    resultsRef.current?.scrollIntoView({
      behavior: window.matchMedia("(prefers-reduced-motion: reduce)").matches
        ? "auto"
        : "smooth",
      block: "start",
    });
  }, [profile]);

  useEffect(() => {
    if (initialSearchAppliedRef.current) return;
    initialSearchAppliedRef.current = true;

    const params = new URLSearchParams(window.location.search);
    const initialSearch = params.get("q")?.trim();
    const initialProfile = params.get("profil");
    const initialAudience = AUDIENCE_OPTIONS.find(
      (option) => option.value === params.get("zielgruppe") && option.value !== "all",
    );
    const initialBrand = params.get("marke");
    const initialRating = params.get("bewertung");
    const initialSort = SORT_OPTIONS.find(
      (option) => option.value === params.get("sort"),
    );

    if (initialSearch) {
      setSearch(initialSearch.slice(0, 80));
    }

    const matchedProfile = PROFILE_DISCOVERY.find(
      (card) => card.value === initialProfile,
    );
    if (matchedProfile) {
      setProfile(matchedProfile.value);
      setSort("profile");
    }
    if (initialAudience) setAudience(initialAudience.value);
    if (initialBrand && fragrances.some((item) => item.brand === initialBrand)) {
      setBrand(initialBrand);
    }
    if (initialRating && ["8", "8.3", "8.5"].includes(initialRating)) {
      setMinimumRating(initialRating);
    }
    if (initialSort && (initialSort.value !== "profile" || matchedProfile)) {
      setSort(initialSort.value);
    }
    setUrlReady(true);
  }, [fragrances]);

  useEffect(() => {
    if (!urlReady) return;
    setCopyStatus("");

    const timeout = window.setTimeout(() => {
      const url = catalogLink({
        search, audience, profile, brand, minimumRating, sort,
      });

      const nextUrl = `${url.pathname}${url.search}${url.hash}`;
      const currentUrl = `${window.location.pathname}${window.location.search}${window.location.hash}`;
      if (nextUrl !== currentUrl) {
        window.history.replaceState(window.history.state, "", nextUrl);
      }
    }, 250);

    return () => window.clearTimeout(timeout);
  }, [search, audience, profile, brand, minimumRating, sort, urlReady]);

  const copyCatalogLink = async () => {
    const url = catalogLink({
      search, audience, profile, brand, minimumRating, sort,
    });
    try {
      await navigator.clipboard.writeText(url.href);
      setCopyStatus("Link kopiert");
    } catch {
      setCopyStatus("Kopieren nicht möglich. Bitte die Adresse im Browser kopieren.");
    }
  };

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

  const profileCounts = useMemo<Record<DiscoveryProfile, number>>(
    () => ({
      freshness: fragrances.filter((fragrance) =>
        matchesProfile(fragrance, "freshness"),
      ).length,
      sweetness: fragrances.filter((fragrance) =>
        matchesProfile(fragrance, "sweetness"),
      ).length,
      woodiness: fragrances.filter((fragrance) =>
        matchesProfile(fragrance, "woodiness"),
      ).length,
      spiciness: fragrances.filter((fragrance) =>
        matchesProfile(fragrance, "spiciness"),
      ).length,
    }),
    [fragrances],
  );

  const accordDiscovery = useMemo(() => {
    const counts = new Map<string, number>();

    for (const fragrance of fragrances) {
      for (const accord of new Set(fragrance.accords)) {
        counts.set(accord, (counts.get(accord) ?? 0) + 1);
      }
    }

    return Array.from(counts.entries())
      .map(([accord, count]) => ({
        accord,
        count,
        label: accordLabel(accord),
      }))
      .sort(
        (a, b) =>
          b.count - a.count ||
          a.label.localeCompare(b.label, "de"),
      )
      .slice(0, 8);
  }, [fragrances]);

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
        if (search.trim() && sort === "popular") {
          const relevance =
            searchScore(b, search) -
            searchScore(a, search);

          if (relevance) return relevance;
        }

        if (sort === "rating") {
          return (
            (b.community.rating_10 ?? 0) -
              (a.community.rating_10 ?? 0) ||
            b.community.rating_count -
              a.community.rating_count
          );
        }

        if (sort === "profile" && profile !== "all") {
          return (
            (b.scores[profile] ?? 0) -
              (a.scores[profile] ?? 0) ||
            b.community.rating_count -
              a.community.rating_count ||
            a.name.localeCompare(b.name, "de")
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

  useEffect(() => {
    const safeSearch = safeCatalogSearchTerm(search);

    if (!safeSearch) {
      lastTrackedSearchRef.current = "";
      return;
    }

    const fingerprint = [
      safeSearch,
      audience,
      profile,
      brand,
      minimumRating,
      String(filtered.length),
    ].join("|");

    const timeout = window.setTimeout(() => {
      if (lastTrackedSearchRef.current === fingerprint) {
        return;
      }

      lastTrackedSearchRef.current = fingerprint;
      void trackCatalogSearch(search, filtered.length);
    }, 700);

    return () => window.clearTimeout(timeout);
  }, [
    audience,
    brand,
    filtered.length,
    minimumRating,
    profile,
    search,
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
  const relaxedSearch = relaxedSearchQuery(search);
  const nonSearchFilterCount =
    Number(audience !== "all") +
    Number(profile !== "all") +
    Number(brand !== "all") +
    Number(minimumRating !== "0");

  const resetFilters = () => {
    setSearch("");
    setAudience("all");
    setProfile("all");
    setBrand("all");
    setMinimumRating("0");
    setSort("popular");
  };

  const selectedComparisonFragrances = compareSelection
    .map((productId) =>
      fragrances.find(
        (fragrance) => fragrance.product_id === productId,
      ),
    )
    .filter(
      (fragrance): fragrance is StaticFragrance =>
        fragrance != null,
    );

  const toggleComparisonSelection = (productId: string) => {
    setCompareSelection((current) => {
      if (current.includes(productId)) {
        return current.filter((id) => id !== productId);
      }
      if (current.length >= 2) return current;
      return [...current, productId];
    });
  };

  const comparisonHref =
    selectedComparisonFragrances.length === 2
      ? `/vergleich?left=${encodeURIComponent(
          selectedComparisonFragrances[0].product_id,
        )}&right=${encodeURIComponent(
          selectedComparisonFragrances[1].product_id,
        )}`
      : null;

  return (
    <>
      <section
        className="mt-7 overflow-hidden rounded-[26px] border border-white/10 p-4 text-white shadow-[0_26px_70px_-38px_rgba(23,21,19,0.9)] sm:p-5"
        style={{
          background:
            "radial-gradient(circle at 16% 0%, rgba(184, 137, 52, 0.28), transparent 32%), radial-gradient(circle at 86% 100%, rgba(92, 74, 52, 0.18), transparent 34%), linear-gradient(135deg, #161618 0%, #0a0b0d 72%)",
        }}
        aria-label="Duftgefühl entdecken"
      >
        <div className="flex flex-col gap-3 sm:flex-row sm:items-end sm:justify-between">
          <div>
            <div className="text-[10.5px] font-semibold uppercase tracking-[0.16em] text-white/[0.55]">
              Discovery
            </div>
            <h2 className="mt-1.5 text-[21px] font-semibold tracking-[-0.025em] sm:text-[24px]">
              Nach Duftgefühl entdecken
            </h2>
            <p className="mt-2 max-w-2xl text-[12px] leading-5 text-white/[0.62] sm:text-[13px]">
              Spring direkt in die Duftwelt, die zu deinem Moment passt. Jeder Einstieg filtert den Katalog sofort und lässt sich mit einem zweiten Klick wieder lösen.
            </p>
          </div>
          <div className="shrink-0 rounded-full border border-white/10 bg-white/[0.05] px-3 py-1.5 text-[10.5px] font-medium text-white/[0.58]">
            {fragrances.length} Düfte · 4 Welten
          </div>
        </div>

        <div className="mt-5 flex snap-x snap-mandatory gap-3 overflow-x-auto pb-2 lg:grid lg:grid-cols-4 lg:overflow-visible lg:pb-0">
          {PROFILE_DISCOVERY.map((card) => {
            const active = profile === card.value;

            return (
              <button
                key={card.value}
                type="button"
                onClick={() =>
                  selectProfile(active ? "all" : card.value, !active)
                }
                className={`group min-w-[224px] snap-start rounded-2xl border p-4 text-left transition duration-200 lg:min-w-0 ${
                  active
                    ? "border-[#d5a84f]/70 bg-[#d5a84f]/[0.12] shadow-[0_14px_34px_-22px_rgba(213,168,79,0.9)]"
                    : "border-white/10 bg-white/[0.045] hover:-translate-y-0.5 hover:border-white/20 hover:bg-white/[0.07]"
                }`}
                aria-pressed={active}
              >
                <div className="flex items-start justify-between gap-3">
                  <span className="text-[17px] font-semibold tracking-[-0.02em] text-white">
                    {card.label}
                  </span>
                  <span
                    className={`rounded-full border px-2 py-1 text-[9.5px] font-semibold ${
                      active
                        ? "border-[#d5a84f]/[0.35] bg-[#d5a84f]/[0.12] text-[#f1d493]"
                        : "border-white/10 bg-black/[0.15] text-white/[0.55]"
                    }`}
                  >
                    {profileCounts[card.value]} Düfte
                  </span>
                </div>
                <div className="mt-5 text-[12px] font-semibold text-white/[0.78]">
                  {card.mood}
                </div>
                <div className="mt-1 text-[11px] leading-4 text-white/[0.48]">
                  {card.notes}
                </div>
                <div
                  className={`mt-4 flex items-center justify-between border-t pt-3 text-[10.5px] font-semibold uppercase tracking-[0.08em] ${
                    active
                      ? "border-[#d5a84f]/[0.24] text-[#f1d493]"
                      : "border-white/[0.08] text-white/[0.48] group-hover:text-white/[0.68]"
                  }`}
                >
                  <span>{active ? "Profil aktiv" : "Entdecken"}</span>
                  <span aria-hidden="true">
                    {active ? "✓" : "→"}
                  </span>
                </div>
              </button>
            );
          })}
        </div>

        <div className="mt-5 border-t border-white/[0.08] pt-4">
          <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
            <div>
              <div className="text-[10px] font-semibold uppercase tracking-[0.14em] text-white/[0.45]">
                Duft-DNA
              </div>
              <div className="mt-1 text-[12px] font-semibold text-white/[0.74]">
                Beliebte Akkorde im aktuellen Katalog
              </div>
            </div>
            <div className="flex max-w-full gap-2 overflow-x-auto pb-1 sm:flex-wrap sm:justify-end sm:overflow-visible">
              {accordDiscovery.map(({ accord, count, label }) => {
                const active =
                  normalize(search) === normalize(label);

                return (
                  <button
                    key={accord}
                    type="button"
                    onClick={() =>
                      setSearch(active ? "" : label)
                    }
                    className={`shrink-0 rounded-full border px-3 py-2 text-[10.5px] font-semibold transition ${
                      active
                        ? "border-[#d5a84f]/65 bg-[#d5a84f]/[0.14] text-[#f1d493]"
                        : "border-white/10 bg-white/[0.04] text-white/[0.58] hover:border-white/20 hover:bg-white/[0.07] hover:text-white/[0.78]"
                    }`}
                    aria-pressed={active}
                    aria-label={`${label}: ${count} Düfte`}
                  >
                    {label}
                    <span className="ml-1.5 text-white/[0.36]">
                      {count}
                    </span>
                  </button>
                );
              })}
            </div>
          </div>
        </div>
      </section>

      <section
        className="mt-4 rounded-2xl border border-(--line) bg-(--card) p-4 shadow-(--shadow-sm) sm:p-5"
        aria-label="Duftkatalog filtern"
      >
        <div className="grid gap-3 md:grid-cols-[1fr_auto] md:items-end">
          <label className="block">
            <span className="mb-1.5 block text-[11px] font-semibold uppercase tracking-[0.07em] text-(--ink-soft)">
              Duft, Marke oder Profil
            </span>
            <input
              type="search"
              value={search}
              onChange={(event) =>
                setSearch(event.target.value)
              }
              placeholder="z. B. Prada Herren frisch, Naxos würzig …"
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
                {SORT_OPTIONS.filter(
                  (option) =>
                    option.value !== "profile" ||
                    profile !== "all",
                ).map((option) => (
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
                        selectProfile(option.value)
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
                onClick={() => selectProfile("all")}
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
              <span>
                {" "}
                · {visibleFragrances.length} angezeigt
              </span>
            ) : null}
          </div>

          {hasChanges ? (
            <div className="flex flex-wrap items-center gap-3">
              <button
                type="button"
                onClick={() => void copyCatalogLink()}
                className="text-[12px] font-semibold text-(--accent-ink) hover:underline"
              >
                Filterlink kopieren
              </button>
              <button
                type="button"
                onClick={resetFilters}
                className="text-[12px] font-semibold text-(--accent-ink) hover:underline"
              >
                Filter zurücksetzen
              </button>
            </div>
          ) : null}
        </div>
        <span role="status" className="text-[11px] text-(--ink-soft)">
          {copyStatus}
        </span>
      </section>

      {profile !== "all" ? (
        <div className="mt-5 flex items-baseline justify-between gap-3">
          <h2
            ref={resultsRef}
            tabIndex={-1}
            className="scroll-mt-5 text-[17px] font-semibold text-(--ink) focus:outline-none"
          >
            {optionLabel(PROFILE_OPTIONS, profile)} entdecken
          </h2>
          <span className="text-[11px] text-(--ink-soft)">
            {filtered.length} Treffer
            {sort === "profile" ? " · stärkstes Profil zuerst" : ""}
          </span>
        </div>
      ) : null}

      {compareSelection.length ? (
        <aside
          className="sticky bottom-3 z-30 mt-5 rounded-2xl border border-[#d9bd82]/30 bg-[#15120f]/95 p-3 text-white shadow-[0_20px_55px_-28px_rgba(20,14,6,0.92)] backdrop-blur sm:p-4"
          aria-label="Duftvergleich vorbereiten"
        >
          <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
            <div className="min-w-0">
              <div className="text-[9.5px] font-semibold uppercase tracking-[0.14em] text-[#d9bd82]">
                Vergleich vorbereiten
              </div>
              <div className="mt-1 flex flex-wrap gap-1.5 text-[11px] text-white/70">
                {selectedComparisonFragrances.map((fragrance, index) => (
                  <span
                    key={fragrance.product_id}
                    className="rounded-full border border-white/10 bg-white/[0.06] px-2.5 py-1"
                  >
                    {index + 1}. {fragrance.brand} {fragrance.name}
                  </span>
                ))}
                {selectedComparisonFragrances.length < 2 ? (
                  <span className="px-1 py-1 text-white/45">
                    Noch einen Duft auswählen
                  </span>
                ) : null}
              </div>
            </div>
            <div className="flex shrink-0 items-center gap-2">
              <button
                type="button"
                onClick={() => setCompareSelection([])}
                className="rounded-xl border border-white/10 px-3 py-2 text-[11px] font-semibold text-white/65 transition hover:border-white/20 hover:text-white"
              >
                Leeren
              </button>
              {comparisonHref ? (
                <a
                  href={comparisonHref}
                  className="rounded-xl bg-[#d9bd82] px-4 py-2 text-[11px] font-semibold text-[#241b0e] transition hover:bg-[#e4cb98]"
                >
                  Jetzt vergleichen →
                </a>
              ) : (
                <span
                  className="rounded-xl border border-white/10 bg-white/[0.04] px-4 py-2 text-[11px] font-semibold text-white/35"
                  aria-disabled="true"
                >
                  2 Düfte wählen
                </span>
              )}
            </div>
          </div>
        </aside>
      ) : null}

      {filtered.length ? (
        <>
          <section
            className="mt-5 grid gap-3 sm:grid-cols-2 lg:grid-cols-3"
            aria-label="Passende Düfte"
          >
            {visibleFragrances.map((fragrance) => {
              const visual = fragrance.preferred_visual;
              const isProductTruth =
                isVerifiedProductTruthVisual(visual);

              return (
              <article
                key={fragrance.product_id}
                className="overflow-hidden rounded-2xl border border-(--line) bg-(--card) shadow-(--shadow-sm) transition hover:-translate-y-0.5 hover:shadow-md"
              >
                <a
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
                  className="group block"
                >
                  <div className="h-52 w-full overflow-hidden">
                    {visual ? (
                      <FragranceVisual
                        imageUrl={visual.url}
                        cutoutUrl={isProductTruth ? visual.url : undefined}
                        alt={`${fragrance.brand} ${fragrance.name}`}
                        variant="card"
                        mode={isProductTruth ? "cutout" : "editorial"}
                        className="h-full w-full"
                      />
                    ) : (
                      <div className="grid h-full place-items-center text-[11px] font-semibold tracking-[0.16em] text-white/65">
                        DUFYND
                      </div>
                    )}
                  </div>

                  <div className="p-4 pb-3">
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

                    <div
                      className="mt-4 rounded-xl border border-(--line) bg-(--surface)/70 px-3 py-2.5"
                      aria-label="Duft-DNA"
                    >
                      <div className="mb-2 flex items-center justify-between gap-2">
                        <span className="text-[9.5px] font-semibold uppercase tracking-[0.08em] text-(--ink-soft)">
                          Duft-DNA
                        </span>
                        <span className="text-[9.5px] text-(--ink-soft)">
                          Profil 0–10
                        </span>
                      </div>
                      <div className="grid grid-cols-4 gap-2">
                        {SCENT_DNA_PROFILES.map(({ key, label }) => {
                          const value = scentDnaScore(
                            fragrance,
                            key,
                          );

                          return (
                            <div key={key} className="min-w-0">
                              <div className="h-1.5 overflow-hidden rounded-full bg-(--well)">
                                <div
                                  className="h-full rounded-full bg-(--accent)"
                                  style={{
                                    width: `${value * 10}%`,
                                  }}
                                />
                              </div>
                              <div className="mt-1 flex items-center justify-between gap-1">
                                <span className="truncate text-[8.5px] text-(--ink-soft)">
                                  {label}
                                </span>
                                <span className="text-[8.5px] font-semibold text-(--ink)">
                                  {value}
                                </span>
                              </div>
                            </div>
                          );
                        })}
                      </div>
                    </div>

                    <div className="mt-4 border-t border-(--line) pt-3 text-[11px] font-semibold text-(--accent-ink)">
                      Duftprofil & Angebote ansehen →
                    </div>
                  </div>
                </a>

                <div className="flex flex-wrap items-center justify-between gap-2 border-t border-(--line) p-3">
                  <FragranceSaveControls
                    productId={fragrance.product_id}
                    source="catalog_grid"
                    compact
                  />
                  <button
                    type="button"
                    onClick={() =>
                      toggleComparisonSelection(
                        fragrance.product_id,
                      )
                    }
                    disabled={
                      !compareSelection.includes(
                        fragrance.product_id,
                      ) && compareSelection.length >= 2
                    }
                    aria-pressed={compareSelection.includes(
                      fragrance.product_id,
                    )}
                    aria-label={`${fragrance.brand} ${fragrance.name} ${compareSelection.includes(fragrance.product_id) ? "aus Vergleich entfernen" : "für Vergleich auswählen"}`}
                    className="rounded-lg px-2 py-1.5 text-[11px] font-semibold text-(--accent-ink) transition hover:bg-(--well) disabled:cursor-not-allowed disabled:opacity-35"
                  >
                    {compareSelection.includes(
                      fragrance.product_id,
                    )
                      ? "Ausgewählt ✓"
                      : "Vergleichen +"}
                  </button>
                </div>
              </article>
              );
            })}
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
          <p className="mx-auto mt-2 max-w-lg text-[13px] leading-5 text-(--ink-soft)">
            {search.trim() && nonSearchFilterCount
              ? "Die Kombination aus Suchtext und aktiven Filtern ist aktuell zu eng."
              : search.trim()
                ? "Der Suchtext ist aktuell zu spezifisch."
                : "Die gewählten Filter liefern aktuell keine Treffer."}
            {" "}Du kannst die Suche lockern oder einzelne Filter oben entfernen.
          </p>

          <div className="mx-auto mt-5 flex max-w-xl flex-wrap justify-center gap-2">
            {relaxedSearch ? (
              <button
                type="button"
                onClick={() => setSearch(relaxedSearch)}
                className="rounded-xl bg-(--ink) px-4 py-2 text-[12px] font-semibold text-(--surface)"
              >
                Suche lockern: „{relaxedSearch}“
              </button>
            ) : null}

            {search.trim() ? (
              <button
                type="button"
                onClick={() => setSearch("")}
                className="rounded-xl border border-(--line) bg-(--surface) px-4 py-2 text-[12px] font-semibold text-(--ink)"
              >
                Nur Suche löschen
              </button>
            ) : null}

            {hasChanges ? (
              <button
                type="button"
                onClick={resetFilters}
                className="rounded-xl border border-(--line) bg-(--surface) px-4 py-2 text-[12px] font-semibold text-(--ink)"
              >
                Alle Filter zurücksetzen
              </button>
            ) : null}
          </div>

          <div className="mt-5 border-t border-(--line) pt-5">
            <p className="text-[12px] text-(--ink-soft)">
              Du suchst nach mehreren Eigenschaften gleichzeitig?
            </p>
            <a
              href="/"
              className="mt-2 inline-flex rounded-xl bg-(--ink) px-4 py-2 text-[12px] font-semibold text-(--surface)"
            >
              DUFYND Duftberater öffnen
            </a>
          </div>
        </section>
      )}
    </>
  );
}
