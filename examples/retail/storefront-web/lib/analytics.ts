import { api, initializeAnalyticsSession } from "./api";
import { resolveAcquisitionEntry } from "./acquisitionEntry";
import {
  MEASUREMENT_PROTOCOL, measurementAllowed, measurementChoice,
  measurementGeneration, measurementStillAllowed, subscribeMeasurement,
} from "./measurementConsent";

const ACQUISITION_IDENTIFIER_PATTERN = /^[A-Za-z0-9._:-]{1,80}$/;
const ACQUISITION_STORAGE_KEY = "dufynd_acquisition_attribution_v1";
const ANALYTICS_SESSION_STORAGE_KEY = "dufynd_analytics_session_v1";
const QA_STORAGE_KEY = "dufynd_internal_qa_v1";
const ANALYTICS_SESSION_PATTERN = /^[A-Za-z0-9_-]{16,80}$/;
const ANALYTICS_EVENT_TIMEOUT_MS = 8_000;
const OPTIONAL_URL_FIELDS = ["sid", "src", "cmp", "content", "measurement", "utm_source", "utm_medium", "utm_campaign", "utm_content", "utm_term"];
let apiSessionPromise: Promise<string | null> | null = null;
let analyticsOwnedApiSession: string | null = null;
let analyticsEventQueue: Promise<void> = Promise.resolve();
let acquisitionAttributionMemory: AcquisitionAttribution | null = null;
let analyticsSessionMemory: string | null = null;
let internalQaMemory = false;
let entryReferrerConsumed = false;
let ignoreIncomingSession = false;
let cleanupInstalled = false;
const activeRequests = new Set<AbortController>();

export type AcquisitionAttribution = { source: string; campaign_id?: string; content_id?: string };
function safeAcquisitionIdentifier(value: string | null | undefined): string | null {
  const normalized = String(value || "").trim();
  return ACQUISITION_IDENTIFIER_PATTERN.test(normalized) ? normalized : null;
}

export function isInternalQa(): boolean {
  if (typeof window === "undefined" || !measurementAllowed()) return false;
  if (new URLSearchParams(window.location.search || "").get("qa") === "1") internalQaMemory = true;
  try {
    internalQaMemory ||= window.sessionStorage.getItem(QA_STORAGE_KEY) === "1";
    if (internalQaMemory) window.sessionStorage.setItem(QA_STORAGE_KEY, "1");
  } catch { /* Classification remains in memory; QA never grants permission. */ }
  return internalQaMemory;
}
function currentAnalyticsSessionId(): string | null {
  if (typeof window === "undefined" || !measurementAllowed()) return null;
  if (analyticsSessionMemory) return analyticsSessionMemory;
  try {
    const stored = window.sessionStorage.getItem(ANALYTICS_SESSION_STORAGE_KEY);
    if (stored && ANALYTICS_SESSION_PATTERN.test(stored)) return (analyticsSessionMemory = stored);
  } catch { /* Blocked storage must not break shopping. */ }
  let incoming: string | null = null;
  if (!ignoreIncomingSession) {
    try {
      const value = new URLSearchParams(window.location.search || "").get("sid");
      if (value && ANALYTICS_SESSION_PATTERN.test(value) &&
          new URL(document.referrer).origin === window.location.origin) incoming = value;
    } catch { /* Shared/external URLs cannot establish a previous tab identity. */ }
  }
  // Independent of the functional advisor session, also after withdrawal/regrant.
  const session = incoming || globalThis.crypto?.randomUUID?.();
  if (!session || !ANALYTICS_SESSION_PATTERN.test(session)) return null;
  analyticsSessionMemory = session;
  try { window.sessionStorage.setItem(ANALYTICS_SESSION_STORAGE_KEY, session); } catch { /* Memory only. */ }
  return session;
}
function storedAcquisitionAttribution(): AcquisitionAttribution | null {
  if (typeof window === "undefined" || !measurementAllowed()) return null;
  if (acquisitionAttributionMemory) return acquisitionAttributionMemory;
  try {
    const raw = window.sessionStorage.getItem(ACQUISITION_STORAGE_KEY);
    if (!raw) return null;
    const parsed = JSON.parse(raw) as Partial<AcquisitionAttribution>;
    const source = safeAcquisitionIdentifier(parsed.source);
    const campaign = safeAcquisitionIdentifier(parsed.campaign_id);
    const content = safeAcquisitionIdentifier(parsed.content_id);
    if (!source) return null;
    return (acquisitionAttributionMemory = { source, ...(campaign ? {campaign_id: campaign} : {}), ...(content ? {content_id: content} : {}) });
  } catch { return null; }
}
export function rememberAcquisitionAttribution({source, campaignId, contentId}: {
  source: string; campaignId?: string | null; contentId?: string | null;
}): void {
  if (!measurementAllowed()) return;
  const safeSource = safeAcquisitionIdentifier(source);
  if (!safeSource) return;
  const campaign = safeAcquisitionIdentifier(campaignId), content = safeAcquisitionIdentifier(contentId);
  acquisitionAttributionMemory = { source: safeSource, ...(campaign ? {campaign_id: campaign} : {}), ...(content ? {content_id: content} : {}) };
  try { window.sessionStorage.setItem(ACQUISITION_STORAGE_KEY, JSON.stringify(acquisitionAttributionMemory)); }
  catch { /* Attribution must never block the storefront. */ }
}
export function currentAcquisitionAttribution(): AcquisitionAttribution | null { return storedAcquisitionAttribution(); }
export function captureAcquisitionEntry(): AcquisitionAttribution | null {
  if (typeof window === "undefined" || !measurementAllowed()) return null;
  const entry = resolveAcquisitionEntry(window.location.search || "", !entryReferrerConsumed ? document.referrer : "",
    window.location.origin, storedAcquisitionAttribution());
  entryReferrerConsumed = true;
  rememberAcquisitionAttribution({source: entry.source, campaignId: entry.campaign_id, contentId: entry.content_id});
  return entry;
}

