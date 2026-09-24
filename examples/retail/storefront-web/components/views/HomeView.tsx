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
import FragranceVisual from "../FragranceVisual";
import ProductTile, {
  customerPriceLabel,
  ProductRating,
  ProductRow,
} from "../ProductTile";
import LegalFooter from "../LegalFooter";
import MerchantDiscovery from "../MerchantDiscovery";
import PersonalLibrarySummary from "../PersonalLibrarySummary";

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
    icon: "ticket",
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
      den du bereits magst. DUFYND vergleicht das Sortiment und empfiehlt dir
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
  const spotlight =
    catalog["SC-XERJOFF-NAXOS-100"] || picks[0];
  const scentCount = Object.values(catalog).filter(
    (product) =>
      String(product.product_id).startsWith("SC-") &&
      product.in_stock !== false,
  ).length;
  return (
    <div className="mx-auto flex w-full max-w-[1080px] flex-col gap-4 px-4 sm:gap-6 sm:px-6">
      <Greeting
        eyebrow="DUFYND · Persönliche Duftberatung"
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

      {spotlight ? (
        <section
          aria-label="DUFYND Edit"
          className="relative overflow-hidden rounded-[28px] border border-black/10 bg-[#171513] text-[#fffdf8] shadow-(--shadow-lg)"
        >
          <div
            aria-hidden
            className="pointer-events-none absolute inset-0 bg-[radial-gradient(circle_at_18%_18%,rgba(184,137,52,0.22),transparent_34%),radial-gradient(circle_at_82%_78%,rgba(255,255,255,0.08),transparent_28%)]"
          />
          <div className="relative grid gap-0 md:grid-cols-[1.05fr_0.95fr]">
            <div className="flex flex-col justify-center p-5 sm:p-7 md:p-9">
              <div className="text-[10.5px] font-semibold uppercase tracking-[0.18em] text-[#d7b56f]">
                DUFYND Edit · Launch Spotlight
              </div>
              <div className="mt-3 text-[12px] font-medium uppercase tracking-[0.11em] text-white/55">
                {spotlight.brand}
              </div>
              <h2 className="mt-1 max-w-xl text-[28px] font-semibold leading-[1.02] tracking-[-0.04em] sm:text-[36px]">
                Naxos
              </h2>
              <p className="mt-3 max-w-xl text-[13px] leading-5 text-white/68 sm:text-[14px] sm:leading-6">
                Entdecke Duftprofil, Community-Werte, Alternativen und aktuelle
                Händlerangebote in einer Ansicht.
              </p>

              <div className="mt-5 flex flex-wrap items-center gap-x-4 gap-y-2">
                <a
                  href={fragrancePathForProduct(spotlight)}
                  onClick={() =>
                    void trackAnalyticsEvent("product_open", {
                      product_id: spotlight.product_id,
                      source: "homepage_spotlight",
                    })
                  }
                  className="rounded-xl bg-[#fffdf8] px-4 py-2.5 text-[12.5px] font-semibold text-[#171513] transition hover:-translate-y-0.5"
                >
                  Naxos entdecken
                </a>
                <span className="text-[12px] font-semibold text-white/90">
                  {customerPriceLabel(spotlight)}
                </span>
                <span className="[&_*]:!text-white/65 [&_span.font-semibold]:!text-white">
                  <ProductRating product={spotlight} compact />
                </span>
              </div>
            </div>

            <a
              href={fragrancePathForProduct(spotlight)}
              aria-label="Xerjoff Naxos entdecken"
              className="group min-h-[280px] border-t border-white/10 p-4 md:min-h-[360px] md:border-l md:border-t-0 md:p-5"
            >
              <FragranceVisual
                imageUrl={spotlight.image_url}
                alt={spotlight.title}
                variant="hero"
                className="h-full min-h-[248px] w-full rounded-[22px] md:min-h-[320px]"
                priority
              />
            </a>
          </div>
        </section>
      ) : null}
      <div className="flex flex-wrap gap-x-2 gap-y-1 text-[11.5px] text-(--ink-soft) sm:hidden">
        <span>Unabhängige Empfehlungen</span>
        <span>·</span>
        <span>Transparente Händlerangebote</span>
        <span>·</span>
        <a href="/transparenz" className="font-medium text-(--accent-ink)">Mehr erfahren</a>
      </div>
      <section className="hidden gap-3 sm:grid sm:grid-cols-3" aria-label="So funktioniert DUFYND">
        <div className="rounded-2xl border border-(--line) bg-(--card) p-4 shadow-(--shadow-sm)">
          <div className="text-[13px] font-semibold text-(--ink)">Empfehlungen nach deinen Kriterien</div>
          <p className="mt-1 text-[12.5px] leading-5 text-(--ink-soft)">
            DUFYND priorisiert Passung, Preis, Verfügbarkeit und Aktualität. Partnervergütungen haben keinen Einfluss auf die Produktempfehlung oder die Reihenfolge der Händlerangebote.
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
            DUFYND verkauft nicht selbst. Zahlung, Versand, Retouren und Kaufvertrag laufen direkt über den ausgewählten Händler.
          </p>
        </div>
      </section>
      <div className="-mt-2 hidden space-y-1 text-[12px] text-(--ink-soft) sm:block">
        <a href="/transparenz" className="font-medium text-(--accent-ink) hover:underline">
          So bewertet DUFYND Empfehlungen und Händlerangebote
        </a>
        <p>
          Werbung: Händlerlinks können Partnerlinks sein. Bei einem Kauf kann DUFYND eine Provision erhalten.
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
        <a
          href="/sammlung"
          className="rounded-full border border-(--line) bg-(--card) px-3 py-1.5 font-medium text-(--accent-ink) hover:border-(--accent)"
        >
          Meine Duftsammlung
        </a>
        <a
          href="/merkliste"
          className="rounded-full border border-(--line) bg-(--card) px-3 py-1.5 font-medium text-(--accent-ink) hover:border-(--accent)"
        >
          Meine Merkliste
        </a>
      </div>
      <PersonalLibrarySummary />
      <MerchantDiscovery />

      {picks.length ? (
        <HomeSection title="Düfte entdecken" subtitle="Entdecke das Sortiment oder lass dich direkt von DUFYND beraten">
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

