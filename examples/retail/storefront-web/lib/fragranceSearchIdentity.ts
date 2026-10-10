type FragranceIdentity = {
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
  return normalizeFragranceSearch([
    fragrance.brand, fragrance.name, fragrance.concentration,
    BRAND_ALIASES[normalizeFragranceSearch(fragrance.brand)] || "",
    CONCENTRATION_ALIASES[normalizeFragranceSearch(fragrance.concentration)] || "",
    `${fragrance.volume_ml}ml ${fragrance.volume_ml} ml`,
  ].join(" "));
}

// An explicit size or concentration must not match a different variant through
// substring matching (e.g. 50 ml within 150 ml). No variants are inferred.
export function matchesRequestedVariant(fragrance: FragranceIdentity, query: string): boolean {
  const volumes = [...query.toLowerCase().matchAll(/\b(\d+(?:[.,]\d+)?)\s*ml\b/g)];
  if (volumes.some((match) => Number(match[1].replace(",", ".")) !== fragrance.volume_ml)) return false;
  const concentration = CONCENTRATION_ALIASES[normalizeFragranceSearch(fragrance.concentration)];
  const requested = normalizeFragranceSearch(query).match(/\b(edp|edt|extrait)\b/g) || [];
  return requested.every((value) => value === concentration);
}
