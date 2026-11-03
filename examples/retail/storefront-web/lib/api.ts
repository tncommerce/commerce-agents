// Copyright 2026 Anthropic PBC
// SPDX-License-Identifier: Apache-2.0

import { AgentApi } from "web-shared";
import type {
  CartPayload,
  MerchantOffersPayload,
  MerchantPartnersPayload,
  Product,
  ProductDetails,
} from "./types";

const configuredApiUrl =
  process.env.NEXT_PUBLIC_API_URL?.trim();

function resolveApiUrl(): string {
  if (configuredApiUrl) {
    return configuredApiUrl.replace(/\/$/, "");
  }

  if (typeof window === "undefined") {
    return "http://localhost:8000";
  }

  if (
    window.location.hostname === "localhost" ||
    window.location.hostname === "127.0.0.1"
  ) {
    return "http://localhost:8000";
  }

  throw new Error(
    "NEXT_PUBLIC_API_URL is required for public DUFYND deployments.",
  );
}

const API_URL = resolveApiUrl();

export const api = new AgentApi(API_URL, "/api");

export const UNREACHABLE =
  process.env.NODE_ENV === "development"
    ? "DUFYND API auf Port 8000 nicht erreichbar. Starte lokal: uvicorn retail.api.main:app --app-dir examples --port 8000."
    : "DUFYND ist gerade kurz nicht erreichbar. Bitte versuche es in einem Moment erneut.";

const ANALYTICS_SESSION_TIMEOUT_MS = 8_000;

export async function initializeAnalyticsSession(): Promise<string | null> {
  const controller = new AbortController();
  const timeoutId = setTimeout(
    () => controller.abort(),
    ANALYTICS_SESSION_TIMEOUT_MS,
  );

  try {
    const response = await fetch(`${api.base}/session`, {
      method: "POST",
      headers: api.headers(),
      signal: controller.signal,
    });
    if (!response.ok) return null;
    const data = (await response.json()) as { session_id?: string };
    return data.session_id || null;
  } catch {
    return null;
  } finally {
    clearTimeout(timeoutId);
  }
}

const PRODUCT_CATALOG_TIMEOUT_MS = 8_000;

export async function fetchProducts(): Promise<Product[] | null> {
  const controller = new AbortController();
  const timeoutId = setTimeout(
    () => controller.abort(),
    PRODUCT_CATALOG_TIMEOUT_MS,
  );

  try {
    const response = await fetch(`${api.base}/products?category=fragrance&limit=100`, {
      headers: api.headers(),
      signal: controller.signal,
    });
    if (!response.ok) return null;
    const data = (await response.json()) as { products?: Product[] };
    return data?.products ?? null;
  } catch {
    return null;
  } finally {
    clearTimeout(timeoutId);
  }
}

export async function fetchProduct(productId: string): Promise<ProductDetails | null> {
  const controller = new AbortController();
  const timeoutId = setTimeout(() => controller.abort(), 8_000);
  try {
    const response = await fetch(`${api.base}/products/${encodeURIComponent(productId)}`, {
      headers: api.headers(),
      signal: controller.signal,
    });
    if (!response.ok) return null;
    return (await response.json()) as ProductDetails;
  } catch {
    return null;
  } finally {
    clearTimeout(timeoutId);
  }
}

const MERCHANT_OFFERS_TIMEOUT_MS = 8_000;

function record(value: unknown): value is Record<string, unknown> {
  return value !== null && typeof value === "object" && !Array.isArray(value);
}

function text(value: unknown): value is string {
  return typeof value === "string" && value.trim().length > 0;
}

function optionalText(value: unknown): boolean {
  return value == null || typeof value === "string";
}

function positiveMoney(value: unknown): value is number {
  return typeof value === "number" && Number.isFinite(value) && value > 0;
}

/**
 * Validate the public offer response before any consumer renders prices or links.
 * Reject the whole response on mismatch: silently dropping a row could change the
 * server's best-offer decision. Valid empty results remain distinct from errors.
 * This does not refresh timestamps, infer stock, or replace server-side freshness,
 * partner authorization, or clickout validation. Never rewrite a merchant URL.
 */
function isMerchantOffersPayload(
  value: unknown,
  productId: string,
): value is MerchantOffersPayload {
  if (!record(value) || value.product_id !== productId ||
      !Array.isArray(value.offers) || !text(value.affiliate_disclosure)) return false;

  if (value.offers.length === 0) return value.best_offer_id == null;
  if (!text(value.best_offer_id)) return false;

  const seen = new Set<string>();
  for (const offer of value.offers) {
    if (!record(offer) || !text(offer.offer_id) ||
        !/^[A-Za-z0-9][A-Za-z0-9._:-]*$/.test(offer.offer_id) ||
        seen.has(offer.offer_id) || offer.product_id !== productId ||
        !text(offer.merchant_id) || !text(offer.merchant_name) ||
        !positiveMoney(offer.price) || offer.currency !== "EUR" ||
        offer.in_stock !== true || typeof offer.affiliate_link !== "boolean" ||
        offer.clickout_path !== `/api/clickout/${offer.offer_id}` ||
        !text(offer.last_updated_at) || !Number.isFinite(Date.parse(offer.last_updated_at)) ||
        !optionalText(offer.merchant_product_id) || !optionalText(offer.shipping_label) ||
        !optionalText(offer.variant_label)) return false;

    if (offer.shipping_cost != null &&
        (typeof offer.shipping_cost !== "number" || !Number.isFinite(offer.shipping_cost) ||
         offer.shipping_cost < 0)) return false;
    if (offer.total_price != null && !positiveMoney(offer.total_price)) return false;
    seen.add(offer.offer_id);
  }
  return seen.has(value.best_offer_id);
}

export async function fetchMerchantOffers(productId: string): Promise<MerchantOffersPayload | null> {
  const controller = new AbortController();
  const timeoutId = setTimeout(
    () => controller.abort(),
    MERCHANT_OFFERS_TIMEOUT_MS,
  );

  try {
    const response = await fetch(
      `${API_URL}/api/merchant-offers/${encodeURIComponent(productId)}`,
      {
        headers: api.headers(),
        signal: controller.signal,
      },
    );
    if (!response.ok) return null;
    const value: unknown = await response.json();
    return isMerchantOffersPayload(value, productId) ? value : null;
  } catch {
    return null;
  } finally {
    clearTimeout(timeoutId);
  }
}

export function merchantClickoutUrl(path: string): string {
  return `${API_URL}${path}`;
}

const MERCHANT_PARTNERS_TIMEOUT_MS = 8_000;

export async function fetchMerchantPartners(): Promise<MerchantPartnersPayload | null> {
  const controller = new AbortController();
  const timeoutId = setTimeout(
    () => controller.abort(),
    MERCHANT_PARTNERS_TIMEOUT_MS,
  );

  try {
    const response = await fetch(`${api.base}/merchant-partners`, {
      headers: api.headers(),
      signal: controller.signal,
    });
    if (!response.ok) return null;
    return (await response.json()) as MerchantPartnersPayload;
  } catch {
    return null;
  } finally {
    clearTimeout(timeoutId);
  }
}

export function merchantPartnerClickoutUrl(
  merchantId: string,
): string {
  return `${API_URL}/api/merchant-partners/${encodeURIComponent(
    merchantId,
  )}/clickout`;
}

export async function addToCart(productId: string, quantity = 1): Promise<CartPayload | null> {
  const data = await api.post<{ cart: CartPayload }>("/cart/add", { product_id: productId, quantity });
  return data?.cart ?? null;
}
