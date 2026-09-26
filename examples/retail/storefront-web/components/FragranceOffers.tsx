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
import { OFFICIAL_PRODUCT_PAGES } from "@/lib/officialProductPages";

function OfficialProductLink({ productId }: { productId: string }) {
  const page = OFFICIAL_PRODUCT_PAGES[productId];
  if (!page) return null;

  return (
    <div className="mt-3 rounded-xl border border-(--line) bg-(--surface) p-3">
      <p className="text-[12px] leading-5 text-(--ink-soft)">
        Produktinformationen direkt bei Marke bzw. Hersteller ansehen. Preis und
        Verfügbarkeit prüfst du dort aktuell; DUFYND zeigt dafür keinen ungeprüften
        Preis an.
        Dieser Verweis ist kein Partnerlink.
      </p>
      <a
        href={page.url}
        target="_blank"
        rel="noopener noreferrer"
        className="mt-2 inline-flex rounded-lg border border-(--line-strong) px-3 py-2 text-[12px] font-semibold text-(--accent-ink) hover:bg-(--card)"
      >
        Bei {page.merchant} ansehen ↗
      </a>
    </div>
  );
}

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
        <OfficialProductLink productId={productId} />
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
        <OfficialProductLink productId={productId} />
      </section>
    );
  }

  const partnerOfferCount = payload.offers.filter(
    (offer) => offer.affiliate_link,
  ).length;
  const externalOfferCount =
    payload.offers.length - partnerOfferCount;

  return (
    <section
      className={`rounded-[24px] border border-(--line) bg-(--card) ${compact ? "p-4" : "p-5 sm:p-6"} shadow-(--shadow)`}
      data-merchant-offers
    >
      <div className="flex flex-wrap items-end justify-between gap-2">
        <div>
          <h2 className="text-[17px] font-semibold text-(--ink)">
            {heading}
          </h2>
          <p className="mt-1 max-w-2xl text-[12px] leading-5 text-(--ink-soft)">
            {payload.offers.length} verifizierte{" "}
            {payload.offers.length === 1 ? "Kaufoption" : "Kaufoptionen"} ·
            {partnerOfferCount ? ` ${partnerOfferCount} Partner${partnerOfferCount === 1 ? "angebot" : "angebote"}` : ""}
            {partnerOfferCount && externalOfferCount ? " · " : ""}
            {externalOfferCount ? ` ${externalOfferCount} weitere ${externalOfferCount === 1 ? "Option" : "Optionen"}` : ""}
            {" · "}Sortiert nach bekanntem Gesamtpreis und Aktualität. Bei Preisgleichheit und vergleichbarer Aktualität können Partnerlink und Provision entscheiden.
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
              className={`flex flex-wrap items-center justify-between gap-3 rounded-2xl border px-4 py-3.5 sm:px-5 ${
                best
                  ? "border-(--accent)/45 bg-(--accent-soft)/45 shadow-(--shadow-sm)"
                  : "border-(--line) bg-(--well)/35"
              }`}
            >
              <div className="min-w-0">
                <div className="flex flex-wrap items-center gap-2">
                  <span className="font-semibold text-(--ink)">
                    {offer.merchant_name}
                  </span>
                  {best ? (
                    <span className="rounded-full bg-(--ink) px-2 py-0.5 text-[9.5px] font-semibold uppercase tracking-[0.08em] text-(--surface)">
                      {offer.total_price != null
                        ? "Bester Gesamtpreis"
                        : "Beste verfügbare Option"}
                    </span>
                  ) : null}
                  <span
                    className={`rounded-full border px-2 py-0.5 text-[9.5px] font-semibold uppercase tracking-[0.07em] ${
                      offer.affiliate_link
                        ? "border-(--accent)/45 bg-(--accent-soft) text-(--accent-ink)"
                        : "border-(--line) bg-(--card) text-(--ink-soft)"
                    }`}
                  >
                    {offer.affiliate_link
                      ? "Werbung · Partnerlink"
                      : "Weitere Kaufoption"}
                  </span>
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
                className={`w-full rounded-xl px-4 py-2.5 text-center text-[13px] font-semibold text-white transition sm:w-auto ${
                  best
                    ? "bg-(--accent-strong) shadow-sm hover:brightness-95"
                    : "bg-(--ink) hover:opacity-90"
                }`}
              >
                Bei {offer.merchant_name} ansehen
              </a>
            </div>
          );
        })}
      </div>

      <div className="mt-3 rounded-xl border border-(--line) bg-(--well)/35 px-3 py-2.5 text-[10.5px] leading-relaxed text-(--ink-soft)">
        {partnerOfferCount ? (
          <p>
            <span className="font-semibold text-(--ink)">Werbung · Partnerlink:</span>{" "}
            DUFYND kann bei entsprechend gekennzeichneten Links eine Provision
            erhalten. Sie beeinflusst weder die Duftempfehlung noch den angezeigten
            Händlerpreis. Bei gleichem Gesamtpreis und vergleichbarer Aktualität
            können Partnerstatus und – zwischen gleichwertigen Partnerangeboten –
            die Provision als Tie-Breaker dienen.
          </p>
        ) : null}
        {externalOfferCount ? (
          <p className={partnerOfferCount ? "mt-1.5" : ""}>
            <span className="font-semibold text-(--ink)">Weitere Kaufoptionen:</span>{" "}
            Diese Links zeigen wir als Orientierung, auch wenn DUFYND dafür
            aktuell keine Provision erhält.
          </p>
        ) : null}
        <p className="mt-1.5">
          Kaufvertrag, Zahlung, Versand und Retouren erfolgen direkt beim
          jeweiligen Händler.
        </p>
      </div>
    </section>
  );
}
