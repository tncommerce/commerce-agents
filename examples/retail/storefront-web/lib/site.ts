const DEFAULT_SITE_URL = "https://scentai-xxya.onrender.com";

function normalizeSiteUrl(value: string | undefined): string {
  const candidate = (value || DEFAULT_SITE_URL).trim().replace(/\/$/, "");

  try {
    const parsed = new URL(candidate);
    if (parsed.protocol !== "https:" && parsed.protocol !== "http:") {
      return DEFAULT_SITE_URL;
    }
    return parsed.toString().replace(/\/$/, "");
  } catch {
    return DEFAULT_SITE_URL;
  }
}

export const SITE_URL = normalizeSiteUrl(
  process.env.NEXT_PUBLIC_SITE_URL,
);

export const SITE_INDEXABLE =
  process.env.NEXT_PUBLIC_SITE_INDEXABLE === "true";
