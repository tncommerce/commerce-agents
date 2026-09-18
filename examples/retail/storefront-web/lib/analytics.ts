import { api } from "./api";

const ANALYTICS_CONTEXT_KEY = "scentai_analytics_context_v1";
const ANALYTICS_CONTEXT_PATTERN = /^[A-Za-z0-9-]{16,80}$/;
let apiSessionPromise: Promise<string | null> | null = null;
let analyticsOwnedApiSession: string | null = null;
let analyticsEventQueue: Promise<void> = Promise.resolve();

function storedAnalyticsContext(): string | null {
  if (typeof window === "undefined") return null;

  try {
    const value = window.sessionStorage.getItem(
      ANALYTICS_CONTEXT_KEY,
    );
    return value && ANALYTICS_CONTEXT_PATTERN.test(value)
      ? value
      : null;
  } catch {
    return null;
  }
}

function rememberAnalyticsContext(contextId: string): void {
  if (typeof window === "undefined") return;

  try {
    window.sessionStorage.setItem(
      ANALYTICS_CONTEXT_KEY,
      contextId,
    );
  } catch {
    // Analytics storage must never break the shopping experience.
  }
}

function createAnalyticsContext(): string | null {
  if (
    typeof window === "undefined" ||
    !window.crypto
  ) {
    return null;
  }

  if (typeof window.crypto.randomUUID === "function") {
    return window.crypto.randomUUID();
  }

  const bytes = new Uint8Array(16);
  window.crypto.getRandomValues(bytes);
  return Array.from(
    bytes,
    (value) => value.toString(16).padStart(2, "0"),
  ).join("");
}

function analyticsContextId(): string | null {
  const stored = storedAnalyticsContext();
  if (stored) return stored;

  const created = createAnalyticsContext();
  if (created) rememberAnalyticsContext(created);
  return created;
}

async function ensureApiSession(): Promise<string | null> {
  if (api.session) {
    if (
      analyticsOwnedApiSession &&
      analyticsOwnedApiSession !== api.session
    ) {
      analyticsOwnedApiSession = null;
    }
    return api.session;
  }

  if (!apiSessionPromise) {
    apiSessionPromise = api
      .startSession()
      .then((started) => {
        const sessionId = started?.sessionId ?? null;
        if (sessionId) {
          api.session = sessionId;
          analyticsOwnedApiSession = sessionId;
        }
        return sessionId;
      })
      .finally(() => {
        apiSessionPromise = null;
      });
  }

  return apiSessionPromise;
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
  const apiSessionId = await ensureApiSession();
  if (!apiSessionId) return;

  const payload = {
    event,
    product_id: context.product_id,
    source: context.source,
    search_term: context.search_term,
    result_count: context.result_count,
    surface: context.surface,
    related_product_id: context.related_product_id,
    item_position: context.item_position,
    analytics_session_id: analyticsContextId(),
  };

  const recorded = await api.post<{ ok?: boolean }>(
    "/analytics/events",
    payload,
  );

  // A Render restart can invalidate an API session created only for a
  // standalone analytics page. Retry once with a new API session, but never
  // replace an active advisor session owned by the storefront.
  if (
    recorded === null &&
    analyticsOwnedApiSession === apiSessionId
  ) {
    api.session = null;
    analyticsOwnedApiSession = null;

    const freshSession = await ensureApiSession();
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
