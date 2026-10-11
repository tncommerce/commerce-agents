import type {Metadata} from 'next';
import {notFound} from 'next/navigation';
import {PUBLIC_BRANDS,fragrancesForBrand} from '@/lib/brands';
import FragranceCatalogBrowser from '@/components/FragranceCatalogBrowser';
import styles from '../brands.module.css';
export const dynamicParams=false;
export function generateStaticParams(){return PUBLIC_BRANDS.map(b=>({slug:b.slug}));}
export async function generateMetadata({params}:{params:Promise<{slug:string}>}):Promise<Metadata>{const {slug}=await params;const b=PUBLIC_BRANDS.find(b=>b.slug===slug);return {title:b?`${b.name} – Parfums & Duftprofile`:'Marke nicht gefunden',description:b?`${b.count} öffentliche Duftprofile von ${b.name}. Varianten und dokumentierte Duftnoten entdecken.`:undefined,robots:{index:false,follow:true},alternates:{canonical:`/marken/${slug}`}};}
export default async function BrandPage({params}:{params:Promise<{slug:string}>}){const {slug}=await params;const b=PUBLIC_BRANDS.find(b=>b.slug===slug);if(!b)notFound();return <main className={styles.page}><header className={styles.header}><a className={styles.logo} href="/">DUFYND</a><a href="/duft">Duftkatalog ↗</a></header><a href="/marken" className={styles.back}>← Alle Marken A–Z</a><div className={styles.intro}><p>DUFTPROFILE DER MARKE</p><h1>{b.name}</h1><p data-brand-public-count={b.count}>{b.count} {b.count===1?'öffentliches Duftprofil':'öffentliche Duftprofile'}. Produktinformationen unabhängig von Händlerangeboten. Suche nach Duft, Konzentration oder dokumentierten Noten.</p></div><section className={styles.catalog}><FragranceCatalogBrowser fragrances={fragrancesForBrand(slug)}/></section></main>;}
