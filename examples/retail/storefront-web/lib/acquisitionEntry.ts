export type EntryAttribution = {
  source: string;
  campaign_id?: string;
  content_id?: string;
};

const CHANNELS = new Set([
  "tiktok", "instagram", "youtube", "organic", "newsletter", "partner",
  "unknown", "referral",
  "google", "bing", "duckduckgo", "yahoo", "ecosia",
]);

function identifier(value: string | null): string | undefined {
  const clean = value?.trim();
  return clean && /^[A-Za-z0-9._:-]{1,80}$/.test(clean) ? clean : undefined;
}

// Read only the host: never store a referrer's path, search terms or personal data.
function referrerSource(referrer: string, origin: string): string | undefined {
  try {
    const url = new URL(referrer);
    if (!["https:", "http:"].includes(url.protocol)) return;
    const host = url.hostname.toLowerCase();
    if (url.origin === origin || ["dufynd.de", "www.dufynd.de"].includes(host)) return;
    const matches = (domain: string) => host === domain || host.endsWith(`.${domain}`);
    if (matches("instagram.com")) return "instagram";
    if (matches("youtube.com") || matches("youtu.be")) return "youtube";
    if (matches("tiktok.com")) return "tiktok";
    if (["google.com", "google.de", "bing.com", "duckduckgo.com", "search.yahoo.com", "ecosia.org"].some(matches)) return "organic";
    return "referral";
  } catch { return; }
}

export function resolveAcquisitionEntry(
  search: string,
  referrer: string,
  origin: string,
  previous: EntryAttribution | null,
): EntryAttribution {
  const params = new URLSearchParams(search);
  const src = identifier(params.get("src"))?.toLowerCase();
  const utm = identifier(params.get("utm_source"))?.toLowerCase();
  // Existing DUFYND links take precedence. Preserve explicit UTM sources as
  // labelled, e.g. google + cpc must not be relabelled organic search.
  const source = (src && CHANNELS.has(src) ? src : undefined)
    || (utm ? (CHANNELS.has(utm) ? utm : "unknown") : undefined);
  if (source) {
    const campaign = identifier(params.get("cmp")) || identifier(params.get("utm_campaign"));
    const content = identifier(params.get("content")) || identifier(params.get("utm_content"));
    return { source, ...(campaign ? { campaign_id: campaign } : {}), ...(content ? { content_id: content } : {}) };
  }
  const referred = referrerSource(referrer, origin);
  // A new external entry must not inherit an unrelated old campaign.
  if (referred) return { source: referred };
  return previous || { source: "unknown" };
}