// Destination validation precedes any consent, acquisition or optional storage read.
function acquisitionTarget(url: string): URL | null {
  if (typeof window === "undefined") return null;
  try {
    const origin = window.location.origin;
    const target = new URL(url, window.location.href || origin);
    if (!/^https?:$/.test(target.protocol) || target.username || target.password) return null;
    const isClickout = (prefix: string, suffix = ""): boolean => {
      if (!target.pathname.startsWith(prefix) || !target.pathname.endsWith(suffix)) return false;
      const offer = decodeURIComponent(target.pathname.slice(prefix.length, suffix ? -suffix.length : undefined));
      return Boolean(offer) && offer !== "." && offer !== ".." && !/[\\/\u0000-\u0020\u007f]/.test(offer);
    };
    if (target.origin === origin) {
      return !/^\/api(?:\/|$)/.test(target.pathname) || isClickout("/api/clickout/") ||
        isClickout("/api/merchant-partners/", "/clickout") ? target : null;
    }
    const apiRoot = new URL(api.base, origin);
    if (!/^https?:$/.test(apiRoot.protocol) || apiRoot.username || apiRoot.password || target.origin !== apiRoot.origin) return null;
    const root = apiRoot.pathname.replace(/\/$/, "");
    return isClickout(`${root}/clickout/`) || isClickout(`${root}/merchant-partners/`, "/clickout") ? target : null;
  } catch { return null; }
}
function stripOptionalFields(target: URL): void {
  // URLSearchParams.delete also reserializes an unchanged query (%20 becomes
  // +). Leave functional SSR links intact when there is no optional data.
  for (const key of OPTIONAL_URL_FIELDS) {
    if (target.searchParams.has(key)) target.searchParams.delete(key);
  }
}
export function appendAcquisitionAttribution(url: string): string {
  // A fragment is same-document navigation, not a new acquisition or clickout.
  // Preserve its raw form and never turn it into a different page destination.
  if (url.startsWith("#")) return url;
  const target = acquisitionTarget(url);
  if (!target) return url;
  if (!measurementAllowed()) { stripOptionalFields(target); return target.toString(); }
  const attribution = captureAcquisitionEntry(), internalQa = isInternalQa();
  if (internalQa) target.searchParams.set("qa", "1");
  if (attribution) target.searchParams.set("src", attribution.source);
  if (attribution?.campaign_id) target.searchParams.set("cmp", attribution.campaign_id);
  if (attribution?.content_id) target.searchParams.set("content", attribution.content_id);
  const session = currentAnalyticsSessionId();
  if (session) target.searchParams.set("sid", session);
  // The explicit transport signal is only for our redirect endpoints; never
  // adopt it from an incoming URL as consent, and never send it to a third party.
  if (/\/(?:clickout\/[^/]+|merchant-partners\/[^/]+\/clickout)$/.test(target.pathname)) {
    target.searchParams.set("measurement", MEASUREMENT_PROTOCOL);
  } else { target.searchParams.delete("measurement"); }
  return target.toString();
}

