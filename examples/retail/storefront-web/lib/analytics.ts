import { api, initializeAnalyticsSession } from "./api";
import { resolveAcquisitionEntry } from "./acquisitionEntry";

const ACQUISITION_IDENTIFIER_PATTERN = /^[A-Za-z0-9._:-]{1,80}$/;
let apiSessionPromise: Promise<string | null> | null = null;
let analyticsOwnedApiSession: string | null = null;
let analyticsEventQueue: Promise<void> = Promise.resolve();
let acquisitionAttributionMemory: AcquisitionAttribution | null = null;
const ACQUISITION_STORAGE_KEY = "dufynd_acquisition_attribution_v1";
const ANALYTICS_EVENT_TIMEOUT_MS = 8_000;
const ANALYTICS_SESSION_STORAGE_KEY = "dufynd_analytics_session_v1";
// Match the URL-safe alphabet used by the server's secrets.token_urlsafe(24).
const ANALYTICS_SESSION_PATTERN = /^[A-Za-z0-9_-]{16,80}$/;
let analyticsSessionMemory: string | null = null;

let internalQaMemory = false;
let entryReferrerConsumed = false;
const QA_STORAGE_KEY = "dufynd_internal_qa_v1";

export function isInternalQa(): boolean {
  if (typeof window === "undefined") return false;
  if (new URLSearchParams(window.location?.search || "").get("qa") === "1") internalQaMemory = true;
  try {
    internalQaMemory ||= window.sessionStorage.getItem(QA_STORAGE_KEY) === "1";
    if (internalQaMemory) window.sessionStorage.setItem(QA_STORAGE_KEY, "1");
  } catch { /* Keep the in-memory marker when storage is unavailable. */ }
  return internalQaMemory;
}

// Keep the funnel identity across document navigation and API-session recovery.
// API/advisor session ownership remains independent and is never restored here.
function currentAnalyticsSessionId(): string | null {
  if (typeof window === "undefined") return api.session;
  if (analyticsSessionMemory) return analyticsSessionMemory;
  try {
    const stored = window.sessionStorage.getItem(ANALYTICS_SESSION_STORAGE_KEY);
    if (stored && ANALYTICS_SESSION_PATTERN.test(stored)) {
      analyticsSessionMemory = stored;
      return stored;
    }
  } catch {
    // Blocked browser storage cannot block analytics or shopping.
  }
  const session = api.session;
  if (!session || !ANALYTICS_SESSION_PATTERN.test(session)) return null;
  analyticsSessionMemory = session;
  try {
    window.sessionStorage.setItem(ANALYTICS_SESSION_STORAGE_KEY, session);
  } catch {
    // Retain an in-memory identity for this document when storage is unavailable.
  }
  return session;
}

export type AcquisitionAttribution = {
  source: string;
  campaign_id?: string;
  content_id?: string;
};

function safeAcquisitionIdentifier(
  value: string | null | undefined,
): string | null {
  const normalized = String(value || "").trim();
  return ACQUISITION_IDENTIFIER_PATTERN.test(normalized)
    ? normalized
    : null;
}

function storedAcquisitionAttribution(): AcquisitionAttribution | null {
  if (acquisitionAttributionMemory) {
    return acquisitionAttributionMemory;
  }

  if (typeof window === "undefined") {
    return null;
  }

  try {
    const raw = window.sessionStorage.getItem(
      ACQUISITION_STORAGE_KEY,
    );
    if (!raw) return null;

    const parsed = JSON.parse(raw) as Partial<AcquisitionAttribution>;
    const source = safeAcquisitionIdentifier(parsed.source);
    const campaign = safeAcquisitionIdentifier(
      parsed.campaign_id,
    );
    const content = safeAcquisitionIdentifier(
      parsed.content_id,
    );

    if (!source) return null;

    acquisitionAttributionMemory = {
      source,
      ...(campaign ? { campaign_id: campaign } : {}),
      ...(content ? { content_id: content } : {}),
    };
    return acquisitionAttributionMemory;
  } catch {
    return null;
  }
}

export function rememberAcquisitionAttribution({
  source,
  campaignId,
  contentId,
}: {
  source: string;
  campaignId?: string | null;
  contentId?: string | null;
}): void {
  const safeSource = safeAcquisitionIdentifier(source);
  if (!safeSource) return;

  const safeCampaign = safeAcquisitionIdentifier(campaignId);
  const safeContent = safeAcquisitionIdentifier(contentId);

  const attribution: AcquisitionAttribution = {
    source: safeSource,
    ...(safeCampaign ? { campaign_id: safeCampaign } : {}),
    ...(safeContent ? { content_id: safeContent } : {}),
  };

  acquisitionAttributionMemory = attribution;

  if (typeof window !== "undefined") {
    try {
      window.sessionStorage.setItem(
        ACQUISITION_STORAGE_KEY,
        JSON.stringify(attribution),
      );
    } catch {
      // Attribution is helpful but must never block the storefront.
    }
  }
}

