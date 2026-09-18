import { api } from "./api";

const ANALYTICS_SESSION_KEY = "scentai_analytics_session_v1";
let analyticsSessionPromise: Promise<string | null> | null = null;

function storedAnalyticsSession(): string | null {
  if (typeof window === "undefined") return null;

  try {
    return window.sessionStorage.getItem(
      ANALYTICS_SESSION_KEY,
    );
  } catch {
    return null;
  }
}

function rememberAnalyticsSession(sessionId: string): void {
  if (typeof window === "undefined") return;

  try {
    window.sessionStorage.setItem(
      ANALYTICS_SESSION_KEY,
      sessionId,
    );
  } catch {
    // Analytics storage must never break the shopping experience.
  }
}

async function ensureAnalyticsSession(): Promise<string | null> {
  if (api.session) {
    rememberAnalyticsSession(api.session);
    return api.session;
  }

  const stored = storedAnalyticsSession();
  if (stored) {
    api.session = stored;
    return stored;
  }

  if (!analyticsSessionPromise) {
    analyticsSessionPromise = api
      .startSession()
      .then((started) => {
        const sessionId = started?.sessionId ?? null;
        if (sessionId) {
          api.session = sessionId;
          rememberAnalyticsSession(sessionId);
        }
        return sessionId;
      })
      .finally(() => {
        analyticsSessionPromise = null;
      });
  }

  return analyticsSessionPromise;
}

export type AnalyticsEventName =
  | "page_view"
  | "consultation_start"
  | "product_open"
  | "merchant_clickout"
  | "catalog_search"
  | "catalog_no_results"
  | "advisor_recommendation_view"
  | "advisor_product_open"
  | "fragrance_detail_view"
  | "comparison_start";

export async function trackAnalyticsEvent(
  event: AnalyticsEventName,
  context: {
    product_id?: string;
    source?: string;
    search_term?: string;
    result_count?: number;
    surface?: string;
    related_product_id?: string;
    item_position?: number;
  } = {},
): Promise<void> {
  const sessionId = await ensureAnalyticsSession();
  if (!sessionId) return;

  await api.post("/analytics/events", {
    event,
    product_id: context.product_id,
    source: context.source,
    search_term: context.search_term,
    result_count: context.result_count,
    surface: context.surface,
    related_product_id: context.related_product_id,
    item_position: context.item_position,
  });
}


function normalizeCatalogSearchTerm(value: string): string {
  return value
    .normalize("NFKC")
    .toLowerCase()
    .replace(/\s+/g, " ")
    .trim()
    .slice(0, 80);
}

function looksSensitiveCatalogSearch(value: string): boolean {
  if (/\S+@\S+\.\S+/.test(value)) return true;
  if (/\b\d{7,}\b/.test(value.replace(/[\s()+-]/g, ""))) {
    return true;
  }
  return false;
}

export function safeCatalogSearchTerm(
  value: string,
): string | null {
  const normalized = normalizeCatalogSearchTerm(value);

  if (normalized.length < 2) return null;
  if (looksSensitiveCatalogSearch(normalized)) return null;

  return normalized;
}

export async function trackCatalogSearch(
  search: string,
  resultCount: number,
): Promise<void> {
  const searchTerm = safeCatalogSearchTerm(search);
  if (!searchTerm) return;

  await trackAnalyticsEvent(
    resultCount === 0
      ? "catalog_no_results"
      : "catalog_search",
    {
      source: "catalog_filter",
      search_term: searchTerm,
      result_count: resultCount,
    },
  );
}
