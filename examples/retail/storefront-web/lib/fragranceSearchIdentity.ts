type FragranceIdentity = {
  product_id?: string;
  brand: string;
  name: string;
  concentration: string;
  volume_ml: number;
};

export function normalizeFragranceSearch(value: string): string {
  return value.normalize("NFKD").replace(/[\u0300-\u036f]/g, "")
    .toLowerCase().replace(/ß/g, "ss").replace(/[^a-z0-9]+/g, " ")
    .replace(/\s+/g, " ").trim();
}

const BRAND_ALIASES: Record<string, string> = {
  "yves saint laurent": "ysl",
  "parfums de marly": "pdm",
  rabanne: "paco rabanne",
};
const CONCENTRATION_ALIASES: Record<string, string> = {
  "eau de parfum": "edp",
  "eau de toilette": "edt",
  "extrait de parfum": "extrait",
};

export function fragranceSearchIdentity(fragrance: FragranceIdentity): string {
  const brand = normalizeFragranceSearch(fragrance.brand);
  const productAliases = brand === "rabanne" && normalizeFragranceSearch(fragrance.name) === "1 million"
    ? "one million onemillion 1million" : "";
  // The verified Libre purchase guide describes this exact 90-ml bottle as
  // refillable. Do not transfer that property to other sizes or refill packs.
  const refillableBottleAliases =
    fragrance.product_id === "SC-YSL-LIBRE-EDP-90" &&
    brand === "yves saint laurent" &&
    normalizeFragranceSearch(fragrance.name) === "libre" &&
    normalizeFragranceSearch(fragrance.concentration) === "eau de parfum" &&
    fragrance.volume_ml === 90
      ? "nachfüllbar nachfüllbarer Flakon refillable"
      : "";
  return normalizeFragranceSearch([
    fragrance.brand, fragrance.name, fragrance.concentration,
    BRAND_ALIASES[brand] || "", productAliases, refillableBottleAliases,
    CONCENTRATION_ALIASES[normalizeFragranceSearch(fragrance.concentration)] || "",
    `${fragrance.volume_ml}ml ${fragrance.volume_ml} ml`,
  ].join(" "));
}

// Expand only a whole token equal to this product's complete normalized name.
// Do not compact the query, brand, concentration or size, or match name prefixes.
// Numeric names retain their existing explicit, brand-bound aliases above.
export function fragranceSearchTokens(fragrance: FragranceIdentity, query: string): string[] {
  const name = normalizeFragranceSearch(fragrance.name);
  const words = name.split(" ");
  const compactName = /^[a-z]+(?: [a-z]+)+$/.test(name) ? words.join("") : null;
  return normalizeFragranceSearch(query).split(" ").filter(Boolean)
    .flatMap((token) => token === compactName ? words : [token]);
}

// An explicit size or concentration must not match a different variant through
// substring matching (e.g. 50 ml within 150 ml). No variants are inferred.
export function matchesRequestedVariant(fragrance: FragranceIdentity, query: string): boolean {
  const volumes = [...query.toLowerCase().matchAll(/\b(\d+(?:[.,]\d+)?)\s*ml\b/g)];
  if (volumes.some((match) => Number(match[1].replace(",", ".")) !== fragrance.volume_ml)) return false;
  const name = ` ${normalizeFragranceSearch(fragrance.name)} `;
  const normalizedQuery = ` ${normalizeFragranceSearch(query)} `;
  // Variant qualifiers belong to the recorded product name, not a substring
  // elsewhere in the search document (e.g. "le" in Belle + EDP's "parfum").
  for (const qualifier of ["intense", "elixir", "le parfum", "refill", "nachfullung"]) {
    if (normalizedQuery.includes(` ${qualifier} `) && !name.includes(` ${qualifier} `)) return false;
  }
  const concentration = CONCENTRATION_ALIASES[normalizeFragranceSearch(fragrance.concentration)];
  const requested = normalizeFragranceSearch(query).match(/\b(edp|edt|extrait)\b/g) || [];
  return requested.every((value) => value === concentration);
}
