"use client";
import CatalogReturnLink from "@/components/CatalogReturnLink";

import { useEffect, useLayoutEffect, useRef, useState } from "react";
import { formatMoney } from "web-shared";

import {
  fetchMerchantOffers,
  merchantClickoutUrl,
} from "@/lib/api";
import {
  appendAcquisitionAttribution,
  trackAnalyticsEvent,
} from "@/lib/analytics";
import { measurementAllowed, subscribeMeasurement } from "@/lib/measurementConsent";
import type { MerchantOffersPayload } from "@/lib/types";
import { OFFICIAL_PRODUCT_PAGES } from "@/lib/officialProductPages";
import styles from "./FragranceOffers.module.css";

// Recheck returning tabs without polling. A single deadline timer below also
// covers a buyer who keeps the page visible across the API's 72-hour window.
const RETURN_RECHECK_INTERVAL_MS = 5 * 60 * 1000;
const OFFER_MAX_AGE_MS = 72 * 60 * 60 * 1000;
const OFFER_CLOCK_SKEW_MS = 5 * 60 * 1000;

function earliestOfferExpiry(payload: MerchantOffersPayload): number | null {
  let deadline = Number.POSITIVE_INFINITY;
  const now = Date.now();
  for (const offer of payload.offers) {
    const verifiedAt = Date.parse(offer.last_updated_at);
    if (!Number.isFinite(verifiedAt) || verifiedAt > now + OFFER_CLOCK_SKEW_MS) return null;
    deadline = Math.min(deadline, verifiedAt + OFFER_MAX_AGE_MS);
  }
  return deadline;
}

