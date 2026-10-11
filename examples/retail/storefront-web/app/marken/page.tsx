import type {Metadata} from 'next';
import BrandDirectory from '@/components/BrandDirectory';
import {PUBLIC_BRANDS} from '@/lib/brands';
import styles from './brands.module.css';
export const metadata:Metadata={title:'Parfummarken von A–Z',description:'Alle Marken im unabhängigen DUFYND Duftkatalog. Öffentliche Duftprofile, alphabetisch geordnet.',robots:{index:false,follow:true},alternates:{canonical:'/marken'}};
export default function BrandsPage(){return <main className={styles.page}><header className={styles.header}><a className={styles.logo} href="/">DUFYND</a><a href="/duft">Zum Duftkatalog ↗</a></header><div className={styles.intro}><p>DIE MARKENBIBLIOTHEK</p><h1>Eine Welt voller<br/>Duftgeschichten.</h1><p>Von vertrauten Klassikern bis zu neuen Perspektiven. Alle Marken alphabetisch – ohne Popularitätsranking. Gezählt werden nur öffentliche Duftprofile.</p></div><BrandDirectory brands={PUBLIC_BRANDS}/></main>;}
