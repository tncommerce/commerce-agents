// Functional navigation only. Never nest acquisition/session parameters or URLs.
const FILTER_KEYS = ["q", "profil", "zielgruppe", "marke", "bewertung", "sort"];

export function catalogContext(params: URLSearchParams): string {
  const clean = new URLSearchParams();
  for (const key of FILTER_KEYS) {
    const value = params.get(key)?.trim().slice(0, 80);
    if (value) clean.set(key, value);
  }
  const selection = [...new Set((params.get("compare") || "").split(","))]
    .filter((id) => /^SC-[A-Z0-9-]{1,96}$/.test(id)).slice(0, 2);
  if (selection.length) clean.set("compare", selection.join(","));
  return clean.toString();
}

export function catalogReturnHref(context: string): string {
  const clean = catalogContext(new URLSearchParams(context.slice(0, 1600)));
  return `/duft${clean ? `?${clean}` : ""}#dufynd-katalog`;
}

export function withCatalogContext(href: string, context: string): string {
  if (!context) return href;
  const target = new URL(href, "https://dufynd.invalid");
  target.searchParams.set("catalog", catalogContext(new URLSearchParams(context)));
  return `${target.pathname}${target.search}${target.hash}`;
}
