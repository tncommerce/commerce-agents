"use client";

import { getLiveFragranceByProductId } from "@/lib/fragranceCatalog";
import { HOME_PARTNER_PRODUCTS, getHomeVisual } from "@/lib/homeVisualAssets";
import AcquisitionInternalLink from "./AcquisitionInternalLink";
import FragranceVisual from "./FragranceVisual";
import styles from "./VisualHome.module.css";

/** Partner permission travels with the photograph, including its destination. */
export default function AtelierSelection() {
  const items = HOME_PARTNER_PRODUCTS.flatMap(entry => {
    const product = getLiveFragranceByProductId(entry.productId);
    const visual = product && getHomeVisual(product, { kind: "merchant_showcase", merchantId: "top-parfuemerie", destinationUrl: entry.merchantProductUrl });
    return product && visual ? [{ entry, product, visual }] : [];
  });
  if (!items.length) return null;
  return <section className="wow-selection" data-dufynd-home-selected-stage aria-labelledby="wow-selection-title">
    <div className={styles.heading}><div><p className={styles.kicker}>Partner-Schaufenster · top Parfümerie</p><h2 id="wow-selection-title">Ein erster <em>Funke.</em></h2><p className={styles.headingNote}>Drei Parfums im Blick. Entdecke sie direkt bei unserem Bildpartner.</p></div><AcquisitionInternalLink href="/duft">Zum Duftkatalog ↗</AcquisitionInternalLink></div>
    <div className={styles.productGrid} aria-label="Parfums bei top Parfümerie">
      {items.map(({ entry, product, visual }, index) => <a key={product.product_id} className={styles.product} data-dufynd-partner-photo href={entry.merchantProductUrl} target="_blank" rel="sponsored noopener noreferrer" aria-label={`${product.brand} ${product.name} bei top Parfümerie ansehen, neuer Tab`}>
        <div className={styles.productPhoto}><span className={styles.productNumber}>0{index + 1}</span><FragranceVisual imageUrl={visual.url} cutoutUrl={visual.url} alt={`${product.brand} ${product.name} · ${product.concentration} ${product.volume_ml} ml`} variant="card" mode="cutout" className="h-full w-full" /></div>
        <div className={styles.productCopy}><span className={styles.productBrand}>{product.brand}</span><h3>{product.name}</h3><p>Eau de Parfum · Abbildung: {entry.displayedVolumeMl} ml</p><span className={styles.productCta}>Bei top Parfümerie ansehen <span aria-hidden>↗</span></span></div>
      </a>)}
    </div>
    <p className={styles.partnerNote}>Werbung · Bilder: top Parfümerie. Größe, Preis und Verfügbarkeit beim Händler prüfen. Die Händlerseite kann eine andere Größe vorauswählen.</p>
  </section>;
}
