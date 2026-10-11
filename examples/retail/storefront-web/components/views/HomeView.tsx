// Copyright 2026 Anthropic PBC
// SPDX-License-Identifier: Apache-2.0

"use client";


import staticCatalog from "../../../data/catalog.json";

import {
  HomeSection,
  type Starter,
  Starters,
  useCatalogIndex,
} from "web-shared";
import { fetchProducts } from "@/lib/api";
import { appendAcquisitionAttribution, trackAnalyticsEvent } from "@/lib/analytics";
import { ADVISOR_STARTS } from "@/lib/advisorStarts";
import { fragrancePathForProduct } from "@/lib/fragranceSlug";
import {
  catalogAudienceFor,
  fragranceMatchesAudience,
  getLiveFragranceByProductId,
  visualWorldFor,
} from "@/lib/fragranceCatalog";
import type { Product } from "@/lib/types";
import AcquisitionInternalLink from "../AcquisitionInternalLink";
import DiscoveryIntro from "../DiscoveryIntro";
import ProductTile, {
  ProductImage,
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

/** Keep the homepage preview short and represent the available audiences. */
function featured(catalog: Record<string, Product>): Product[] {
  const candidates = Object.values(catalog)
    .filter((product) => {
      if (
        !String(product.product_id).startsWith("SC-") ||
        product.in_stock === false
      ) {
        return false;
      }

      const fragrance = getLiveFragranceByProductId(
        String(product.product_id),
      );

      return Boolean(
        fragrance?.presentation_visual?.url ||
          fragrance?.preferred_visual?.url ||
          product.image_url,
      );
    })
    .sort(
      (a, b) =>
        Number(b.review_count ?? 0) - Number(a.review_count ?? 0),
    );

  const picks: Product[] = [];
  const chosen = new Set<string>();
  const add = (product: Product) => {
    const id = String(product.product_id);
    if (chosen.has(id)) return;
    chosen.add(id);
    picks.push(product);
  };

  for (const audience of ["women", "unisex", "men"] as const) {
    candidates
      .filter((product) => {
        const fragrance = getLiveFragranceByProductId(
          String(product.product_id),
        );
        return fragrance
          ? fragranceMatchesAudience(fragrance, audience)
          : false;
      })
      .slice(0, 2)
      .forEach(add);
  }

  for (const product of candidates) {
    if (picks.length >= 6) break;
    add(product);
  }

  return picks.slice(0, 6);
}

const AUDIENCE_DISCOVERY = [
  { key: "women", label: "Damen", eyebrow: "Für sie" },
  { key: "men", label: "Herren", eyebrow: "Für ihn" },
  { key: "unisex", label: "Unisex", eyebrow: "Für alle" },
] as const;

function homeVisualWorldFor(product: Product | undefined) {
  if (!product) return "ember" as const;

  const fragrance = getLiveFragranceByProductId(
    String(product.product_id),
  );

  return fragrance ? visualWorldFor(fragrance) : "ember";
}

function audiencePreviewProducts(catalog: Record<string, Product>) {
  const used = new Set<string>();

  return AUDIENCE_DISCOVERY.map((audience) => {
    const matches = Object.values(catalog)
      .filter((product) => {
        if (
          !String(product.product_id).startsWith("SC-") ||
          product.in_stock === false
        ) {
          return false;
        }

        const fragrance = getLiveFragranceByProductId(
          String(product.product_id),
        );

        if (
          !fragrance ||
          !fragranceMatchesAudience(fragrance, audience.key)
        ) {
          return false;
        }

        return Boolean(
          fragrance.presentation_visual?.url ||
            fragrance.preferred_visual?.url ||
            product.image_url,
        );
      })
      .sort((a, b) => {
        const aTargets =
          getLiveFragranceByProductId(
            String(a.product_id),
          )?.target_groups.length ?? Number.MAX_SAFE_INTEGER;
        const bTargets =
          getLiveFragranceByProductId(
            String(b.product_id),
          )?.target_groups.length ?? Number.MAX_SAFE_INTEGER;

        return (
          aTargets - bTargets ||
          Number(b.review_count ?? 0) - Number(a.review_count ?? 0)
        );
      });

    const product =
      matches.find(
        (candidate) => !used.has(String(candidate.product_id)),
      ) || matches[0];

    if (product) {
      used.add(String(product.product_id));
    }

    return { ...audience, product };
  });
}


export default function HomeView({
  shopperName: _shopperName,
  sessionSettled,
}: {
  shopperName: string;
  sessionSettled: boolean;
}) {
  const liveCatalog = useCatalogIndex(fetchProducts);
  const loadedCatalog = Object.keys(liveCatalog).length
    ? liveCatalog
    : STATIC_CATALOG;
  const catalog = Object.fromEntries(
    Object.entries(loadedCatalog).filter(([id]) => getLiveFragranceByProductId(id)),
  );
  const picks = featured(catalog);
  const audiencePreviews = audiencePreviewProducts(catalog);
  const scentCount = Object.values(catalog).filter(
    (product) =>
      String(product.product_id).startsWith("SC-") &&
      product.in_stock !== false &&
      Boolean(
        getLiveFragranceByProductId(
          String(product.product_id),
        ),
      ),
  ).length;
  const audienceCounts = Object.values(catalog).reduce(
    (counts, product) => {
      if (
        !String(product.product_id).startsWith("SC-") ||
        product.in_stock === false
      ) {
        return counts;
      }

      const fragrance = getLiveFragranceByProductId(
        String(product.product_id),
      );

      const audience = fragrance
        ? catalogAudienceFor(fragrance.target_groups)
        : null;
      if (audience) {
        counts[audience] += 1;
      }

      return counts;
    },
    { women: 0, men: 0, unisex: 0 },
  );
  return (
    <div className="mx-auto flex w-full max-w-[1180px] flex-col gap-4 px-4 sm:gap-6 sm:px-6">
      <DiscoveryIntro />

      <section
        aria-labelledby="dufynd-home-search-heading"
        className="rounded-[22px] border border-(--line) bg-(--card) p-3.5 shadow-(--shadow-sm) sm:p-4"
      >
        <div className="grid gap-3 lg:grid-cols-[0.72fr_1.28fr] lg:items-center">
          <div>
            <div className="text-[9.5px] font-semibold uppercase tracking-[0.13em] text-(--accent-ink)">
              Direkt entdecken
            </div>
            <h2
              id="dufynd-home-search-heading"
              className="mt-1 text-[16px] font-semibold tracking-[-0.02em] text-(--ink)"
            >
              Schon einen Duft oder eine Marke im Kopf?
            </h2>
            <p className="mt-1 text-[11.5px] leading-5 text-(--ink-soft)">
              Suche direkt im aktuellen DUFYND-Katalog oder öffne den Vergleich.
            </p>
          </div>

          <div className="flex flex-col gap-2 sm:flex-row sm:items-center">
            <form
              action="/duft"
              onSubmit={(event) => {
                event.preventDefault();
                const query = String(
                  new FormData(event.currentTarget).get("q") || "",
                );
                const target = new URL("/duft", window.location.origin);
                target.searchParams.set("q", query);
                window.location.assign(
                  appendAcquisitionAttribution(target.toString()),
                );
              }}
              method="get"
              role="search"
              aria-label="DUFYND Duftkatalog durchsuchen"
              className="flex min-w-0 flex-1 gap-2"
            >
              <label htmlFor="dufynd-home-search" className="sr-only">
                Duft oder Marke suchen
              </label>
              <input
                id="dufynd-home-search"
                name="q"
                type="search"
                maxLength={80}
                placeholder="z. B. Naxos, Dior oder Vanille"
                className="min-w-0 flex-1 rounded-xl border border-(--line) bg-(--surface) px-3.5 py-2.5 text-[12.5px] text-(--ink) outline-none transition placeholder:text-(--ink-faint) focus:border-(--accent)"
              />
              <button
                type="submit"
                className="shrink-0 rounded-xl bg-(--ink) px-4 py-2.5 text-[12px] font-semibold text-(--surface) transition hover:opacity-90"
              >
                Suchen
              </button>
            </form>

            <AcquisitionInternalLink
              href="/vergleich"
              className="rounded-xl border border-(--line) bg-(--surface) px-4 py-2.5 text-center text-[12px] font-semibold text-(--accent-ink) transition hover:border-(--accent)"
            >
              Düfte vergleichen
            </AcquisitionInternalLink>
          </div>
        </div>
      </section>

      <div className="[&_button]:py-2.5 sm:[&_button]:py-3">
        <Starters items={STARTERS} />
      </div>
      <nav
        aria-label="Duftwelten im Katalog"
        className="flex items-center gap-2 overflow-x-auto pb-1 text-[11px] sm:gap-3"
      >
        <span className="shrink-0 font-semibold text-(--ink-soft)">
          Nach Duftgefühl:
        </span>
        {[
          ["freshness", "Frisch"],
          ["sweetness", "Süß"],
          ["woodiness", "Holzig"],
          ["spiciness", "Würzig"],
        ].map(([profile, label]) => (
          <AcquisitionInternalLink
            key={profile}
            href={`/duft?profil=${profile}`}
            className="shrink-0 rounded-full border border-(--line) bg-(--card) px-3 py-2 font-semibold text-(--accent-ink) transition hover:border-(--accent)"
          >
            {label} →
          </AcquisitionInternalLink>
        ))}
      </nav>
      <section
        aria-labelledby="dufynd-audience-discovery-heading"
        className="dufynd-home-audience-stage rounded-[26px] border border-white/10 p-3.5 shadow-(--shadow-sm) sm:p-5"
        data-dufynd-home-audience-stage
      >
        <div className="flex items-end justify-between gap-4">
          <div>
            <div className="text-[9.5px] font-semibold uppercase tracking-[0.13em] text-(--accent-ink)">
              Zielgruppe entdecken
            </div>
            <h2
              id="dufynd-audience-discovery-heading"
              className="mt-1 text-[16px] font-semibold tracking-[-0.02em] text-(--ink)"
            >
              Direkt in deine Duftwelt
            </h2>
          </div>
          <AcquisitionInternalLink
            href="/duft"
            className="hidden text-[11px] font-semibold text-(--accent-ink) hover:underline sm:inline"
          >
            Alle Düfte →
          </AcquisitionInternalLink>
        </div>

        <div className="-mx-1 mt-3 flex snap-x snap-mandatory gap-2.5 overflow-x-auto px-1 pb-1 sm:grid sm:grid-cols-3 sm:overflow-visible">
          {audiencePreviews.map(({ key, label, eyebrow, product }) => {
            const count = audienceCounts[key];
            const world = homeVisualWorldFor(product);
            const productHasVisual = Boolean(
              product?.image_url ||
                (product &&
                  getLiveFragranceByProductId(
                    String(product.product_id),
                  )?.presentation_visual?.url) ||
                (product &&
                  getLiveFragranceByProductId(
                    String(product.product_id),
                  )?.preferred_visual?.url),
            );

            return (
              <AcquisitionInternalLink
                key={key}
                href={`/duft?zielgruppe=${key}`}
                className="dufynd-home-audience-card group relative min-h-[146px] min-w-[76%] snap-start overflow-hidden rounded-2xl border border-white/10 p-4 transition sm:min-w-0"
                data-dufynd-home-audience-card
                data-dufynd-home-world={world}
              >
                <span
                  aria-hidden
                  className="dufynd-home-audience-atmosphere"
                />
                <div className="relative z-10 max-w-[58%]">
                  <div className="text-[9px] font-semibold uppercase tracking-[0.14em] text-(--ink-faint)">
                    {eyebrow}
                  </div>
                  <h3 className="mt-1 text-[17px] font-semibold tracking-[-0.025em] text-(--ink)">
                    {label}
                  </h3>
                  <p className="mt-1 text-[11px] leading-4 text-(--ink-soft)">
                    {count === 1 ? "1 Duft" : `${count} Düfte`} im aktuellen
                    Katalog
                  </p>
                  <span className="mt-3 inline-flex text-[10.5px] font-semibold text-(--accent-ink)">
                    Entdecken →
                  </span>
                </div>

                {product && productHasVisual ? (
                  <div className="dufynd-home-audience-product pointer-events-none absolute inset-y-0 right-0 z-[1] flex w-[52%] items-center justify-center p-2">
                    <ProductImage
                      product={product}
                      className="h-[128px] w-full transition duration-300 group-hover:scale-[1.035]"
                    />
                  </div>
                ) : null}
                <span
                  aria-hidden
                  className="dufynd-home-audience-shade pointer-events-none absolute inset-0"
                />
              </AcquisitionInternalLink>
            );
          })}
        </div>
      </section>
      <div className="flex flex-wrap gap-x-2 gap-y-1 text-[11.5px] text-(--ink-soft) sm:hidden">
        <span>Unabhängige Empfehlungen</span>
        <span>·</span>
        <span>Transparente Händlerangebote</span>
        <span>·</span>
        <AcquisitionInternalLink href="/transparenz" className="font-medium text-(--accent-ink)">Mehr erfahren</AcquisitionInternalLink>
      </div>
      <section className="hidden gap-3 sm:grid sm:grid-cols-3" aria-label="So funktioniert DUFYND">
        <div className="rounded-2xl border border-(--line) bg-(--card) p-4 shadow-(--shadow-sm)">
          <div className="text-[13px] font-semibold text-(--ink)">Empfehlungen nach deinen Kriterien</div>
          <p className="mt-1 text-[12.5px] leading-5 text-(--ink-soft)">
            DUFYND priorisiert Passung, Preis, Verfügbarkeit und Aktualität. Partnervergütungen beeinflussen keine Duftempfehlung. Bei gleichem Gesamtpreis und vergleichbarer Aktualität können Partnerlink und Provision die Angebotsreihenfolge entscheiden.
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
        <AcquisitionInternalLink href="/transparenz" className="font-medium text-(--accent-ink) hover:underline">
          So bewertet DUFYND Empfehlungen und Händlerangebote
        </AcquisitionInternalLink>
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
          <AcquisitionInternalLink
            href="/duftfinder"
            className="rounded-2xl border border-(--line) bg-(--card) p-4 shadow-(--shadow-sm) transition hover:border-(--accent)"
          >
            <div className="text-[13px] font-semibold text-(--ink)">
              Meinen Duft finden
            </div>
            <p className="mt-1 text-[12px] leading-5 text-(--ink-soft)">
              Nach Anlass, Budget, Duftprofil, Haltbarkeit und Ausstrahlung.
            </p>
          </AcquisitionInternalLink>
          <AcquisitionInternalLink
            href="/parfum-alternativen"
            className="rounded-2xl border border-(--line) bg-(--card) p-4 shadow-(--shadow-sm) transition hover:border-(--accent)"
          >
            <div className="text-[13px] font-semibold text-(--ink)">
              Alternative finden
            </div>
            <p className="mt-1 text-[12px] leading-5 text-(--ink-soft)">
              Ähnliche Duftrichtungen transparent vergleichen.
            </p>
          </AcquisitionInternalLink>
          <AcquisitionInternalLink
            href="/parfum-geschenkberater"
            className="rounded-2xl border border-(--line) bg-(--card) p-4 shadow-(--shadow-sm) transition hover:border-(--accent)"
          >
            <div className="text-[13px] font-semibold text-(--ink)">
              Parfum verschenken
            </div>
            <p className="mt-1 text-[12px] leading-5 text-(--ink-soft)">
              Mit wenigen Fragen zu einer passenden Geschenkidee.
            </p>
          </AcquisitionInternalLink>
        </div>
      </HomeSection>

      <div className="flex flex-wrap gap-2 text-[12.5px] text-(--ink-soft)">
        <AcquisitionInternalLink
          href="/duft"
          className="rounded-full border border-(--line) bg-(--card) px-3 py-1.5 font-medium text-(--accent-ink) hover:border-(--accent)"
        >
          {scentCount
            ? `${scentCount} Düfte im Sortiment ansehen`
            : "Duftkatalog ansehen"}
        </AcquisitionInternalLink>
        <span className="rounded-full border border-(--line) bg-(--card) px-3 py-1.5">
          Preise & Community-Bewertungen
        </span>
        <span className="rounded-full border border-(--line) bg-(--card) px-3 py-1.5">
          Empfehlungen nach Budget & Duftprofil
        </span>
        <AcquisitionInternalLink
          href="/vergleich"
          className="rounded-full border border-(--line) bg-(--card) px-3 py-1.5 font-medium text-(--accent-ink) hover:border-(--accent)"
        >
          Parfumvergleiche
        </AcquisitionInternalLink>
        <AcquisitionInternalLink
          href="/sammlung"
          className="rounded-full border border-(--line) bg-(--card) px-3 py-1.5 font-medium text-(--accent-ink) hover:border-(--accent)"
        >
          Meine Duftsammlung
        </AcquisitionInternalLink>
        <AcquisitionInternalLink
          href="/merkliste"
          className="rounded-full border border-(--line) bg-(--card) px-3 py-1.5 font-medium text-(--accent-ink) hover:border-(--accent)"
        >
          Meine Merkliste
        </AcquisitionInternalLink>
      </div>
      <PersonalLibrarySummary />
      <MerchantDiscovery sessionSettled={sessionSettled} />

      {picks.length ? (
        <HomeSection title="Ausgewählte Düfte" subtitle="Ein schneller Einstieg für Damen, Herren und Unisex">
          <div
            className="dufynd-home-selected-stage rounded-[26px] border border-white/10 p-3 sm:p-4"
            data-dufynd-home-selected-stage
          >
            <div className="flex flex-col gap-2 sm:hidden">
              {picks.map((product) => (
                <div
                  key={product.product_id}
                  className="dufynd-home-selected-card"
                  data-dufynd-home-world={homeVisualWorldFor(product)}
                >
                  <ProductRow
                    product={product}
                    onOpen={(item) =>
                      window.location.assign(
                        appendAcquisitionAttribution(
                          fragrancePathForProduct(item),
                        ),
                      )
                    }
                  />
                </div>
              ))}
            </div>
            <div className="hidden grid-cols-3 gap-4 sm:grid">
              {picks.map((product) => (
                <div
                  key={product.product_id}
                  className="dufynd-home-selected-card"
                  data-dufynd-home-world={homeVisualWorldFor(product)}
                >
                  <ProductTile
                    product={product}
                    fluid
                    onOpen={(item) =>
                      window.location.assign(
                        appendAcquisitionAttribution(
                          fragrancePathForProduct(item),
                        ),
                      )
                    }
                  />
                </div>
              ))}
            </div>
            <AcquisitionInternalLink
              href="/duft"
              className="dufynd-home-selected-all mt-3 inline-flex w-fit rounded-xl border border-white/10 bg-white/[0.06] px-4 py-2.5 text-[12px] font-semibold text-white/78 transition hover:border-white/20 hover:bg-white/[0.09]"
            >
              Alle {scentCount} Düfte im Katalog entdecken →
            </AcquisitionInternalLink>
          </div>
        </HomeSection>
      ) : null}
      <LegalFooter />
    </div>
  );
}
