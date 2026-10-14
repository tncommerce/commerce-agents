import type { Metadata } from "next";
import AcquisitionInternalLink from "@/components/AcquisitionInternalLink";
import BrandDirectory from "@/components/BrandDirectory";
import { PUBLIC_BRANDS } from "@/lib/brands";
import { SITE_INDEXABLE } from "@/lib/site";
import styles from "./brands.module.css";

export const metadata: Metadata = {
  title: "Parfummarken von A bis Z | DUFYND",
  description:
    "Entdecke bereits veröffentlichte Duftprofile nach Marke. Markenindex von A bis Z mit direkten Links zu den richtigen Parfumvarianten.",
  robots: { index: false, follow: SITE_INDEXABLE },
  alternates: { canonical: "/marken" },
};

export default function BrandsPage() {
  const totalProducts = PUBLIC_BRANDS.reduce((sum, brand) => sum + brand.count, 0);

  return (
    <main className={styles.page}>
      <div className={styles.frame}>
        <header className={styles.header}>
          <AcquisitionInternalLink href="/" className={styles.logo} aria-label="DUFYND Startseite">
            <img src="/icon.svg" width={32} height={32} alt="" aria-hidden className={styles.logoIcon} />
            <span>DUFYND</span>
          </AcquisitionInternalLink>
          <AcquisitionInternalLink href="/duft" className={styles.headerLink}>
            Zum Duftkatalog <span aria-hidden="true">↗</span>
          </AcquisitionInternalLink>
        </header>

        <section className={styles.hero} aria-labelledby="brand-index-heading">
          <div className={styles.heroLight} aria-hidden="true" />
          <div className={styles.heroContent}>
            <p className={styles.heroEyebrow}><span className={styles.goldLine} /> DUFYND / MARKENINDEX</p>
            <h1 id="brand-index-heading">Deine Duftwelt. <span>Von A bis Z.</span></h1>
            <p className={styles.heroDescription}>
              Entdecke die Marken hinter unseren Duftprofilen. Klar sortiert,
              mit direkten Wegen zur passenden Variante.
            </p>
            <div className={styles.heroBottom}>
              <div className={styles.heroStats}>
                <span><strong>{PUBLIC_BRANDS.length}</strong> Marken</span>
                <span className={styles.heroStatsLine} aria-hidden="true" />
                <span><strong>{totalProducts}</strong> Duftprofile</span>
              </div>
              <a href="#marken-finden" className={styles.heroButton}>Marken finden <span aria-hidden="true">↓</span></a>
            </div>
          </div>
          <div className={styles.heroVisual} aria-hidden="true">
            <span className={styles.heroVisualRing} />
            <span className={styles.heroLetterA}>A</span>
            <span className={styles.heroVisualDash}>—</span>
            <span className={styles.heroLetterZ}>Z</span>
            <span className={styles.heroVisualCaption}>THE FRAGRANCE INDEX · DUFYND</span>
          </div>
        </section>

        <BrandDirectory brands={PUBLIC_BRANDS} />

        <footer className={styles.footer}>
          <span>DUFYND <span aria-hidden="true">·</span> Entdecke bewusst.</span>
          <div>
            <AcquisitionInternalLink href="/duft">Duftkatalog</AcquisitionInternalLink>
            <AcquisitionInternalLink href="/transparenz">Transparenz</AcquisitionInternalLink>
          </div>
        </footer>
      </div>
    </main>
  );
}
