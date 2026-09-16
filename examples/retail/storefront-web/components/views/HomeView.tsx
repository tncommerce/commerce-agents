// Copyright 2026 Anthropic PBC
// SPDX-License-Identifier: Apache-2.0

"use client";

import {
  Greeting,
  HomeSection,
  type Starter,
  Starters,
  useCatalogIndex,
  useStoreFrame,
} from "web-shared";
import { fetchProducts } from "@/lib/api";
import type { Product } from "@/lib/types";
import ProductTile from "../ProductTile";
import LegalFooter from "../LegalFooter";

const STARTERS: Starter[] = [
  {
    icon: "search",
    prompt: "Ich suche einen frischen Sommerduft unter 60 €.",
  },
  {
    icon: "calendar",
    prompt: "Ich suche einen eleganten Duft für ein Date unter 100 €.",
  },
  {
    icon: "tag",
    prompt: "Finde mir eine gute Alternative zu Louis Vuitton Imagination.",
  },
  {
    icon: "signal",
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

function Brief() {
  return (
    <span className="max-w-2xl text-[15px] leading-6 text-(--ink-soft)">
      Beschreibe, was du suchst – Duftprofil, Anlass, Budget oder einen Duft,
      den du bereits magst. SCENTAI vergleicht das Sortiment und empfiehlt dir
      passende Optionen.
    </span>
  );
}

export default function HomeView({
  shopperName: _shopperName,
}: {
  shopperName: string;
}) {
  const { ask } = useStoreFrame();
  const catalog = useCatalogIndex(fetchProducts);
  const picks = featured(catalog);
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
        <Brief />
      </Greeting>
      <Starters items={STARTERS} />
      <section className="grid gap-3 sm:grid-cols-3" aria-label="So funktioniert SCENTAI">
        <div className="rounded-2xl border border-(--line) bg-(--card) p-4 shadow-(--shadow-sm)">
          <div className="text-[13px] font-semibold text-(--ink)">Empfehlungen nach deinen Kriterien</div>
          <p className="mt-1 text-[12.5px] leading-5 text-(--ink-soft)">
            SCENTAI priorisiert Passung, Preis, Verfügbarkeit und Aktualität. Partnervergütungen haben keinen Einfluss auf die Produktempfehlung oder die Reihenfolge der Händlerangebote.
          </p>
        </div>
        <div className="rounded-2xl border border-(--line) bg-(--card) p-4 shadow-(--shadow-sm)">
          <div className="text-[13px] font-semibold text-(--ink)">Aktuelle Händlerangebote</div>
          <p className="mt-1 text-[12.5px] leading-5 text-(--ink-soft)">
            Kaufbare Angebote werden getrennt von den Duftdaten gepflegt und nach Preis, Verfügbarkeit und Aktualität bewertet.
          </p>
        </div>
        <div className="rounded-2xl border border-(--line) bg-(--card) p-4 shadow-(--shadow-sm)">
          <div className="text-[13px] font-semibold text-(--ink)">Kauf direkt beim Händler</div>
          <p className="mt-1 text-[12.5px] leading-5 text-(--ink-soft)">
            SCENTAI verkauft nicht selbst. Zahlung, Versand, Retouren und Kaufvertrag laufen direkt über den ausgewählten Händler.
          </p>
        </div>
      </section>
      <div className="-mt-2 space-y-1 text-[12px] text-(--ink-soft)">
        <a href="/transparenz" className="font-medium text-(--accent-ink) hover:underline">
          So bewertet SCENTAI Empfehlungen und Händlerangebote
        </a>
        <p>
          Werbung: Händlerlinks können Partnerlinks sein. Bei einem Kauf kann SCENTAI eine Provision erhalten.
          Für dich soll sich der Händlerpreis dadurch nicht erhöhen.
        </p>
      </div>
      {picks.length ? (
        <div className="flex flex-wrap gap-2 text-[12.5px] text-(--ink-soft)">
          <span className="rounded-full border border-(--line) bg-(--card) px-3 py-1.5">{picks.length} Düfte im Sortiment</span>
          <span className="rounded-full border border-(--line) bg-(--card) px-3 py-1.5">Preise & Community-Bewertungen</span>
          <span className="rounded-full border border-(--line) bg-(--card) px-3 py-1.5">Empfehlungen nach Budget & Duftprofil</span>
        </div>
      ) : null}
      {picks.length ? (
        <HomeSection title="Düfte entdecken" subtitle="Entdecke das Sortiment oder lass dich direkt von SCENTAI beraten">
          <div className="grid grid-cols-1 gap-4 sm:grid-cols-3">
            {picks.map((product) => (
              <ProductTile key={product.product_id} product={product} fluid onOpen={(item) => ask(`Erzähl mir mehr über ${item.title} und für wen dieser Duft besonders interessant ist.`)} />
            ))}
          </div>
        </HomeSection>
      ) : null}
      <LegalFooter />
    </div>
  );
}