function OfferRecoveryLinks({ alternativesHref }: { alternativesHref?: string }) {
  return (
    <nav aria-label="Weitere Wege zum passenden Duft" className="mt-4 flex flex-wrap gap-2">
      {alternativesHref ? (
        <a href={alternativesHref} className="inline-flex min-h-11 items-center rounded-xl bg-(--accent-strong) px-4 py-2 text-[12px] font-semibold text-white">
          Ähnliche Düfte entdecken
        </a>
      ) : null}
      <CatalogReturnLink href="/duft" className="inline-flex min-h-11 items-center rounded-xl border border-(--line-strong) px-4 py-2 text-[12px] font-semibold text-(--accent-ink)">
        Weitere Düfte & Angebote entdecken
      </CatalogReturnLink>
    </nav>
  );
}

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
  alternativesHref,
  focusedLanding = false,
}: {
  productId: string;
  heading?: string;
  trackProductOpen?: boolean;
  compact?: boolean;
  analyticsSurface?: string;
  alternativesHref?: string;
  /** Compact commerce presentation for the existing first-money product page. */
  focusedLanding?: boolean;
}) {
  // Bind each settled result (including errors) atomically to the request that
  // produced it. A tab-return state update renders before passive effects run.
  const [response, setResponse] = useState<{
    productId: string;
    reloadToken: number;
    payload: MerchantOffersPayload | null | undefined;
  } | undefined>(undefined);
  const payload = response?.payload;
  const [loadError, setLoadError] = useState(false);
  const [reloadToken, setReloadToken] = useState(0);
  // Consent changes must synchronously re-render link attribution, not wait on
  // the optional analytics session. No sensitive data is stored by this tick.
  const [, refreshConsentHref] = useState(0);
  const trackedDetailViewRef = useRef<string | null>(null);
  const offerSectionRef = useRef<HTMLElement | null>(null);
  const trackedOfferViewRef = useRef<string | null>(null);
  const lastOfferFetchStartedAtRef = useRef(0);
  const currentRequestRef = useRef<{
    expiresAt: number | null;
    revalidationPending: boolean;
  } | null>(null);
  const expiresAt = payload && response?.productId === productId &&
    response?.reloadToken === reloadToken ? earliestOfferExpiry(payload) : null;

  useLayoutEffect(() => {
    // Only a committed render can replace the visible offer's ownership.
    // An interrupted candidate render must leave its timer and observer intact.
    const request = { expiresAt, revalidationPending: false };
    currentRequestRef.current = request;
    return () => {
      if (currentRequestRef.current === request) currentRequestRef.current = null;
    };
  }, [analyticsSurface, expiresAt, productId, reloadToken, trackProductOpen]);

  // Consent can change after this product mounted. Observe that choice without
  // re-fetching the functional offers or replaying pre-consent shopping actions.
  useEffect(() => {
    const refreshMeasurement = () => {
      // Rebuild the existing clickout href for grant and withdrawal alike.
      // A verified merchant CTA remains available throughout the update.
      refreshConsentHref((revision) => revision + 1);
      if (!measurementAllowed()) {
        trackedDetailViewRef.current = null;
        return;
      }

      // Shopping never waits on the optional analytics-session transport.
      // The clickout GET is public and independently revalidates the offer.
      // trackAnalyticsEvent keeps best-effort, consent-bound first-party data.
      const detailViewKey = `${productId}:${analyticsSurface}`;
      if (trackProductOpen && trackedDetailViewRef.current !== detailViewKey) {
        trackedDetailViewRef.current = detailViewKey;
        // Only the product that is currently mounted is measured after consent.
        void trackAnalyticsEvent("fragrance_detail_view", {
          product_id: productId,
          source: "fragrance_detail_page",
          surface: analyticsSurface,
        });
      }
    };
    const unsubscribe = subscribeMeasurement(refreshMeasurement);
    refreshMeasurement();
    return () => {
      unsubscribe();
    };
  }, [analyticsSurface, productId, reloadToken, trackProductOpen]);

  useEffect(() => {
    let active = true;
    const setPayload = (value: MerchantOffersPayload | null | undefined) => {
      setResponse({ productId, reloadToken, payload: value });
    };
    setLoadError(false);
    setPayload(undefined);
    lastOfferFetchStartedAtRef.current = Date.now();

    void fetchMerchantOffers(productId)
      .then((value) => {
        if (!active) return;
        // Reject a response for a different fragrance; never reuse its purchase links.
        const deadline = value === null ? null : earliestOfferExpiry(value);
        if (value === null || value.product_id !== productId ||
            deadline === null || deadline <= Date.now()) {
          // A cached or late response cannot revive an expired purchase link.
          // Settle as an error rather than automatically retrying it in a loop.
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

    return () => { active = false; };
  }, [analyticsSurface, productId, reloadToken, trackProductOpen]);

  useEffect(() => {
    const recheckOnReturn = () => {
      if (document.visibilityState !== "visible") return;
      const request = currentRequestRef.current;
      if (!request || request.revalidationPending) return;
      const expired = request.expiresAt !== null && request.expiresAt <= Date.now();
      if (!expired && Date.now() - lastOfferFetchStartedAtRef.current < RETURN_RECHECK_INTERVAL_MS) return;
      // The same fail-closed API fetch runs again. No clickout or measurement
      // event is emitted by this functional freshness check.
      // Reserve the recheck immediately; pageshow and visibilitychange may both
      // fire before React commits the reload and starts the next request.
      request.revalidationPending = true;
      lastOfferFetchStartedAtRef.current = Date.now();
      setReloadToken((current) => current + 1);
    };
    document.addEventListener("visibilitychange", recheckOnReturn);
    window.addEventListener("pageshow", recheckOnReturn);
    return () => {
      document.removeEventListener("visibilitychange", recheckOnReturn);
      window.removeEventListener("pageshow", recheckOnReturn);
    };
  }, []);

  useEffect(() => {
    if (expiresAt === null || !Number.isFinite(expiresAt)) return;
    const request = currentRequestRef.current;
    if (!request) return;
    let active = true;
    const timeoutId = setTimeout(() => {
      // The captured identity also guards a queued timer during a product
      // change, before passive-effect cleanup has had a chance to run.
      if (!active || currentRequestRef.current !== request || request.revalidationPending) return;
      // Hidden tabs defer this one functional read until their return handler.
      if (document.visibilityState !== "visible") return;
      request.revalidationPending = true;
      lastOfferFetchStartedAtRef.current = Date.now();
      setReloadToken((current) => current === reloadToken ? current + 1 : current);
    }, Math.max(1, expiresAt - Date.now()));
    return () => {
      active = false;
      clearTimeout(timeoutId);
    };
  }, [analyticsSurface, expiresAt, productId, reloadToken, trackProductOpen]);

  useEffect(() => {
    const section = offerSectionRef.current;
    if (!section || !payload || payload.offers.length === 0 ||
        response?.productId !== productId || response?.reloadToken !== reloadToken ||
        expiresAt === null || expiresAt <= Date.now()) return;
    const request = currentRequestRef.current;
    if (!request) return;
    const isCurrentOffer = () => currentRequestRef.current === request &&
      !request.revalidationPending && expiresAt > Date.now();
    const impressionKey = `${productId}:${analyticsSurface}`;
    let observer: IntersectionObserver | null = null;
    let observation = 0;
    let active = true;

    const refreshImpression = () => {
      const currentObservation = ++observation;
      observer?.disconnect();
      observer = null;
      if (!measurementAllowed()) {
        trackedOfferViewRef.current = null;
        return;
      }
      if (!isCurrentOffer() || trackedOfferViewRef.current === impressionKey) return;
      const trackImpression = () => {
        if (!active || !isCurrentOffer() || currentObservation !== observation || !measurementAllowed() ||
            trackedOfferViewRef.current === impressionKey) return;
        trackedOfferViewRef.current = impressionKey;
        void trackAnalyticsEvent("offer_section_view", {
          product_id: productId,
          source: "merchant_offers",
          surface: analyticsSurface,
        });
      };
      if (typeof IntersectionObserver === "undefined") {
        // No viewport proof: do not report an offer impression merely because
        // offers loaded. Shopping and navigation remain fully functional.
        return;
      }
      observer = new IntersectionObserver(([entry]) => {
        if (!active || !isCurrentOffer() || currentObservation !== observation ||
            !entry?.isIntersecting || entry.intersectionRatio < 0.35) return;
        trackImpression();
        observer?.disconnect();
      }, { threshold: [0.35] });
      observer.observe(section);
    };
    const unsubscribe = subscribeMeasurement(refreshImpression);
    refreshImpression();
    return () => {
      active = false;
      observation += 1;
      observer?.disconnect();
      unsubscribe();
    };
  }, [analyticsSurface, expiresAt, payload, productId, reloadToken,
      response?.productId, response?.reloadToken, trackProductOpen]);

  // Product props can change before the passive fetch effect clears old data.
  // Never render the previous fragrance's offer or CTA in that intermediate render.
  if (payload === undefined || response?.productId !== productId ||
      response?.reloadToken !== reloadToken ||
      (payload !== null && payload.product_id !== productId)) {
    return (
      <section
        className={`dufynd-journey-offers rounded-2xl border border-(--line) bg-(--card) ${compact ? "p-4" : "p-5"} shadow-(--shadow-sm)`}
        aria-busy="true"
        data-offer-state="loading"
      >
        <div className="text-[13px] font-semibold text-(--ink)">
          Händlerangebote werden geprüft …
        </div>
      </section>
    );
  }

  if (loadError || (payload !== null && payload.offers.length > 0 &&
      (expiresAt === null || expiresAt <= Date.now()))) {
    return (
      <section data-offer-state="error" className={`dufynd-journey-offers rounded-2xl border border-(--line) bg-(--card) ${compact ? "p-4" : "p-5"} shadow-(--shadow-sm)`}>
        <h2 className="text-[17px] font-semibold text-(--ink)">
          {focusedLanding ? "Angebote gerade nicht erreichbar" : heading}
        </h2>
        <p className="mt-2 text-[13px] leading-5 text-(--ink-soft)">
          Die Händlerangebote konnten gerade nicht geladen werden.
          Duftdaten und Empfehlungen bleiben verfügbar.
        </p>
        <button
          type="button"
          onClick={() => setReloadToken((value) => value + 1)}
          className={`mt-3 rounded-xl border border-(--line) px-3 py-2 text-[12px] font-semibold transition hover:border-(--ink) ${focusedLanding ? "min-h-11 bg-(--accent-strong) text-white" : "bg-(--surface) text-(--ink)"}`}
        >
          Angebote erneut prüfen
        </button>
        {!focusedLanding && <OfficialProductLink productId={productId} />}
        <OfferRecoveryLinks alternativesHref={alternativesHref} />
      </section>
    );
  }

  if (!payload || payload.offers.length === 0) {
    return (
      <section data-offer-state="empty" className={`dufynd-journey-offers rounded-2xl border border-(--line) bg-(--card) ${compact ? "p-4" : "p-5"} shadow-(--shadow-sm)`}>
        <h2 className="text-[17px] font-semibold text-(--ink)">
          {focusedLanding ? "Zurzeit kein aktuelles Angebot" : heading}
        </h2>
        <p className="mt-2 text-[13px] leading-5 text-(--ink-soft)">
          Für diesen Duft ist aktuell kein ausreichend aktuelles,
          verifiziertes Händlerangebot verfügbar. DUFYND zeigt hier
          erst ein Angebot an, wenn Preis und Verfügbarkeit die
          Aktualitätsprüfung bestehen.
        </p>
        {!focusedLanding && <OfficialProductLink productId={productId} />}
        <OfferRecoveryLinks alternativesHref={alternativesHref} />
      </section>
    );
  }

  const partnerOfferCount = payload.offers.filter((offer) => offer.affiliate_link).length;
  const externalOfferCount = payload.offers.length - partnerOfferCount;

  return (
    <section
      ref={offerSectionRef}
      className={`dufynd-journey-offers rounded-[24px] border border-(--line) bg-(--card) ${compact ? "p-4" : "p-5 sm:p-6"} shadow-(--shadow)`}
      data-merchant-offers
      data-offer-state="available"
    >
      <div className="flex flex-wrap items-end justify-between gap-2">
        <div>
          <h2 className="text-[17px] font-semibold text-(--ink)">{heading}</h2>
          <p className="mt-1 max-w-2xl text-[12px] leading-5 text-(--ink-soft)">
            {payload.offers.length} verifizierte{" "}
            {payload.offers.length === 1 ? "Kaufoption" : "Kaufoptionen"} ·
            {partnerOfferCount ? ` ${partnerOfferCount} Partner${partnerOfferCount === 1 ? "angebot" : "angebote"}` : ""}
            {partnerOfferCount && externalOfferCount ? " · " : ""}
            {externalOfferCount ? ` ${externalOfferCount} weitere ${externalOfferCount === 1 ? "Option" : "Optionen"}` : ""}
            {focusedLanding && payload.offers.length === 1
              ? " · Kauf direkt beim Händler."
              : " · Nach bekanntem Gesamtpreis und Aktualität sortiert."}
          </p>
        </div>
      </div>

      <p className={styles.purchaseGuide}>
        Angebote vergleichen, beim Händler kaufen. DUFYND verkauft selbst keine Produkte.
      </p>
      <div className="mt-4 space-y-2.5">
        {payload.offers.map((offer) => {
          const best = offer.offer_id === payload.best_offer_id;
          const displayedPrice = offer.total_price ?? offer.price;
          const showPriceBreakdown = offer.total_price != null && offer.shipping_cost != null;
          return (
            <div
              key={offer.offer_id}
              className={`${styles.offer} ${focusedLanding ? styles.focusedOffer : ""} flex flex-wrap items-center justify-between gap-3 rounded-2xl border px-4 py-3.5 sm:px-5 ${
                best
                  ? "border-(--accent)/45 bg-(--accent-soft)/45 shadow-(--shadow-sm)"
                  : "border-(--line) bg-(--well)/35"
              }`}
            >
              <div className="min-w-0">
                <div className="flex flex-wrap items-center gap-2">
                  <span className="font-semibold text-(--ink)">{offer.merchant_name}</span>
                  {best && payload.offers.length > 1 ? (
                    <span className="rounded-full bg-(--ink) px-2 py-0.5 text-[11px] font-semibold uppercase tracking-[0.08em] text-(--surface)">
                      {offer.total_price != null ? "Bester Gesamtpreis" : "Beste verfügbare Option"}
                      {" · hier gelistet"}
                    </span>
                  ) : null}
                  <span
                    className={`rounded-full border px-2 py-0.5 text-[11px] font-semibold uppercase tracking-[0.07em] ${
                      offer.affiliate_link
                        ? "border-(--accent)/45 bg-(--accent-soft) text-(--accent-ink)"
                        : "border-(--line) bg-(--card) text-(--ink-soft)"
                    }`}
                  >
                    {offer.affiliate_link ? "Werbung · Partnerlink" : "Weitere Kaufoption"}
                  </span>
                </div>
                {offer.variant_label ? (
                  <p className="mt-2 text-[13px] leading-5 text-(--ink-soft)">{offer.variant_label}</p>
                ) : null}
                <div className="mt-2 flex flex-wrap items-baseline gap-x-2 gap-y-1">
                  <span className={`${styles.total} text-[24px] font-bold text-(--ink)`}>
                    {formatMoney(displayedPrice, offer.currency)}
                  </span>
                  {offer.total_price != null ? (
                    <span data-offer-price-basis className="text-[13px] leading-5 text-(--ink-soft)">
                      Gesamtpreis inkl. Versand
                    </span>
                  ) : null}
                  {!showPriceBreakdown && offer.shipping_label ? (
                    <span className="text-[13px] leading-5 text-(--ink-soft)">{offer.shipping_label}</span>
                  ) : offer.total_price == null ? (
                    <span className="text-[13px] leading-5 text-(--ink-soft)">
                      Artikelpreis · Versand beim Händler prüfen
                    </span>
                  ) : null}
                </div>
                {showPriceBreakdown ? (
                  <dl data-offer-breakdown className={styles.breakdown}>
                    <div><dt>Artikel</dt><dd>{formatMoney(offer.price, offer.currency)}</dd></div>
                    <div><dt>Versand</dt><dd>{formatMoney(offer.shipping_cost!, offer.currency)}</dd></div>
                  </dl>
                ) : null}
                {formatUpdatedAt(offer.last_updated_at) ? (
                  <div className="mt-2 text-[12px] text-(--ink-soft)">
                    Preis & Bestand geprüft:{" "}{formatUpdatedAt(offer.last_updated_at)}
                  </div>
                ) : null}
              </div>
              <a
                  href={appendAcquisitionAttribution(merchantClickoutUrl(offer.clickout_path))}
                  target="_blank"
                  title="Öffnet einen neuen Tab"
                  rel={offer.affiliate_link ? "sponsored noopener noreferrer" : "noopener noreferrer"}
                  onClick={() => {
                    void trackAnalyticsEvent("merchant_clickout", {
                      product_id: productId,
                      offer_id: offer.offer_id,
                      source: offer.merchant_id,
                      surface: "merchant_offer",
                    });
                  }}
                  className={`${styles.merchantAction} inline-flex items-center justify-center w-full rounded-xl px-4 py-2.5 text-center text-[13px] font-semibold text-white transition sm:w-auto ${
                    best ? "bg-(--accent-strong) shadow-sm hover:brightness-95" : "bg-(--ink) hover:opacity-90"
                  }`}
                >
                  Bei {offer.merchant_name} ansehen <span aria-hidden="true" className="ml-2">↗</span>
                </a>
            </div>
          );
        })}
      </div>
      <div className={styles.disclosure}>
        {partnerOfferCount ? (
          <p>
            <strong>Werbung · Partnerlinks:</strong> Bei einem Kauf über diese Links kann
            DUFYND eine Provision erhalten. Der angezeigte Händlerpreis bleibt davon unberührt.
          </p>
        ) : null}
        <p>
          Kaufvertrag, Zahlung, Versand und Retouren erfolgen beim jeweiligen Händler.
          Preis und Verfügbarkeit können sich seit der letzten Prüfung ändern;
          maßgeblich sind die Angaben beim Händler.
        </p>
        <details className={styles.ranking}>
          <summary>Wie wir Angebote auswählen und sortieren</summary>
          <p>
            Sortiert nach bekanntem Gesamtpreis und Aktualität.
            Bei gleichem Gesamtpreis und vergleichbarer Aktualität
            können Partnerstatus und – zwischen gleichwertigen Partnerangeboten –
            die Provision als Tie-Breaker dienen. Die Duftempfehlung bleibt davon unberührt.
          </p>
          {externalOfferCount ? (
            <p>Weitere Kaufoptionen dienen der Orientierung. DUFYND erhält dafür aktuell keine Provision.</p>
          ) : null}
        </details>
      </div>
    </section>
  );
}
