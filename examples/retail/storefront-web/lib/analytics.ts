import { api } from "./api";

const ANALYTICS_SESSION_KEY = "scentai_analytics_session_v1";
let analyticsSessionPromise: Promise<string | null> | null = null;
let restoredAnalyticsSession: string | null = null;
let analyticsEventQueue: Promise<void> = Promise.resolve();

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

function clearStoredAnalyticsSession(): void {
  if (typeof window === "undefined") return;

  try {
    window.sessionStorage.removeItem(
      ANALYTICS_SESSION_KEY,
    );
  } catch {
    // Analytics storage must never break the shopping experience.
  }
}

async function ensureAnalyticsSession(): Promise<string | null> {
  if (api.session) {
    if (
      restoredAnalyticsSession &&
      restoredAnalyticsSession !== api.session
    ) {
      restoredAnalyticsSession = null;
    }
    rememberAnalyticsSession(api.session);
    return api.session;
  }

  const stored = storedAnalyticsSession();
  if (stored) {
    api.session = stored;
    restoredAnalyticsSession = stored;
    return stored;
  }

  if (!analyticsSessionPromise) {
    analyticsSessionPromise = api
      .startSession()
      .then((started) => {
        const sessionId = started?.sessionId ?? null;
        if (sessionId) {
          api.session = sessionId;
          restoredAnalyticsSession = null;
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

type AnalyticsContext = {
  product_id?: string;
  source?: string;
  search_term?: string;
  result_count?: number;
  surface?: string;
  related_product_id?: string;
  item_position?: number;
};

async function sendAnalyticsEvent(
  event: AnalyticsEventName,
  context: AnalyticsContext,
): Promise<void> {
  const sessionId = await ensureAnalyticsSession();
  if (!sessionId) return;

  const payload = {
    event,
    product_id: context.product_id,
    source: context.source,
    search_term: context.search_term,
    result_count: context.result_count,
    surface: context.surface,
    related_product_id: context.related_product_id,
    item_position: context.item_position,
  };

  const recorded = await api.post<{ ok?: boolean }>(
    "/analytics/events",
    payload,
  );

  // Render restarts can invalidate the in-memory API session while the
  // browser still holds its anonymous analytics session. Recover once
  // without disturbing an active advisor session.
  if (
    recorded === null &&
    restoredAnalyticsSession === sessionId
  ) {
    clearStoredAnalyticsSession();
    restoredAnalyticsSession = null;
    api.session = null;

    const freshSession = await ensureAnalyticsSession();
    if (!freshSession) return;

    await api.post("/analytics/events", payload);
  }
}

export function trackAnalyticsEvent(
  event: AnalyticsEventName,
  context: AnalyticsContext = {},
): Promise<void> {
  const queued = analyticsEventQueue.then(() =>
    sendAnalyticsEvent(event, context),
  );

  analyticsEventQueue = queued.catch(() => {
    // First-party analytics must never interrupt the storefront.
  });

  return analyticsEventQueue;
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
