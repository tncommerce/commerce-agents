"use client";

import { useEffect, useRef, useState } from "react";
import { formatMoney } from "web-shared";

import {
  fetchMerchantOffers,
  merchantClickoutUrl,
} from "@/lib/api";
import {
  appendAcquisitionAttribution,
  trackAnalyticsEvent,
} from "@/lib/analytics";
import type { MerchantOffersPayload } from "@/lib/types";

function formatUpdatedAt(value: string): string | null {
  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime())) return null;

  return parsed.toLocaleString("de-DE", {
    day: "2-digit",
    month: "2-digit",
    year: "numeric",
    hour: "2-digit",
    minute: "2-digit",
    timeZone: "Europe/Berlin",
  });
}

export default function FragranceOffers({
  productId,
  heading = "Aktuelle Händlerangebote",
  trackProductOpen = true,
  compact = false,
  analyticsSurface = "fragrance_detail",
}: {
  productId: string;
  heading?: string;
  trackProductOpen?: boolean;
  compact?: boolean;
  analyticsSurface?: string;
}) {
  const [payload, setPayload] = useState<
    MerchantOffersPayload | null | undefined
  >(undefined);
  const [loadError, setLoadError] = useState(false);
  const [reloadToken, setReloadToken] = useState(0);
  const trackedDetailViewRef = useRef<string | null>(null);

  useEffect(() => {
    let active = true;

    const detailViewKey = `${productId}:${analyticsSurface}`;
    if (
      trackProductOpen &&
      trackedDetailViewRef.current !== detailViewKey
    ) {
      trackedDetailViewRef.current = detailViewKey;
      void trackAnalyticsEvent("fragrance_detail_view", {
        product_id: productId,
        source: "fragrance_detail_page",
        surface: analyticsSurface,
      });
    }

    setLoadError(false);
    setPayload(undefined);

    void fetchMerchantOffers(productId)
      .then((value) => {
        if (!active) return;

        if (value === null) {
          setLoadError(true);
          setPayload(null);
          return;
        }

        setPayload(value);
      })
      .catch(() => {
        if (!active) return;
        setLoadError(true);
        setPayload(null);
      });

    return () => {
      active = false;
    };
  }, [
    analyticsSurface,
    productId,
    reloadToken,
    trackProductOpen,
  ]);

  if (payload === undefined) {
    return (
      <section
        className={`rounded-2xl border border-(--line) bg-(--card) ${compact ? "p-4" : "p-5"} shadow-(--shadow-sm)`}
        aria-busy="true"
      >
        <div className="text-[13px] font-semibold text-(--ink)">
          Händlerangebote werden geprüft …
        </div>
      </section>
    );
  }

  if (loadError) {
    return (
      <section className={`rounded-2xl border border-(--line) bg-(--card) ${compact ? "p-4" : "p-5"} shadow-(--shadow-sm)`}>
        <h2 className="text-[17px] font-semibold text-(--ink)">
          {heading}
        </h2>
        <p className="mt-2 text-[13px] leading-5 text-(--ink-soft)">
          Die Händlerangebote konnten gerade nicht geladen werden.
          Duftdaten und Empfehlungen bleiben verfügbar.
        </p>
        <button
          type="button"
          onClick={() =>
            setReloadToken((value) => value + 1)
          }
          className="mt-3 rounded-xl border border-(--line) bg-(--surface) px-3 py-2 text-[12px] font-semibold text-(--ink) transition hover:border-(--ink)"
        >
          Angebote erneut prüfen
        </button>
      </section>
    );
  }

  if (!payload || payload.offers.length === 0) {
    return (
      <section className={`rounded-2xl border border-(--line) bg-(--card) ${compact ? "p-4" : "p-5"} shadow-(--shadow-sm)`}>
        <h2 className="text-[17px] font-semibold text-(--ink)">
          {heading}
        </h2>
        <p className="mt-2 text-[13px] leading-5 text-(--ink-soft)">
          Für diesen Duft ist aktuell kein ausreichend aktuelles,
          verifiziertes Händlerangebot verfügbar. DUFYND zeigt hier
          erst ein Angebot an, wenn Preis und Verfügbarkeit die
          Aktualitätsprüfung bestehen.
        </p>
      </section>
    );
  }

  const hasAffiliateLink = payload.offers.some(
    (offer) => offer.affiliate_link,
  );

  return (
    <section
      className={`rounded-2xl border border-(--line) bg-(--card) ${compact ? "p-4" : "p-5"} shadow-(--shadow-sm)`}
      data-merchant-offers
    >
      <div className="flex flex-wrap items-end justify-between gap-2">
        <div>
          <h2 className="text-[17px] font-semibold text-(--ink)">
            {heading}
          </h2>
          <p className="mt-1 text-[12px] text-(--ink-soft)">
            Kauf, Zahlung, Versand und Retouren erfolgen direkt beim Händler.
            Angebote werden nach bekanntem Gesamtpreis und Aktualität sortiert.
          </p>
        </div>
      </div>

      <div className="mt-4 space-y-2.5">
        {payload.offers.map((offer) => {
          const best = offer.offer_id === payload.best_offer_id;
          const displayedPrice =
            offer.total_price ?? offer.price;

          return (
            <div
              key={offer.offer_id}
              className="flex flex-wrap items-center justify-between gap-3 rounded-xl border border-(--line) bg-(--well)/45 px-4 py-3"
            >
              <div className="min-w-0">
                <div className="flex flex-wrap items-center gap-2">
                  <span className="font-semibold text-(--ink)">
                    {offer.merchant_name}
                  </span>
                  {best ? (
                    <span className="rounded-full border border-(--accent) px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wide text-(--ink)">
                      DUFYND Top-Angebot
                    </span>
                  ) : null}
                  {offer.affiliate_link ? (
                    <span className="rounded-full border border-(--line) bg-(--card) px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wide text-(--ink-soft)">
                      Partnerlink
                    </span>
                  ) : null}
                </div>

                <div className="mt-1 flex flex-wrap items-baseline gap-x-2 gap-y-1">
                  <span className="text-[18px] font-bold text-(--ink)">
                    {formatMoney(
                      displayedPrice,
                      offer.currency,
                    )}
                  </span>
                  {offer.shipping_label ? (
                    <span className="text-[11px] text-(--ok)">
                      {offer.shipping_label}
                    </span>
                  ) : offer.total_price == null ? (
                    <span className="text-[11px] text-(--ink-soft)">
                      zzgl. ggf. Versand
                    </span>
                  ) : null}
                  {offer.variant_label ? (
                    <span className="text-[11px] text-(--ink-soft)">
                      {offer.variant_label}
                    </span>
                  ) : null}
                </div>

                {formatUpdatedAt(offer.last_updated_at) ? (
                  <div className="mt-1 text-[10.5px] text-(--ink-soft)">
                    Preis & Bestand geprüft:{" "}
                    {formatUpdatedAt(offer.last_updated_at)}
                  </div>
                ) : null}
              </div>

              <a
                href={appendAcquisitionAttribution(
                  merchantClickoutUrl(
                    offer.clickout_path,
                  ),
                )}
                target="_blank"
                rel={
                  offer.affiliate_link
                    ? "sponsored noopener noreferrer"
                    : "noopener noreferrer"
                }
                onClick={() =>
                  void trackAnalyticsEvent(
                    "merchant_clickout",
                    {
                      product_id: offer.product_id,
                      source: offer.merchant_id,
                      surface: analyticsSurface,
                    },
                  )
                }
                className="rounded-xl bg-(--accent) px-4 py-2.5 text-[13px] font-semibold text-white transition-opacity hover:opacity-90"
              >
                Bei {offer.merchant_name} ansehen
              </a>
            </div>
          );
        })}
      </div>

      <p className="mt-3 text-[10.5px] leading-relaxed text-(--ink-soft)">
        {hasAffiliateLink
          ? payload.affiliate_disclosure
          : "Aktuell sind dies direkte Händlerlinks ohne Affiliate-Tracking."}
      </p>
    </section>
  );
}