export function currentAcquisitionAttribution():
  | AcquisitionAttribution
  | null {
  return storedAcquisitionAttribution();
}

export function captureAcquisitionEntry(): AcquisitionAttribution | null {
  if (typeof window === "undefined") return storedAcquisitionAttribution();
  const entry = resolveAcquisitionEntry(
    window.location?.search || "",
    !entryReferrerConsumed && typeof document !== "undefined" ? document.referrer : "",
    window.location?.origin || "",
    storedAcquisitionAttribution(),
  );
  entryReferrerConsumed = true;
  rememberAcquisitionAttribution({ source: entry.source, campaignId: entry.campaign_id, contentId: entry.content_id });
  return entry;
}

export function appendAcquisitionAttribution(
  url: string,
): string {
  const attribution = captureAcquisitionEntry();
  const internalQa = isInternalQa();
  if (!attribution && !internalQa) return url;

  const target = new URL(
    url,
    typeof window !== "undefined"
      ? window.location.origin
      : "http://localhost",
  );

  if (internalQa) target.searchParams.set("qa", "1");
  if (attribution) target.searchParams.set("src", attribution.source);
  if (attribution?.campaign_id) {
    target.searchParams.set(
      "cmp",
      attribution.campaign_id,
    );
  }
  if (attribution?.content_id) {
    target.searchParams.set(
      "content",
      attribution.content_id,
    );
  }

  const activeSession = safeAcquisitionIdentifier(
    currentAnalyticsSessionId(),
  );
  if (activeSession) {
    target.searchParams.set("sid", activeSession);
  }

  return target.toString();
}

export async function ensureAnalyticsSession(): Promise<string | null> {
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
    apiSessionPromise = initializeAnalyticsSession()
      .then((sessionId) => {
        // The advisor can establish its session while this request is pending.
        // Use the current owner instead of installing a late analytics session.
        if (api.session) {
          if (analyticsOwnedApiSession !== api.session) {
            analyticsOwnedApiSession = null;
          }
          return api.session;
        }
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
  | "offer_section_open"
  | "offer_section_view"
  | "comparison_start"
  | "wishlist_add"
  | "wishlist_remove"
  | "collection_add"
  | "collection_remove";

type AnalyticsContext = {
  product_id?: string;
  source?: string;
  search_term?: string;
  result_count?: number;
  surface?: string;
  related_product_id?: string;
  item_position?: number;
};

async function postAnalyticsPayload(
  payload: Record<string, unknown>,
): Promise<boolean> {
  const controller = new AbortController();
  const timeoutId = setTimeout(() => controller.abort(), ANALYTICS_EVENT_TIMEOUT_MS);
  try {
    const response = await fetch(
      `${api.base}/analytics/events`,
      {
        method: "POST",
        headers: api.headers(true),
        body: JSON.stringify(payload),
        keepalive: true,
        signal: controller.signal,
      },
    );
    return response.ok;
  } catch {
    return false;
  } finally {
    clearTimeout(timeoutId);
  }
}

async function sendAnalyticsEvent(
  event: AnalyticsEventName,
  context: AnalyticsContext,
): Promise<void> {
  const apiSessionId = await ensureAnalyticsSession();
  if (!apiSessionId) return;

  const attribution = captureAcquisitionEntry();

  const payload = {
    // Generate once per action, outside the bounded transport retry.
    event_id: globalThis.crypto?.randomUUID?.(),
    event,
    internal_qa: isInternalQa(),
    product_id: context.product_id,
    source: context.source,
    acquisition_source: attribution?.source,
    campaign_id: attribution?.campaign_id,
    content_id: attribution?.content_id,
    search_term: context.search_term,
    result_count: context.result_count,
    surface: context.surface,
    related_product_id: context.related_product_id,
    item_position: context.item_position,
    analytics_session_id: currentAnalyticsSessionId(),
  };

  const recorded = await postAnalyticsPayload(payload);

  // A Render restart can invalidate an API session created only for a
  // standalone analytics page. Retry once with a new API session, but never
  // replace an active advisor session owned by the storefront.
  if (
    !recorded &&
    analyticsOwnedApiSession === apiSessionId &&
    api.session === apiSessionId
  ) {
    api.session = null;
    analyticsOwnedApiSession = null;

    const freshSession = await ensureAnalyticsSession();
    if (!freshSession) return;

    await postAnalyticsPayload(payload);
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
