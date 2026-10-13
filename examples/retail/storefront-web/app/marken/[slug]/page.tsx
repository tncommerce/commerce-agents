import type { Metadata } from "next";
import { notFound } from "next/navigation";
import AcquisitionInternalLink from "@/components/AcquisitionInternalLink";
import { PUBLIC_BRANDS, fragrancesForBrand } from "@/lib/brands";
import { SITE_INDEXABLE } from "@/lib/site";
import styles from "../brands.module.css";

export const dynamicParams = false;
type Props = { params: Promise<{ slug: string }> };

export function generateStaticParams() {
  return PUBLIC_BRANDS.map(({ slug }) => ({ slug }));
}

export async function generateMetadata({ params }: Props): Promise<Metadata> {
  const { slug } = await params;
  const brand = PUBLIC_BRANDS.find((item) => item.slug === slug);
  if (!brand) return { title: "Marke nicht gefunden", robots: { index: false, follow: false } };
  return {
    title: `${brand.name} – Düfte & Parfumvarianten | DUFYND`,
    description: `${brand.count} öffentliche Duftprofile von ${brand.name}. Entdecke die vorhandenen Varianten mit Konzentration und Flakongröße.`,
    robots: { index: false, follow: SITE_INDEXABLE },
    alternates: { canonical: `/marken/${brand.slug}` },
  };
}

export default async function BrandPage({ params }: Props) {
  const { slug } = await params;
  const brand = PUBLIC_BRANDS.find((item) => item.slug === slug);
  if (!brand) notFound();
  const fragrances = fragrancesForBrand(slug);

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

        <nav aria-label="Brotkrumennavigation" className={styles.breadcrumb}>
          <AcquisitionInternalLink href="/marken">Marken A–Z</AcquisitionInternalLink>
          <span aria-hidden="true">/</span>
          <span aria-current="page">{brand.name}</span>
        </nav>

        <section className={styles.brandHero} aria-labelledby="brand-title">
          <div className={styles.brandHeroLight} aria-hidden="true" />
          <div className={styles.brandHeroCopy}>
            <p className={styles.heroEyebrow}>
              <span className={styles.goldLine} /> DUFYND / MARKENBIBLIOTHEK
            </p>
            <h1 id="brand-title">{brand.name}</h1>
            <div className={styles.brandHeroBottom}>
              <p>{brand.count} {brand.count === 1 ? "öffentliches Duftprofil" : "öffentliche Duftprofile"} in unserer Bibliothek.</p>
              <a href="#duftprofile" className={styles.brandHeroLink}>
                Düfte ansehen <span aria-hidden="true">↓</span>
              </a>
            </div>
          </div>
          <div className={styles.brandHeroArt} aria-hidden="true">
            <span className={styles.brandHeroRing} />
            <span className={styles.brandHeroInitial}>{brand.name.slice(0, 1)}</span>
            <span className={styles.brandHeroArtCaption}>DUFYND / BRAND INDEX</span>
          </div>
        </section>

        <section className={styles.brandSection} id="duftprofile" aria-labelledby="brand-products-title">
          <div className={styles.brandSectionHead}>
            <div>
              <span className={styles.sectionEyebrow}>AUS DEM DUFYND KATALOG</span>
              <h2 id="brand-products-title">Die Düfte von <span>{brand.name}.</span></h2>
            </div>
            <span className={styles.brandSectionCount}>
              {String(fragrances.length).padStart(2, "0")} / DUFTPROFILE
            </span>
          </div>

          <ul className={styles.products} aria-label={`Duftprofile von ${brand.name}`}>
            {fragrances.map((fragrance, index) => (
              <li key={fragrance.product_id}>
                <AcquisitionInternalLink
                  data-brand-product={fragrance.product_id}
                  href={`/duft/${fragrance.slug}`}
                  className={styles.productCard}
                  aria-label={`${fragrance.brand} ${fragrance.name}, ${fragrance.concentration}, ${fragrance.volume_ml} ml – Duftprofil öffnen`}
                >
                  <span className={styles.productCardText}>
                    <span className={styles.productOverline}>DUFYND DUFTPROFIL <span aria-hidden="true">·</span> {String(index + 1).padStart(2, "0")}</span>
                    <span className={styles.productBrand}>{fragrance.brand}</span>
                    <strong>{fragrance.name}</strong>
                    <span className={styles.productVariant}>{fragrance.concentration} <span aria-hidden="true">/</span> {fragrance.volume_ml} ml</span>
                    <span className={styles.productCardAction}>Duftprofil öffnen <span aria-hidden="true">↗</span></span>
                  </span>
                  <span className={styles.productCardArt} aria-hidden="true">
                    <span className={styles.productCardCircle} />
                    <span className={styles.productCardLetter}>{fragrance.name.slice(0, 1)}</span>
                    <span className={styles.productCardArtLabel}>NO. {String(index + 1).padStart(2, "0")}</span>
                  </span>
                </AcquisitionInternalLink>
              </li>
            ))}
          </ul>

          <div className={styles.brandFootnote}>
            <div>
              <span className={styles.sectionEyebrow}>ENTDECKE MIT KLARHEIT</span>
              <p>Jeder Eintrag führt zur exakten, bereits veröffentlichten Variante. Geprüfte Händlerangebote findest du – falls vorhanden – direkt im jeweiligen Duftprofil.</p>
            </div>
            <AcquisitionInternalLink href="/marken" className={styles.returnLink}>
              Alle Marken entdecken <span aria-hidden="true">↗</span>
            </AcquisitionInternalLink>
          </div>
        </section>

        <footer className={styles.footer}>
          <span>DUFYND <span aria-hidden="true">·</span> Entdecke bewusst.</span>
          <div>
            <AcquisitionInternalLink href="/marken">Alle Marken</AcquisitionInternalLink>
            <AcquisitionInternalLink href="/transparenz">Transparenz</AcquisitionInternalLink>
          </div>
        </footer>
      </div>
    </main>
  );
}
