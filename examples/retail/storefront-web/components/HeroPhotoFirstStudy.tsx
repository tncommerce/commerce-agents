"use client";

import AcquisitionInternalLink from "./AcquisitionInternalLink";
import FragranceVisual from "./FragranceVisual";
import ImageAttribution from "./ImageAttribution";
import { getLiveFragranceByProductId } from "@/lib/fragranceCatalog";
import { HOME_EDITORIAL_PRODUCT_ID, getHomeVisual } from "@/lib/homeVisualAssets";
import styles from "./VisualHome.module.css";

/**
 * Strictly localhost-only editorial/photo-first A/B. No unlicensed commercial
 * image, fake product claim, external paid model or public-runtime replacement.
 * Uses the existing CC BY-SA original with its exact internal fragrance route.
 */
export default function HeroPhotoFirstStudy() {
  const product = getLiveFragranceByProductId(HOME_EDITORIAL_PRODUCT_ID);
  const visual = product && getHomeVisual(product, { kind: "editorial" });
  if (!product || !visual) return null;
  const href = `/duft/${product.slug}`;
  return <div className={styles.photoFirstStage} data-dufynd-photo-first="internal" aria-label="Fotografische Parfüm-Inszenierung, nur internes A/B">
    <span className={styles.photoFirstFolio} aria-hidden="true">DUFYND / THE SCENT EDIT</span>
    <AcquisitionInternalLink href={href} className={styles.photoFirstPhoto}
      data-dufynd-editorial-hero-photo aria-label={`${product.brand} ${product.name} – Originalfoto und Duftprofil`}>
      <FragranceVisual imageUrl={visual.url} cutoutUrl={visual.url}
        alt={`${product.brand} ${product.name} · ${product.concentration} ${product.volume_ml} ml`}
        mode="cutout" variant="card" priority className="h-full w-full" />
    </AcquisitionInternalLink>
    <div className={styles.photoFirstCopy}>
      <span className={styles.photoFirstEyebrow}>01 / IM DUFTPROFIL</span>
      <span className={styles.photoFirstBrand}>{product.brand}</span>
      <strong>{product.name}</strong>
      <p>{product.concentration}<span aria-hidden="true"> · </span>{product.volume_ml} ml</p>
      <AcquisitionInternalLink href={href} className={styles.photoFirstLink}>
        Duft entdecken <span aria-hidden="true">↗</span>
      </AcquisitionInternalLink>
    </div>
    <div className={styles.photoFirstCredit}>
      <ImageAttribution visual={visual} />
    </div>
  </div>;
}
