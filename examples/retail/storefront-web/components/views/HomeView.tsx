// Copyright 2026 Anthropic PBC
// SPDX-License-Identifier: Apache-2.0

"use client";

import type { PointerEvent } from "react";

import staticCatalog from "../../../data/catalog.json";

import {
  HomeSection,
  type Starter,
  Starters,
  useCatalogIndex,
} from "web-shared";
import { fetchProducts } from "@/lib/api";
import { trackAnalyticsEvent } from "@/lib/analytics";
import { ADVISOR_STARTS } from "@/lib/advisorStarts";
import { fragrancePathForProduct } from "@/lib/fragranceSlug";
import type { Product } from "@/lib/types";
import FragranceVisual from "../FragranceVisual";
import FragranceModel3D from "../FragranceModel3D";
import ProductTile, {
  ProductRating,
  ProductRow,
} from "../ProductTile";
import LegalFooter from "../LegalFooter";
import MerchantDiscovery from "../MerchantDiscovery";
import PersonalLibrarySummary from "../PersonalLibrarySummary";

const STATIC_CATALOG: Record<string, Product> = Object.fromEntries(
  (staticCatalog.products as unknown as Product[]).map((product) => [
    product.product_id,
    product,
  ]),
);

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
function updateHeroLight(event: PointerEvent<HTMLElement>) {
  if (event.pointerType === "touch") return;
  const bounds = event.currentTarget.getBoundingClientRect();
  const x = Math.min(1, Math.max(0, (event.clientX - bounds.left) / bounds.width));
  const y = Math.min(1, Math.max(0, (event.clientY - bounds.top) / bounds.height));
  event.currentTarget.style.setProperty("--dufynd-hero-x", `${(x * 100).toFixed(1)}%`);
  event.currentTarget.style.setProperty("--dufynd-hero-y", `${(y * 100).toFixed(1)}%`);
}

function resetHeroLight(event: PointerEvent<HTMLElement>) {
  event.currentTarget.style.setProperty("--dufynd-hero-x", "68%");
  event.currentTarget.style.setProperty("--dufynd-hero-y", "34%");
}

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


