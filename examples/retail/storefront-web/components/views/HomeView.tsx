// Copyright 2026 Anthropic PBC
// SPDX-License-Identifier: Apache-2.0

"use client";

import { useEffect, useState } from "react";
import {
  ArrivingPanel,
  estimateOf,
  Greeting,
  greeting,
  HomeSection,
  type Order,
  plural,
  type Starter,
  Starters,
  upcoming,
  useCatalogIndex,
  useStoreFrame,
} from "web-shared";
import { fetchProducts } from "@/lib/api";
import { NOUNS, OrderThumb } from "@/lib/orders";
import type { Product } from "@/lib/types";
import ProductTile from "../ProductTile";

const STARTERS: Starter[] = [
  {
    icon: "search",
    prompt: "Ich suche einen frischen Sommerduft unter 60 €.",
  },
  {
    icon: "home",
    prompt: "Ich suche einen eleganten Duft für ein Date unter 100 €.",
  },
  {
    icon: "tag",
    prompt: "Finde mir eine gute Alternative zu Louis Vuitton Imagination.",
  },
  {
    icon: "edit",
    prompt: "Ich suche einen Duft mit starker Haltbarkeit und Ausstrahlung.",
  },
];

/** What the store is featuring: labelled bestseller or new, photographed ones first. */
function featured(catalog: Record<string, Product>): Product[] {
  return Object.values(catalog)
    .filter(
      (product) =>
        String(product.product_id).startsWith("SC-") &&
        product.in_stock !== false &&
        String(product.image_url ?? "").includes("/products/pilot/"),
    )
    .sort(
      (a, b) =>
        Number(b.review_count ?? 0) - Number(a.review_count ?? 0),
    )
;
}

function Brief({ orders: _orders }: { orders: Order[] | null }) {
  return (
    <span className="max-w-2xl text-[15px] leading-6 text-(--ink-soft)">
      Beschreibe, was du suchst – Duftprofil, Anlass, Budget oder einen Duft,
      den du bereits magst. SCENTAI vergleicht das Sortiment und empfiehlt dir
      passende Optionen.
    </span>
  );
}

/** The clock is read after mount, so the prerendered page never disagrees with the browser's day. */
function useNow(): Date | null {
  const [now, setNow] = useState<Date | null>(null);
  useEffect(() => setNow(new Date()), []);
  return now;
}

export default function HomeView({
  shopperName,
  orders,
  ordersFailed,
  onSeeOrders,
}: {
  shopperName: string;
  orders: Order[] | null;
  ordersFailed: boolean;
  onSeeOrders: () => void;
}) {
  const { ask } = useStoreFrame();
  const catalog = useCatalogIndex(fetchProducts);
  const picks = featured(catalog);
  const now = useNow();
  return (
    <div className="mx-auto flex w-full max-w-[1080px] flex-col gap-6 px-4 sm:px-6">
      <Greeting
        eyebrow="SCENTAI · Persönliche Duftberatung"
        title={
          <h1 className="max-w-3xl text-[32px] font-semibold leading-tight tracking-[-0.03em] text-(--ink)">
            Finde den Duft, der wirklich zu dir passt.
          </h1>
        }
      >
        <Brief orders={orders} />
      </Greeting>
      <Starters items={STARTERS} />
      {picks.length ? (
        <HomeSection title="Beliebte Düfte entdecken" subtitle="Entdecke ausgewählte Düfte oder lass dich direkt von SCENTAI beraten">
          <div className="grid grid-cols-1 gap-4 sm:grid-cols-3">
            {picks.map((product) => (
              <ProductTile key={product.product_id} product={product} fluid onOpen={(item) => ask(`Erzähl mir mehr über ${item.title} und für wen dieser Duft besonders interessant ist.`)} />
            ))}
          </div>
        </HomeSection>
      ) : null}
    </div>
  );
}

