// Copyright 2026 Anthropic PBC
// SPDX-License-Identifier: Apache-2.0

"use client";

import {
  Greeting,
  HomeSection,
  type Starter,
  Starters,
  useCatalogIndex,
} from "web-shared";
import { fetchProducts } from "@/lib/api";
import { ADVISOR_STARTS } from "@/lib/advisorStarts";
import { fragrancePathForProduct } from "@/lib/fragranceSlug";
import type { Product } from "@/lib/types";
import ProductTile, { ProductRow } from "../ProductTile";
import LegalFooter from "../LegalFooter";
import MerchantDiscovery from "../MerchantDiscovery";

const STARTERS: Starter[] = [
  {
    icon: "search",
    prompt: ADVISOR_STARTS.summer,
  },
  {
    icon: "calendar",
    prompt: ADVISOR_STARTS.date,
  },
  {
    icon: "tag",
    prompt: ADVISOR_STARTS.alternative,
  },
  {
    icon: "gift",
    prompt: ADVISOR_STARTS.gift,
  },
  {
    icon: "signal",
    prompt: ADVISOR_STARTS.performance,
  },
  {
    icon: "spark",
    prompt: ADVISOR_STARTS.signature,
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
    <span className="max-w-2xl text-[14px] leading-5 text-(--ink-soft) sm:text-[15px] sm:leading-6">
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
  const catalog = useCatalogIndex(fetchProducts);
  const picks = featured(catalog);
  const scentCount = Object.values(catalog).filter(
    (product) =>
      String(product.product_id).startsWith("SC-") &&
      product.in_stock !== false,
  ).length;
  return (
    <div className="mx-auto flex w-full max-w-[1080px] flex-col gap-4 px-4 sm:gap-6 sm:px-6">
      <Greeting
        eyebrow="SCENTAI · Persönliche Duftberatung"
        title={
          <h1 className="max-w-3xl text-[27px] font-semibold leading-[1.12] tracking-[-0.03em] text-(--ink) sm:text-[32px] sm:leading-tight">
            Finde den Duft, der wirklich zu dir passt.
          </h1>
        }
      >
        <Brief />
      </Greeting>
      <div className="[&_button]:py-2.5 sm:[&_button]:py-3">
        <Starters items={STARTERS} />
      </div>
      <div className="flex flex-wrap gap-x-2 gap-y-1 text-[11.5px] text-(--ink-soft) sm:hidden">
        <span>Unabhängige Empfehlungen</span>
        <span>·</span>
        <span>Transparente Händlerangebote</span>
        <span>·</span>
        <a href="/transparenz" className="font-medium text-(--accent-ink)">Mehr erfahren</a>
      </div>
      <section className="hidden gap-3 sm:grid sm:grid-cols-3" aria-label="So funktioniert SCENTAI">
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
      <div className="-mt-2 hidden space-y-1 text-[12px] text-(--ink-soft) sm:block">
        <a href="/transparenz" className="font-medium text-(--accent-ink) hover:underline">
          So bewertet SCENTAI Empfehlungen und Händlerangebote
        </a>
        <p>
          Werbung: Händlerlinks können Partnerlinks sein. Bei einem Kauf kann SCENTAI eine Provision erhalten.
          Für dich soll sich der Händlerpreis dadurch nicht erhöhen.
        </p>
      </div>
      <HomeSection
        title="Starte so, wie es zu dir passt"
        subtitle="Beratung, Alternativen oder Geschenkideen"
      >
        <div className="grid gap-2.5 sm:grid-cols-3">
          <a
            href="/duftfinder"
            className="rounded-2xl border border-(--line) bg-(--card) p-4 shadow-(--shadow-sm) transition hover:border-(--accent)"
          >
            <div className="text-[13px] font-semibold text-(--ink)">
              Meinen Duft finden
            </div>
            <p className="mt-1 text-[12px] leading-5 text-(--ink-soft)">
              Nach Anlass, Budget, Duftprofil und Performance.
            </p>
          </a>
          <a
            href="/parfum-alternativen"
            className="rounded-2xl border border-(--line) bg-(--card) p-4 shadow-(--shadow-sm) transition hover:border-(--accent)"
          >
            <div className="text-[13px] font-semibold text-(--ink)">
              Alternative finden
            </div>
            <p className="mt-1 text-[12px] leading-5 text-(--ink-soft)">
              Ähnliche Duftrichtungen transparent vergleichen.
            </p>
          </a>
          <a
            href="/parfum-geschenkberater"
            className="rounded-2xl border border-(--line) bg-(--card) p-4 shadow-(--shadow-sm) transition hover:border-(--accent)"
          >
            <div className="text-[13px] font-semibold text-(--ink)">
              Parfum verschenken
            </div>
            <p className="mt-1 text-[12px] leading-5 text-(--ink-soft)">
              Mit wenigen Fragen zu einer passenden Geschenkidee.
            </p>
          </a>
        </div>
      </HomeSection>

      <div className="flex flex-wrap gap-2 text-[12.5px] text-(--ink-soft)">
        <a
          href="/duft"
          className="rounded-full border border-(--line) bg-(--card) px-3 py-1.5 font-medium text-(--accent-ink) hover:border-(--accent)"
        >
          {scentCount
            ? `${scentCount} Düfte im Sortiment ansehen`
            : "Duftkatalog ansehen"}
        </a>
        <span className="rounded-full border border-(--line) bg-(--card) px-3 py-1.5">
          Preise & Community-Bewertungen
        </span>
        <span className="rounded-full border border-(--line) bg-(--card) px-3 py-1.5">
          Empfehlungen nach Budget & Duftprofil
        </span>
        <a
          href="/vergleich"
          className="rounded-full border border-(--line) bg-(--card) px-3 py-1.5 font-medium text-(--accent-ink) hover:border-(--accent)"
        >
          Parfumvergleiche
        </a>
      </div>
      <MerchantDiscovery />

      {picks.length ? (
        <HomeSection title="Düfte entdecken" subtitle="Entdecke das Sortiment oder lass dich direkt von SCENTAI beraten">
          <div className="flex flex-col gap-2 sm:hidden">
            {picks.map((product) => (
              <ProductRow
                key={product.product_id}
                product={product}
                onOpen={(item) =>
                  window.location.assign(
                    fragrancePathForProduct(item),
                  )
                }
              />
            ))}
          </div>
          <div className="hidden grid-cols-3 gap-4 sm:grid">
            {picks.map((product) => (
              <ProductTile
                key={product.product_id}
                product={product}
                fluid
                onOpen={(item) =>
                  window.location.assign(
                    fragrancePathForProduct(item),
                  )
                }
              />
            ))}
          </div>
        </HomeSection>
      ) : null}
      <LegalFooter />
    </div>
  );
}

