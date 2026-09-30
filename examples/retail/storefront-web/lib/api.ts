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

export async function fetchProducts(): Promise<Product[] | null> {
  const data = await api.get<{ products: Product[] }>("/products", { limit: "100" });
  return data?.products ?? null;
}

export function fetchProduct(productId: string): Promise<ProductDetails | null> {
  return api.get<ProductDetails>(`/products/${encodeURIComponent(productId)}`);
}

const MERCHANT_OFFERS_TIMEOUT_MS = 8_000;

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
    return (await response.json()) as MerchantOffersPayload;
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
