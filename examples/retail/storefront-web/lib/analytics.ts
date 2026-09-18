import { api } from "./api";

export type AnalyticsEventName =
  | "page_view"
  | "consultation_start"
  | "product_open"
  | "merchant_clickout";

export async function trackAnalyticsEvent(
  event: AnalyticsEventName,
  context: {
    product_id?: string;
    source?: string;
  } = {},
): Promise<void> {
  if (!api.session) return;
  await api.post("/analytics/events", {
    event,
    product_id: context.product_id,
    source: context.source,
  });
}
