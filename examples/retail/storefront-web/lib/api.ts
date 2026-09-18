// Copyright 2026 Anthropic PBC
// SPDX-License-Identifier: Apache-2.0

import { AgentApi } from "web-shared";
import type { CartPayload, MerchantOffersPayload, Product, ProductDetails } from "./types";

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
    "NEXT_PUBLIC_API_URL is required for public SCENTAI deployments.",
  );
}

const API_URL = resolveApiUrl();

export const api = new AgentApi(API_URL, "/api");

export const UNREACHABLE =
  process.env.NODE_ENV === "development"
    ? "SCENTAI API auf Port 8000 nicht erreichbar. Starte lokal: uvicorn retail.api.main:app --app-dir examples --port 8000."
    : "SCENTAI ist gerade kurz nicht erreichbar. Bitte versuche es in einem Moment erneut.";

export async function fetchProducts(): Promise<Product[] | null> {
  const data = await api.get<{ products: Product[] }>("/products", { limit: "100" });
  return data?.products ?? null;
}

export function fetchProduct(productId: string): Promise<ProductDetails | null> {
  return api.get<ProductDetails>(`/products/${encodeURIComponent(productId)}`);
}

export function fetchMerchantOffers(productId: string): Promise<MerchantOffersPayload | null> {
  return api.get<MerchantOffersPayload>(`/merchant-offers/${encodeURIComponent(productId)}`);
}

export function merchantClickoutUrl(path: string): string {
  return `${API_URL}${path}`;
}

export async function addToCart(productId: string, quantity = 1): Promise<CartPayload | null> {
  const data = await api.post<{ cart: CartPayload }>("/cart/add", { product_id: productId, quantity });
  return data?.cart ?? null;
}
