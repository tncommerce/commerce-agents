import { api } from "./api";

export type AnalyticsEventName =
  | "page_view"
  | "consultation_start"
  | "product_open"
  | "merchant_clickout";

const recentEvents = new Map<string, number>();
const DEDUPE_WINDOW_MS = 2000;

export async function trackAnalyticsEvent(
  event: AnalyticsEventName,
  context: {
    product_id?: string;
    source?: string;
  } = {},
): Promise<void> {
  if (!api.session) return;

  const key = [event, context.product_id ?? "", context.source ?? ""].join("|");
  const now = Date.now();
  const lastSeen = recentEvents.get(key);
  if (lastSeen != null && now - lastSeen < DEDUPE_WINDOW_MS) return;
  recentEvents.set(key, now);

  // Keep the tiny in-memory de-duplication cache bounded during long sessions.
  if (recentEvents.size > 100) {
    for (const [candidate, timestamp] of recentEvents) {
      if (now - timestamp > DEDUPE_WINDOW_MS) recentEvents.delete(candidate);
    }
  }

  await api.post("/analytics/events", {
    event,
    product_id: context.product_id,
    source: context.source,
  });
}
