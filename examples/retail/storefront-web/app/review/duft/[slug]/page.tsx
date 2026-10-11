import type { Metadata } from 'next';
import { notFound } from 'next/navigation';
import ScentArtwork, {type ScentMotif} from '@/components/ScentArtwork';
import { RELEASE_PILOTS, PILOT_REVIEW_ENABLED } from '@/lib/releasePilots';
import { noteLabel } from '@/lib/noteLabels';
import { canonicalBrand } from '@/lib/brandIdentity';
import styles from './review.module.css';
export const dynamicParams = false;
export function generateStaticParams() {return PILOT_REVIEW_ENABLED ? RELEASE_PILOTS.map(p=>({slug:p.slug})) : [{slug:'disabled'}];}
export async function generateMetadata({params}:{params:Promise<{slug:string}>}):Promise<Metadata> {
 const {slug}=await params;const p=RELEASE_PILOTS.find(p=>p.slug===slug);
 return {title:p?.seo.title||'Duftprofil – Designprüfung',description:p?.seo.description,robots:{index:false,follow:false},alternates:{canonical:null},openGraph:{title:p?.seo.title,description:p?.seo.description}};
}
export default async function ReviewProductPage({params}:{params:Promise<{slug:string}>}) {
 const {slug}=await params;const pilot=RELEASE_PILOTS.find(p=>p.slug===slug);
 if(!PILOT_REVIEW_ENABLED||!pilot) notFound();
 const {fact}=pilot;const brand=canonicalBrand(fact.brand);
 const displayName=fact.name===fact.name.toUpperCase()?fact.name.toLowerCase().replace(/(^|\s)\S/g,c=>c.toUpperCase()):fact.name;
 const stages=[['top','Auftakt'],['heart','Herz'],['base','Nachklang'],['key','Charakteristische Noten']] as const;
 const notes=fact.notes as Partial<Record<string,string[]>>;
 const index=RELEASE_PILOTS.indexOf(pilot);
 const next=RELEASE_PILOTS[(index+1)%RELEASE_PILOTS.length];
 const previous=RELEASE_PILOTS[(index+RELEASE_PILOTS.length-1)%RELEASE_PILOTS.length];
 return <main className={styles.page} data-review-product={fact.product_id}>
  <div className={styles.review}>Designprüfung · nicht veröffentlicht</div>
  <header className={styles.header}><a href="/">DUFYND<span>ENTDECKE DEINEN DUFT.</span></a><a href="/duft">Zum Duftkatalog ↗</a></header>
  <nav className={styles.breadcrumb} aria-label="Brotkrumennavigation"><a href="/duft">Düfte</a><span>/</span><span>{brand}</span></nav>
  <section className={styles.hero}>
   <div className={styles.identity}><p className={styles.eyebrow}>{brand}</p><h1 data-long-word={displayName.split(/\s+/).some(word=>word.length>11)?'true':undefined}>{displayName.replace('REPLICA ','')}</h1><p className={styles.variant}>{fact.concentration}<span>·</span>{fact.volume_ml} ml</p></div>
   <div className={styles.art}><ScentArtwork name={fact.name} tone={pilot.tone as 'rose'|'sage'|'amber'} motif={pilot.motif as ScentMotif} notes={pilot.art_notes}/></div>
   <div className={styles.intro}><p className={styles.chapter}>DAS DUFTPORTRÄT <span>01 — 03</span></p><h2>{pilot.headline}</h2><p className={styles.summary}>{fact.summary_de}</p><a className={styles.cta} href="#duftverlauf">Die Komposition entdecken <span>↓</span></a><p className={styles.footnote}>Eigenständige Duftillustration, kein Markenflakon.<br/>Produktinformationen unabhängig von Händlerangeboten.</p></div>
  </section>
  <nav className={styles.sectionNav} aria-label="Auf dieser Duftseite"><a href="#duftverlauf">01 · Duftnoten</a><a href="#einordnung">02 · Einordnung</a><a href="#quellen">03 · Quellen</a></nav>
  <section id="duftverlauf" className={styles.notes}><div className={styles.sectionHead}><div><p className={styles.eyebrow}>DIE KOMPOSITION</p><h2>{notes.key?.length?'Facetten eines Duftes.':'Vom Auftakt zum Nachklang.'}</h2></div><p>{notes.key?.length?'Belegte Noten. Keine erfundene Duftpyramide.':'Duftverlauf nach den dokumentierten Originalquellen.'}</p></div><div className={styles.noteGrid} data-stages={notes.key?.length?'key':'pyramid'}>{stages.filter(([k])=>notes[k]?.length).map(([k,label],i)=><article key={k}><span className={styles.number}>0{i+1}</span><h3>{label}</h3><ul>{notes[k]!.map(n=><li key={n}>{noteLabel(n)}</li>)}</ul></article>)}</div></section>
  <section id="einordnung" className={styles.bottom}><div><p className={styles.eyebrow}>DER DUFT STEHT FÜR SICH</p><h2>Entdecken. Ohne Kaufpflicht.</h2><p>Dieses Profil beschreibt die Komposition unabhängig von Händlerangeboten. Für diese exakte Variante zeigen wir aktuell kein verifiziertes Angebot.</p><a href="/duft">Weitere Düfte entdecken ↗</a></div>
   <details id="quellen"><summary>Produktangaben & Quellen <span>+</span></summary><dl><dt>Variante</dt><dd>{fact.concentration} · {fact.volume_ml} ml</dd><dt>Identität</dt><dd>{fact.identity.kind==='gtin'?'Geprüfte GTIN':'Herstellerreferenz (keine GTIN)'}<br/><code>{fact.identity.value}</code></dd><dt>Originalquelle</dt><dd><a href={fact.identity.source_url} target="_blank" rel="noreferrer">{fact.identity.kind==='gtin'?'Identitätsnachweis beim Händler':'Produktseite des Herstellers'} ↗</a></dd><dt>Duftnoten</dt><dd><a href={fact.notes_source.url} target="_blank" rel="noreferrer">{fact.notes_source.kind==='manufacturer_product_facts'?'Herstellerangaben':'Dokumentierte Händlerangaben'} ↗</a></dd><dt>Fakten geprüft</dt><dd>{fact.checked_at}</dd><dt>Darstellung</dt><dd>Eigene DUFYND-Vektorillustration. Kein Produktfoto. Originalproduktbild weiterhin HOLD.</dd></dl></details>
  </section>
  <footer className={styles.footer}><div><p className={styles.eyebrow}>WEITER ENTDECKEN</p><h2>Die nächste Duftgeschichte.</h2></div><nav aria-label="Review-Produktnavigation"><a href={`/review/duft/${previous.slug}`}><small>← Vorheriger Duft</small>{previous.fact.name}</a><a href={`/review/duft/${next.slug}`}><small>Nächster Duft →</small>{next.fact.name}</a></nav><details><summary>Alle {RELEASE_PILOTS.length} Review-Düfte</summary><div className={styles.directory}>{RELEASE_PILOTS.map(p=><a key={p.slug} href={`/review/duft/${p.slug}`} aria-current={p.slug===slug?'page':undefined}>{canonicalBrand(p.fact.brand)} · {p.fact.name}<span>{p.fact.concentration} · {p.fact.volume_ml} ml</span></a>)}</div></details></footer>
 </main>;
}
