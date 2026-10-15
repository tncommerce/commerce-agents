"use client";

import { useRef } from "react";
import { trackAnalyticsEvent } from "@/lib/analytics";
import AcquisitionInternalLink from "./AcquisitionInternalLink";
import FragranceVisual from "./FragranceVisual";
import {
  LIVE_FRAGRANCES,
  isVerifiedProductTruthVisual,
} from "@/lib/fragranceCatalog";
import styles from "./DiscoveryIntro.module.css";

// Only existing approved original photography. No new asset or rights inference.
const ORIGINAL_IDS = [
  "SC-YSL-LIBRE-EDP-90",
  "SC-PDM-DELINA-EDP-75",
  "SC-YSL-BLACK-OPIUM-EDP-90",
];

export default function DiscoveryIntro({
  catalog = false,
}: {
  catalog?: boolean;
}) {
  const strip = useRef<HTMLDivElement>(null);
  const socialProduct = catalog
    ? LIVE_FRAGRANCES.find((entry) => entry.product_id === "SC-RABANNE-1-MILLION-EDT-100")
    : undefined;
  const originals = ORIGINAL_IDS.flatMap((id) => {
    const fragrance = LIVE_FRAGRANCES.find((entry) => entry.product_id === id);
    const visual =
      fragrance?.presentation_visual || fragrance?.preferred_visual;
    return fragrance && isVerifiedProductTruthVisual(visual)
      ? [{ fragrance, visual: visual! }]
      : [];
  });
  return (
    <section
      className={`${styles.intro} ${catalog ? "dufynd-catalog-discovery-hero" : "dufynd-premium-home"}`}
      aria-labelledby={
        catalog
          ? "dufynd-catalog-discovery-heading"
          : "dufynd-home-discovery-heading"
      }
    >
      <div className={styles.copy}>
        <p className={styles.eyebrow}>DUFYND / Duftentdeckung</p>
        <h1
          id={
            catalog
              ? "dufynd-catalog-discovery-heading"
              : "dufynd-home-discovery-heading"
          }
        >
          {catalog ? (
            <>
              Parfums entdecken.
              <br />
              <em>Deinen Duft finden.</em>
            </>
          ) : (
            <>
              Finde den Duft,
              <br />
              der zu dir <em>passt.</em>
            </>
          )}
        </h1>
        <p className={styles.description}>
          Entdecke Duftprofile. Vergleiche deine Favoriten. Finde persönliche
          Beratung.
        </p>
        <div className={styles.actions}>
          {catalog ? (
            <a href="#dufynd-katalog" className={styles.primary}>
              {LIVE_FRAGRANCES.length} Düfte entdecken ↓
            </a>
          ) : (
            <AcquisitionInternalLink
              href="/duftfinder"
              className={`${styles.primary} dufynd-hero-primary`}
            >
              Meinen Duft finden →
            </AcquisitionInternalLink>
          )}
          <AcquisitionInternalLink href={catalog ? "/duftfinder" : "/duft"}>
            {catalog ? "Beratung →" : "Katalog entdecken"}
          </AcquisitionInternalLink>
        </div>
        <p className={styles.caption}>
          Duftprofile entdecken · Händlerangebote separat prüfen
        </p>
      </div>
      {socialProduct ? (
        <AcquisitionInternalLink
          href={`/duft/${socialProduct.slug}`}
          className={styles.socialProduct}
          data-social-product-entry
          onClick={() => void trackAnalyticsEvent("product_open", {
            product_id: socialProduct.product_id,
            source: "catalog_social_entry",
          })}
        >
          <span className={styles.socialLabel}>Aus unseren Duftvideos</span>
          <span className={styles.socialIdentity}>
            <span>{socialProduct.brand}</span>
            <strong>{socialProduct.name}</strong>
          </span>
          <span className={styles.socialVariant}>{socialProduct.concentration} · {socialProduct.volume_ml} ml</span>
          <span className={styles.socialAction}>Duft & Händlerangebote ansehen <span aria-hidden>→</span></span>
        </AcquisitionInternalLink>
      ) : null}
      {!catalog ? <div
        className={styles.selection}
        aria-label="Auswahl mit freigegebenen Originalaufnahmen"
      >
        <p className={styles.selectionLabel}>
          Drei Charaktere. Dein erster Eindruck.
        </p>
        <div className={styles.products} ref={strip} id="dufynd-original-strip">
          {originals.map(({ fragrance, visual }, index) => (
            <AcquisitionInternalLink
              key={fragrance.product_id}
              href={`/duft/${fragrance.slug}`}
              className={styles.product}
              data-dufynd-original-card
              onClick={() => {
                if (!catalog)
                  void trackAnalyticsEvent("product_open", {
                    product_id: fragrance.product_id,
                    source: "homepage_spotlight",
                  });
              }}
              data-dufynd-discovery-slot={index + 1}
              aria-label={`${fragrance.brand} ${fragrance.name} öffnen`}
            >
              <div className={styles.image}>
                <FragranceVisual
                  imageUrl={visual.url}
                  cutoutUrl={visual.url}
                  alt={`${fragrance.brand} ${fragrance.name}`}
                  variant="card"
                  mode="cutout"
                  className="h-full w-full"
                  priority={index === 0}
                />
              </div>
              <span className={styles.brand}>{fragrance.brand}</span>
              <strong>{fragrance.name}</strong>
              <span className={styles.size}>
                {fragrance.volume_ml} ml · Eau de Parfum
              </span>
            </AcquisitionInternalLink>
          ))}
        </div>
        <div className={styles.stripNav}>
          <span>Wischen, um alle Düfte zu entdecken</span>
          <button type="button" aria-label="Vorherige Düfte" aria-controls="dufynd-original-strip" onClick={() => strip.current?.scrollBy({left:-160,behavior:"smooth"})}>←</button>
          <button type="button" aria-label="Weitere Düfte" aria-controls="dufynd-original-strip" onClick={() => strip.current?.scrollBy({left:160,behavior:"smooth"})}>→</button>
        </div>
      </div> : null}
    </section>
  );
}
