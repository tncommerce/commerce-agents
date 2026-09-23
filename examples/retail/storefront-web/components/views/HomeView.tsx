// Copyright 2026 Anthropic PBC
// SPDX-License-Identifier: Apache-2.0

"use client";

import {
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
  const hero = picks[0] ?? null;
  const scentCount = Object.values(catalog).filter(
    (product) =>
      String(product.product_id).startsWith("SC-") &&
      product.in_stock !== false,
  ).length;
  return (
    <div className="mx-auto flex w-full max-w-[1080px] flex-col gap-4 px-4 sm:gap-6 sm:px-6">
      <section className="relative overflow-hidden rounded-[28px] border border-[#d7c7a2]/45 bg-[#15120f] text-white shadow-[0_24px_80px_-38px_rgba(40,27,10,0.75)] sm:rounded-[34px]">
        <div
          aria-hidden
          className="pointer-events-none absolute inset-0 bg-[radial-gradient(circle_at_78%_35%,rgba(212,174,101,0.26),transparent_34%),radial-gradient(circle_at_12%_0%,rgba(255,255,255,0.08),transparent_28%),linear-gradient(135deg,#17130f_0%,#0e0c0a_58%,#211a11_100%)]"
        />
        <div className="relative grid min-h-[390px] items-center gap-7 px-5 py-7 sm:px-8 sm:py-9 lg:grid-cols-[1.08fr_0.92fr] lg:px-10 lg:py-10">
          <div className="max-w-2xl">
            <div className="text-[10.5px] font-semibold uppercase tracking-[0.19em] text-[#d9bd82]">
              DUFYND · Fragrance Discovery
            </div>
            <h1 className="mt-4 max-w-[720px] text-[38px] font-semibold leading-[0.98] tracking-[-0.045em] text-[#fffaf0] sm:text-[52px] lg:text-[60px]">
              Finde den Duft, der wirklich zu dir passt.
            </h1>
            <p className="mt-5 max-w-xl text-[14px] leading-6 text-white/68 sm:text-[15px]">
              Entdecke Duftprofile, vergleiche Alternativen und finde aktuelle Händlerangebote – kuratiert statt überladen.
            </p>
            <div className="mt-6 flex flex-wrap gap-2.5">
              <a
                href="#dufynd-starters"
                className="rounded-xl bg-[#c79b4c] px-4 py-2.5 text-[13px] font-semibold text-[#15120f] transition hover:brightness-105"
              >
                Duftberatung starten
              </a>
              <a
                href="/duft"
                className="rounded-xl border border-white/18 bg-white/[0.06] px-4 py-2.5 text-[13px] font-semibold text-white transition hover:border-[#d9bd82]/70 hover:bg-white/[0.10]"
              >
                Düfte entdecken
              </a>
            </div>
            <div className="mt-7 flex flex-wrap gap-x-4 gap-y-1 text-[10.5px] uppercase tracking-[0.1em] text-white/42">
              <span>Duftprofile</span>
              <span>Vergleiche</span>
              <span>Alternativen</span>
              <span>Händlerangebote</span>
            </div>
          </div>

          <div className="relative mx-auto w-full max-w-[380px] lg:max-w-[420px]">
            <div
              aria-hidden
              className="absolute inset-x-[12%] bottom-[4%] top-[10%] rounded-full bg-[#d6aa58]/15 blur-3xl"
            />
            <div className="relative overflow-hidden rounded-[30px] border border-white/10 bg-[linear-gradient(145deg,rgba(255,250,240,0.98),rgba(231,214,180,0.91))] p-4 shadow-[0_24px_65px_-28px_rgba(0,0,0,0.85)] sm:p-5">
              {hero?.image_url ? (
                <a
                  href={fragrancePathForProduct(hero)}
                  className="group block"
                  aria-label={`${hero.brand} ${hero.title} ansehen`}
                >
                  <div className="flex aspect-[4/4.2] items-center justify-center overflow-hidden rounded-[22px] bg-[radial-gradient(circle_at_50%_42%,#fffdf8_0%,#f4e9d2_58%,#e7d5b4_100%)]">
                    <img
                      src={hero.image_url}
                      alt={hero.title}
                      className="h-full w-full scale-[1.12] object-contain transition duration-500 group-hover:scale-[1.16]"
                    />
                  </div>
                  <div className="px-1 pb-1 pt-4 text-[#17130f]">
                    <div className="text-[9.5px] font-semibold uppercase tracking-[0.15em] text-[#765b2b]">
                      Im Fokus
                    </div>
                    <div className="mt-1 text-[11px] uppercase tracking-[0.08em] text-[#6b6255]">
                      {hero.brand}
                    </div>
                    <div className="mt-0.5 line-clamp-2 text-[19px] font-semibold leading-tight tracking-[-0.02em]">
                      {hero.title}
                    </div>
                    <div className="mt-3 text-[11.5px] font-semibold text-[#765b2b]">
                      Duft entdecken →
                    </div>
                  </div>
                </a>
              ) : (
                <div className="grid aspect-square place-items-center text-center text-[#17130f]">
                  <div>
                    <div className="text-[12px] font-semibold uppercase tracking-[0.18em] text-[#765b2b]">
                      DUFYND
                    </div>
                    <div className="mt-2 text-[24px] font-semibold">
                      Discover your signature scent.
                    </div>
                  </div>
                </div>
              )}
            </div>
          </div>
        </div>
      </section>
      <div id="dufynd-starters" className="scroll-mt-5 [&_button]:py-2.5 sm:[&_button]:py-3">
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

