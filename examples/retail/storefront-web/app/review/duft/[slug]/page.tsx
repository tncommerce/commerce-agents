import type { Metadata } from 'next';
import { notFound } from 'next/navigation';
import ScentArtwork from '@/components/ScentArtwork';
import { RELEASE_PILOTS, PILOT_REVIEW_ENABLED } from '@/lib/releasePilots';
import { noteLabel } from '@/lib/noteLabels';
import styles from './review.module.css';
export const dynamicParams = false;
export const metadata: Metadata = {title:'Duftprofil – private Designprüfung',robots:{index:false,follow:false},alternates:{canonical:null}};
export function generateStaticParams() {
  return PILOT_REVIEW_ENABLED ? RELEASE_PILOTS.map(p => ({slug:p.slug})) : [{slug:'disabled'}];
}
export default async function PilotPage({params}: {params:Promise<{slug:string}>}) {
  const {slug} = await params;
  const pilot = RELEASE_PILOTS.find(p => p.slug === slug);
  if (!PILOT_REVIEW_ENABLED || !pilot) notFound();
  const {fact} = pilot;
  const stages = [['top','Auftakt'],['heart','Herz'],['base','Nachklang'],['key','Duftnoten']] as const;
  const notes = fact.notes as Partial<Record<string,string[]>>;
  return <main className={styles.page}>
    <div className={styles.review}>Designprüfung · nicht veröffentlicht</div>
    <header className={styles.header}><a href="/">DUFYND<span>ENTDECKE DEINEN DUFT.</span></a><a href="/duft">Alle Düfte ↗</a></header>
    <nav className={styles.breadcrumb} aria-label="Brotkrumennavigation"><a href="/duft">Düfte</a><span>/</span><span>{fact.brand}</span></nav>
    <section className={styles.hero}>
      <div className={styles.art}><ScentArtwork name={fact.name} tone={pilot.tone as 'rose'|'sage'|'amber'} notes={pilot.art_notes}/></div>
      <div className={styles.intro}>
        <p className={styles.eyebrow}>{fact.brand}</p>
        <h1>{fact.name.replace('REPLICA ', '')}</h1>
        <p className={styles.variant}>{fact.concentration}<span>·</span>{fact.volume_ml} ml</p>
        <h2>{pilot.headline}</h2>
        <p className={styles.summary}>{fact.summary_de}</p>
        <a className={styles.cta} href="#duftverlauf">Den Duft entdecken <span>↓</span></a>
        <p className={styles.footnote}>Duftnoten nach Herstellerangaben.<br/>Die Illustration interpretiert den Duft – sie zeigt keinen Flakon.</p>
      </div>
    </section>
    <section id="duftverlauf" className={styles.notes}>
      <div className={styles.sectionHead}><div><p className={styles.eyebrow}>DIE KOMPOSITION</p><h2>Ein Duft. Mehrere Facetten.</h2></div><p>Vom ersten Eindruck<br/>bis zum Nachklang.</p></div>
      <div className={styles.noteGrid}>{stages.filter(([key])=>notes[key]?.length).map(([key,label],index)=><article key={key}><span className={styles.number}>0{index+1}</span><h3>{label}</h3><ul>{notes[key]!.map(n=><li key={n}>{noteLabel(n)}</li>)}</ul></article>)}</div>
    </section>
    <section className={styles.bottom}>
      <div><p className={styles.eyebrow}>KLAR EINGEORDNET</p><h2>Der Duft steht für sich.</h2><p>Dieses Profil beschreibt die Komposition unabhängig von Händlerangeboten. Aktuell zeigen wir für diese Variante kein geprüftes Angebot.</p><a href="/duft">Weitere Düfte entdecken ↗</a></div>
      <details><summary>Produktangaben & Quellen <span>+</span></summary><dl><dt>Variante</dt><dd>{fact.concentration} · {fact.volume_ml} ml</dd><dt>Identitätsnachweis</dt><dd>{fact.identity.kind === 'gtin' ? 'Geprüfte GTIN' : 'Herstellerreferenz (keine GTIN)'}<br/><code>{fact.identity.value}</code></dd><dt>Quelle</dt><dd><a href={fact.identity.source_url} target="_blank" rel="noreferrer">Originalquelle des Herstellers ↗</a></dd><dt>Duftnoten</dt><dd><a href={fact.notes_source.url} target="_blank" rel="noreferrer">Herstellerangaben zur Komposition ↗</a></dd><dt>Geprüft</dt><dd>11. Oktober 2026</dd><dt>Darstellung</dt><dd>Eigene DUFYND-Duftillustration. Kein Produktfoto.</dd></dl></details>
    </section>
    <footer><span>DUFYND</span><nav aria-label="Weitere Pilotseiten">{RELEASE_PILOTS.filter(p=>p.slug!==slug).map(p=><a key={p.slug} href={`/review/duft/${p.slug}`}>{p.fact.name} ↗</a>)}</nav></footer>
  </main>;
}