export default function HomeView({
  shopperName: _shopperName,
}: {
  shopperName: string;
}) {
  const liveCatalog = useCatalogIndex(fetchProducts);
  const catalog = Object.keys(liveCatalog).length
    ? liveCatalog
    : STATIC_CATALOG;
  const picks = featured(catalog);
  const spotlight =
    catalog["SC-XERJOFF-NAXOS-100"] || picks[0];
  const spotlightName = spotlight
    ? String(
        spotlight.attributes?.canonical_name ||
          spotlight.title ||
          "Duft",
      ).replace(/\s+(Eau de Parfum|Eau de Toilette|Parfum|Extrait).*$/i, "")
    : "Duft";
  const scentCount = Object.values(catalog).filter(
    (product) =>
      String(product.product_id).startsWith("SC-") &&
      product.in_stock !== false,
  ).length;
  return (
    <div className="mx-auto flex w-full max-w-[1180px] flex-col gap-4 px-4 sm:gap-6 sm:px-6">
      {spotlight ? (
        <section
          aria-label="DUFYND Edit"
          className="dufynd-immersive-hero relative overflow-hidden rounded-[30px] border border-white/10 text-[#fffdf8]"
          onPointerMove={updateHeroLight}
          onPointerLeave={resetHeroLight}
        >
          <div aria-hidden className="dufynd-hero-atmosphere pointer-events-none absolute inset-0" />
          <div aria-hidden className="dufynd-hero-aurora pointer-events-none absolute" />
          <div aria-hidden className="dufynd-hero-orbit pointer-events-none absolute" />
          <div aria-hidden className="dufynd-hero-particles pointer-events-none absolute inset-0" />
          <div aria-hidden className="dufynd-hero-vignette pointer-events-none absolute inset-0" />
          <div className="relative z-10 grid gap-0 md:grid-cols-[1.02fr_0.98fr]">
            <div className="flex flex-col justify-center p-5 sm:p-8 md:p-10 lg:p-12">
              <div className="mb-4 inline-flex w-fit items-center gap-2 rounded-full border border-white/12 bg-white/[0.055] px-3 py-1.5 text-[10px] font-semibold uppercase tracking-[0.19em] text-[#e5c782] backdrop-blur-md">
                <span className="h-1.5 w-1.5 rounded-full bg-[#d8ad55] shadow-[0_0_14px_rgba(216,173,85,0.9)]" />
                DUFYND · Persönliche Duftberatung
              </div>
              <div className="mt-2 text-[11px] font-medium uppercase tracking-[0.14em] text-white/48">
                Duft entdecken. Vergleichen. Sicherer entscheiden.
              </div>
              <h1 className="mt-2 max-w-2xl text-[31px] font-semibold leading-[0.98] tracking-[-0.045em] sm:text-[44px] lg:text-[54px]">
                Finde den Duft, der wirklich zu dir passt.
              </h1>
              <p className="mt-3 max-w-xl text-[13px] leading-5 text-white/72 sm:mt-5 sm:text-[14px] sm:leading-6">
                Beschreibe Duftprofil, Anlass oder Budget. DUFYND verbindet
                Duftberatung, Community-Daten, Alternativen und aktuelle
                Händlerangebote in einem klaren Erlebnis.
              </p>
              <div className="mt-4 hidden flex-wrap gap-2 text-[10.5px] font-medium text-white/58 sm:flex">
                <span className="rounded-full border border-white/10 bg-black/15 px-2.5 py-1 backdrop-blur-sm">Duftprofil</span>
                <span className="rounded-full border border-white/10 bg-black/15 px-2.5 py-1 backdrop-blur-sm">Alternativen</span>
                <span className="rounded-full border border-white/10 bg-black/15 px-2.5 py-1 backdrop-blur-sm">Preisvergleich</span>
              </div>

              <div className="mt-4 flex flex-wrap items-center gap-x-3 gap-y-3 sm:mt-6">
                <a
                  href="/duftfinder"
                  className="dufynd-hero-primary rounded-xl bg-[#fffdf8] px-4 py-2.5 text-[12.5px] font-semibold text-[#171513] transition hover:-translate-y-0.5"
                >
                  Meinen Duft finden
                </a>
                <a
                  href={fragrancePathForProduct(spotlight)}
                  onClick={() =>
                    void trackAnalyticsEvent("product_open", {
                      product_id: spotlight.product_id,
                      source: "homepage_spotlight",
                    })
                  }
                  className="rounded-xl border border-white/14 bg-white/[0.055] px-4 py-2.5 text-[12.5px] font-semibold text-white/88 backdrop-blur-md transition hover:-translate-y-0.5 hover:bg-white/[0.09]"
                >
                  {spotlightName} entdecken
                </a>
                <span className="[&_*]:!text-white/65 [&_span.font-semibold]:!text-white">
                  <ProductRating product={spotlight} compact />
                </span>
              </div>
            </div>

            <a
              href={fragrancePathForProduct(spotlight)}
              aria-label={`${spotlight.brand || ""} ${spotlightName} entdecken`.trim()}
              className="dufynd-hero-product group relative min-h-[260px] sm:min-h-[320px] overflow-hidden border-t border-white/10 md:min-h-[430px] md:border-l md:border-t-0"
            >
              {spotlight.attributes?.product_model_3d_url || spotlight.attributes?.product_cutout_url ? (
                <FragranceModel3D
                  modelUrl={spotlight.attributes?.product_model_3d_url}
                  imageUrl={spotlight.image_url}
                  cutoutUrl={spotlight.attributes?.product_cutout_url}
                  alt={spotlight.title}
                  className="h-full min-h-[260px] sm:min-h-[320px] w-full md:min-h-[430px]"
                  priority
                />
              ) : (
                <div className="dufynd-editorial-media relative h-full min-h-[260px] sm:min-h-[320px] w-full md:min-h-[430px]">
                  {spotlight.image_url ? (
                    // eslint-disable-next-line @next/next/no-img-element
                    <img
                      src={spotlight.image_url}
                      alt={`${spotlight.title} – stilisierte DUFYND-Inszenierung`}
                      fetchPriority="high"
                      decoding="async"
                      className="h-full min-h-[260px] sm:min-h-[320px] w-full object-cover md:min-h-[430px]"
                    />
                  ) : null}
                  <span
                    aria-hidden
                    className="pointer-events-none absolute inset-0 bg-[linear-gradient(90deg,rgba(23,21,19,0.24),transparent_28%),linear-gradient(0deg,rgba(23,21,19,0.12),transparent_30%)] md:bg-[linear-gradient(90deg,rgba(23,21,19,0.32),transparent_36%)]"
                  />
                </div>
              )}
              <div className="pointer-events-none absolute inset-x-0 bottom-0 z-20 flex items-end justify-between bg-gradient-to-t from-black/55 via-black/10 to-transparent px-5 pb-4 pt-14 sm:px-6">
                <div>
                  <div className="text-[9.5px] font-semibold uppercase tracking-[0.18em] text-[#e3c47f]">
                    DUFYND Spotlight
                  </div>
                  <div className="mt-0.5 text-[12px] font-semibold text-white/90">
                    {spotlight.brand} · {spotlightName}
                  </div>
                </div>
                <span className="rounded-full border border-white/12 bg-black/20 px-2.5 py-1 text-[9px] font-semibold uppercase tracking-[0.12em] text-white/64 backdrop-blur-md">
                  {spotlight.attributes?.product_model_3d_url ? "3D-Ansicht" : "Immersive Ansicht"}
                </span>
              </div>
            </a>
          </div>
        </section>
      ) : null}
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