function clearOptionalState(): void {
  for (const controller of activeRequests) controller.abort();
  activeRequests.clear();
  if (analyticsOwnedApiSession && api.session === analyticsOwnedApiSession) api.session = null;
  analyticsOwnedApiSession = null;
  // A pending initializer keeps its own captured promise and generation. It
  // cannot clear or replace a later generation's new initializer when it returns.
  apiSessionPromise = null;
  analyticsEventQueue = Promise.resolve();
  analyticsSessionMemory = null; acquisitionAttributionMemory = null;
  internalQaMemory = false; entryReferrerConsumed = false; ignoreIncomingSession = true;
  if (typeof window === "undefined") return;
  for (const key of [ANALYTICS_SESSION_STORAGE_KEY, ACQUISITION_STORAGE_KEY, QA_STORAGE_KEY]) {
    try { window.sessionStorage.removeItem(key); } catch { /* No fallback storage. */ }
  }
  try {
    const url = new URL(window.location.href);
    if (measurementChoice() === "denied") stripOptionalFields(url);
    else { url.searchParams.delete("sid"); url.searchParams.delete("measurement"); }
    if (url.toString() !== window.location.href) window.history.replaceState(window.history.state, "", url);
  } catch { /* History restrictions cannot restore permission or restart telemetry. */ }
  // React may retain a previously decorated href. Clean every permitted owned
  // destination now, and re-evaluate at native navigation in capture phase below.
  for (const anchor of document.querySelectorAll<HTMLAnchorElement>("a[href]")) {
    const raw = anchor.getAttribute?.("href") ?? anchor.href;
    if (raw.startsWith("#")) continue;
    const target = acquisitionTarget(raw);
    if (target) {
      const before = target.toString();
      stripOptionalFields(target);
      if (target.toString() !== before) anchor.href = target.toString();
    }
  }
}
subscribeMeasurement(() => { if (!measurementAllowed()) clearOptionalState(); });
export function initializeMeasurementPrivacy(): void {
  if (typeof window === "undefined") return;
  if (!measurementAllowed()) clearOptionalState();
  if (cleanupInstalled) return;
  cleanupInstalled = true;
  const prepare = (event: Event) => {
    const anchor = event.target instanceof Element ? event.target.closest<HTMLAnchorElement>("a[href]") : null;
    const raw = anchor?.getAttribute("href");
    if (anchor && raw && !raw.startsWith("#") && acquisitionTarget(raw)) {
      anchor.href = appendAcquisitionAttribution(raw);
    }
  };
  for (const event of ["pointerdown", "focusin", "click", "auxclick"]) document.addEventListener(event, prepare, true);
  window.addEventListener("pageshow", () => { if (!measurementAllowed()) clearOptionalState(); });
}

export async function ensureAnalyticsSession(): Promise<string | null> {
  if (!measurementAllowed()) return null;
  const epoch = measurementGeneration();
  if (api.session) {
    if (analyticsOwnedApiSession && analyticsOwnedApiSession !== api.session) analyticsOwnedApiSession = null;
    return api.session;
  }
  if (!apiSessionPromise) {
    const pending = initializeAnalyticsSession().then((sessionId) => {
      if (!measurementStillAllowed(epoch)) return null;
      if (api.session) {
        if (analyticsOwnedApiSession !== api.session) analyticsOwnedApiSession = null;
        return api.session;
      }
      if (sessionId) { api.session = sessionId; analyticsOwnedApiSession = sessionId; }
      return sessionId;
    }).finally(() => { if (apiSessionPromise === pending) apiSessionPromise = null; });
    apiSessionPromise = pending;
  }
  return apiSessionPromise;
}
export type AnalyticsEventName =
  | "page_view" | "consultation_start" | "product_open" | "merchant_clickout"
  | "catalog_search" | "catalog_no_results" | "advisor_recommendation_view"
  | "advisor_product_open" | "fragrance_detail_view" | "offer_section_open"
  | "offer_section_view" | "comparison_start" | "wishlist_add" | "wishlist_remove"
  | "collection_add" | "collection_remove";
