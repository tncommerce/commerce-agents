"use client";

import { getLiveFragranceByProductId } from "@/lib/fragranceCatalog";
import { getHomeVisual, HOME_EDITORIAL_PRODUCT_ID } from "@/lib/homeVisualAssets";
import { trackAnalyticsEvent } from "@/lib/analytics";
import AcquisitionInternalLink from "./AcquisitionInternalLink";
import FragranceVisual from "./FragranceVisual";
import ImageAttribution from "./ImageAttribution";
import styles from "./VisualHome.module.css";

export default function HomeOffers() {
  const product = getLiveFragranceByProductId(HOME_EDITORIAL_PRODUCT_ID);
  const visual = product && getHomeVisual(product, {kind: "editorial"});
  return <section id="haendlerangebote" className={styles.offerSection} aria-labelledby="home-offers-title">
    {product && visual ? <div className={styles.offerFeature}>
      <AcquisitionInternalLink data-dufynd-original-card href={`/duft/${product.slug}`} className={styles.featurePhoto} aria-label={`${product.brand} ${product.name} öffnen`} onClick={() => void trackAnalyticsEvent("product_open", {product_id:product.product_id,source:"homepage_spotlight"})}><FragranceVisual imageUrl={visual.url} cutoutUrl={visual.url} alt={`${product.brand} ${product.name} · ${product.concentration} ${product.volume_ml} ml`} variant="card" mode="cutout" className="h-full w-full" /></AcquisitionInternalLink>
      <div className={styles.featureText}><span className={styles.kicker}>Im Duftprofil</span><h3>{product.name}</h3><p>{product.brand}<br />{product.concentration} · {product.volume_ml} ml</p><AcquisitionInternalLink href={`/duft/${product.slug}`} className={styles.textLink}>Duft kennenlernen ↗</AcquisitionInternalLink></div>
      <div className={styles.featureAttribution}><ImageAttribution visual={visual} /></div>
    </div> : null}
    <div className={styles.offerCopy}><p className={styles.kicker}>Von der Entdeckung zum Lieblingsduft</p><h2 id="home-offers-title">Hier entdecken.<br /><em>Beim Händler kaufen.</em></h2><p>DUFYND hilft dir bei der Auswahl. Im Duftprofil findest du vorhandene Angebote mit Größe, Preis und Prüfzeitpunkt.</p><AcquisitionInternalLink href="/duft/rabanne-1-million#angebote" data-dufynd-offer-entry className={styles.offerExample}><span><small>Rabanne</small><strong>1 Million</strong><span>Eau de Toilette · 100 ml</span></span><span>Händlerangebote prüfen <i aria-hidden>↗</i></span></AcquisitionInternalLink></div>
  </section>;
}
