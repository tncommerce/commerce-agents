import type { Metadata } from "next";
import { notFound } from "next/navigation";
import { PUBLIC_BRANDS, fragrancesForBrand } from "@/lib/brands";
import { SITE_INDEXABLE } from "@/lib/site";
import AcquisitionInternalLink from "@/components/AcquisitionInternalLink";
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
    title: `${brand.name} – Parfums & Duftprofile`,
    description: `${brand.count} öffentliche Duftprofile von ${brand.name}. Exakte Varianten und dokumentierte Duftnoten entdecken.`,
    robots: { index: false, follow: SITE_INDEXABLE },
    alternates: { canonical: `/marken/${brand.slug}` },
  };
}
export default async function BrandPage({ params }: Props) {
  const { slug } = await params;
  const brand = PUBLIC_BRANDS.find((item) => item.slug === slug);
  if (!brand) notFound();
  return (
    <main className={styles.page}>
      <header className={styles.header}>
        <AcquisitionInternalLink className={styles.logo} href="/">DUFYND</AcquisitionInternalLink>
        <AcquisitionInternalLink href="/duft">Duftkatalog ↗</AcquisitionInternalLink>
      </header>
      <AcquisitionInternalLink href="/marken" className={styles.back}>← Alle Marken A–Z</AcquisitionInternalLink>
      <div className={styles.intro}>
        <p>DUFTPROFILE DER MARKE</p><h1>{brand.name}</h1>
        <p data-brand-public-count={brand.count}>{brand.count} {brand.count === 1 ? "öffentliches Duftprofil" : "öffentliche Duftprofile"}. Produktinformationen unabhängig von Händlerangeboten.</p>
      </div>
      <ul className={styles.products} aria-label={`Duftprofile von ${brand.name}`}>
        {fragrancesForBrand(slug).map((fragrance) => (
          <li key={fragrance.product_id}>
            <AcquisitionInternalLink data-brand-product={fragrance.product_id} href={`/duft/${fragrance.slug}`}>
              <strong>{fragrance.brand} {fragrance.name}</strong>
              <span>{fragrance.concentration} · {fragrance.volume_ml} ml</span>
              <span>Duftprofil ansehen ↗</span>
            </AcquisitionInternalLink>
          </li>
        ))}
      </ul>
    </main>
  );
}