type AnalyticsContext = {
  product_id?: string; offer_id?: string; source?: string; search_term?: string; result_count?: number;
  surface?: string; related_product_id?: string; item_position?: number;
};
async function postAnalyticsPayload(payload: Record<string, unknown>, epoch: number): Promise<boolean> {
  if (!measurementStillAllowed(epoch)) return false;
  const controller = new AbortController(); activeRequests.add(controller);
  const timeoutId = setTimeout(() => controller.abort(), ANALYTICS_EVENT_TIMEOUT_MS);
  try {
    const response = await fetch(`${api.base}/analytics/events?measurement=${MEASUREMENT_PROTOCOL}`, {
      method: "POST", headers: api.headers(true), body: JSON.stringify(payload), keepalive: true, signal: controller.signal,
    });
    return response.ok;
  } catch { return false; }
  finally { clearTimeout(timeoutId); activeRequests.delete(controller); }
}
async function sendAnalyticsEvent(event: AnalyticsEventName, context: AnalyticsContext, epoch: number): Promise<void> {
  if (!measurementStillAllowed(epoch)) return;
  const apiSessionId = await ensureAnalyticsSession();
  if (!apiSessionId || !measurementStillAllowed(epoch)) return;
  const attribution = captureAcquisitionEntry();
  const payload = {
    event_id: globalThis.crypto?.randomUUID?.(), event, internal_qa: isInternalQa(),
    product_id: context.product_id, offer_id: context.offer_id, source: context.source, acquisition_source: attribution?.source,
    campaign_id: attribution?.campaign_id, content_id: attribution?.content_id,
    search_term: context.search_term, result_count: context.result_count, surface: context.surface,
    related_product_id: context.related_product_id, item_position: context.item_position,
    analytics_session_id: currentAnalyticsSessionId(),
  };
  const recorded = await postAnalyticsPayload(payload, epoch);
  if (!recorded && measurementStillAllowed(epoch) && analyticsOwnedApiSession === apiSessionId && api.session === apiSessionId) {
    api.session = null; analyticsOwnedApiSession = null;
    const freshSession = await ensureAnalyticsSession();
    if (freshSession && measurementStillAllowed(epoch)) await postAnalyticsPayload(payload, epoch);
  }
}
export function trackAnalyticsEvent(event: AnalyticsEventName, context: AnalyticsContext = {}): Promise<void> {
  if (!measurementAllowed()) return Promise.resolve();
  const epoch = measurementGeneration();
  const queued = analyticsEventQueue.then(() => sendAnalyticsEvent(event, context, epoch));
  analyticsEventQueue = queued.catch(() => { /* Analytics cannot interrupt shopping. */ });
  return analyticsEventQueue;
}
function normalizeCatalogSearchTerm(value: string): string {
  return value.normalize("NFKC").toLowerCase().replace(/\s+/g, " ").trim().slice(0, 80);
}
function looksSensitiveCatalogSearch(value: string): boolean {
  return /\S+@\S+\.\S+/.test(value) || /\b\d{7,}\b/.test(value.replace(/[\s()+-]/g, ""));
}
export function safeCatalogSearchTerm(value: string): string | null {
  const normalized = normalizeCatalogSearchTerm(value);
  return normalized.length < 2 || looksSensitiveCatalogSearch(normalized) ? null : normalized;
}
export async function trackCatalogSearch(search: string, resultCount: number): Promise<void> {
  if (!measurementAllowed()) return;
  const searchTerm = safeCatalogSearchTerm(search);
  if (!searchTerm) return;
  await trackAnalyticsEvent(resultCount === 0 ? "catalog_no_results" : "catalog_search", {
    source: "catalog_filter", search_term: searchTerm, result_count: resultCount,
  });
}
