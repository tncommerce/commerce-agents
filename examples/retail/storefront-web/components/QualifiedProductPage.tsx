import QualifiedReviewExplorer, { type ReviewProfile } from './QualifiedReviewExplorer';
import FragranceVariant from './FragranceVariant';
import FragranceNotesOverview from './FragranceNotesOverview';
import type { RELEASE_PILOTS } from '@/lib/releasePilots';
import { noteLabel } from '@/lib/noteLabels';
import { canonicalBrand, brandSlug } from '@/lib/brandIdentity';
import { PUBLIC_BRANDS } from '@/lib/brands';
import styles from '@/app/review/duft/[slug]/review.module.css';
type Pilot=typeof RELEASE_PILOTS[number];
function reviewProfile(p: Pilot): ReviewProfile {
 const notes = p.fact.notes as Partial<Record<string, string[]>>;
 return {id:p.product_id,slug:p.slug,brand:canonicalBrand(p.fact.brand),name:p.fact.name,concentration:p.fact.concentration,volume:p.fact.volume_ml,checkedAt:p.fact.checked_at,source:p.fact.notes_source.url,notes:{top:notes.top||[],heart:notes.heart||[],base:notes.base||[],key:notes.key||[],supporting:notes.supporting||[]}};
}
export default function QualifiedProductPage({pilot,profiles,publicMode=false}:{pilot:Pilot;profiles:Pilot[];publicMode?:boolean}) {
 const {fact}=pilot;const brand=canonicalBrand(fact.brand);
 const displayName=fact.name===fact.name.toUpperCase()?fact.name.toLowerCase().replace(/(^|\s)\S/g,c=>c.toUpperCase()):fact.name;

 const notes=fact.notes as Partial<Record<string,string[]>>;
 const sharedNotes=new Set(Object.values(notes).flat().map(n=>n?.toLowerCase()));
 const related=profiles.filter(p=>p.product_id!==pilot.product_id).map(p=>({p,shared:[...new Set(Object.values(p.fact.notes).flat().filter(n=>sharedNotes.has(n.toLowerCase())))]})).filter(r=>r.shared.length).sort((a,b)=>b.shared.length-a.shared.length||a.p.slug.localeCompare(b.p.slug)).slice(0,3);
 const index=profiles.indexOf(pilot);
 const next=profiles[(index+1)%profiles.length];
 const previous=profiles[(index+profiles.length-1)%profiles.length];
 return <main className={styles.page} data-review-product={publicMode?undefined:fact.product_id} data-product-id={fact.product_id}>
  {!publicMode&&<div className={styles.review}>Designprüfung · nicht veröffentlicht</div>}
  <header className={styles.header}><a href="/">DUFYND<span>ENTDECKE DEINEN DUFT.</span></a><a href={publicMode?"/duft":"#review-auswahl"}>{publicMode?"Zum Duftkatalog ↗":"Zur privaten Auswahl ↓"}</a></header>
  <nav className={styles.breadcrumb} aria-label="Brotkrumennavigation"><a href={publicMode?"/duft":"#review-auswahl"}>{publicMode?"Düfte":"Review-Auswahl"}</a><span>/</span>{publicMode&&PUBLIC_BRANDS.some(b=>b.slug===brandSlug(brand))?<a href={`/marken/${brandSlug(brand)}`}>{brand}</a>:<span>{brand}</span>}</nav>
  <section className={styles.hero}>
   <div className={styles.identity}><p className={styles.eyebrow}>{brand}</p><h1 data-long-word={displayName.split(/\s+/).some(word=>word.length>11)?'true':undefined}>{displayName.replace('REPLICA ','')}</h1><FragranceVariant concentration={fact.concentration} volume={fact.volume_ml} /></div>
   <div className={styles.art} data-dufynd-studio-source-hold role="img" aria-label={`${brand} ${displayName}: Originalfoto noch nicht freigegeben`}>
      <span className={styles.photoEyebrow}>DUFYND / DUFTARCHIV</span>
      <div className={styles.photoIdentity}>
        <span>{brand}</span><strong>{displayName}</strong>
        <small>{fact.concentration} · {fact.volume_ml} ml</small>
      </div>
      <span data-dufynd-studio-source-label className={styles.photoHold}>Originalfoto in Prüfung</span>
    </div>
   <div className={styles.intro}><p className={styles.chapter}>DAS DUFTPORTRÄT <span>01 — 03</span></p><h2>{pilot.headline}</h2><p className={styles.summary}>{fact.summary_de}</p><a className={styles.cta} href="#duftverlauf">Die Komposition entdecken <span>↓</span></a><p className={styles.footnote}>Neutrale Studiokarte, kein Markenflakon. Produktinformationen unabhängig von Händlerangeboten.</p></div>
  </section>
  <nav className={styles.sectionNav} aria-label="Auf dieser Duftseite"><a href="#duftverlauf">01 · Duftnoten</a><a href="#einordnung">02 · Einordnung</a><a href="#quellen">03 · Quellen</a></nav>
  <section id="duftverlauf" className={styles.notes}>
       <FragranceNotesOverview interactive={publicMode} notes={{
         top: notes.top || [],
         heart: notes.heart || [],
         base: notes.base || [],
         key: notes.key || [],
         supporting: notes.supporting || [],
       }} />
     </section>
  <section id="einordnung" className={styles.bottom}><div><p className={styles.eyebrow}>DER DUFT STEHT FÜR SICH</p><h2>Entdecken. Ohne Kaufpflicht.</h2><p>Dieses Profil beschreibt die Komposition unabhängig von Händlerangeboten. Für diese exakte Variante zeigen wir aktuell kein verifiziertes Angebot.</p><a href={publicMode?"/duft":"#review-auswahl"}>{publicMode?"Weitere Düfte entdecken ↗":"Private Düfte suchen & vergleichen ↓"}</a></div>
   <details id="quellen"><summary>Produktangaben & Quellen <span>+</span></summary><dl><dt>Variante</dt><dd>{fact.concentration} · {fact.volume_ml} ml</dd><dt>Identität</dt><dd>{fact.identity.kind==='gtin'?'Geprüfte GTIN':'Herstellerreferenz (keine GTIN)'}<br/><code>{fact.identity.value}</code></dd><dt>Originalquelle</dt><dd><a href={fact.identity.source_url} target="_blank" rel="noreferrer">{fact.identity.kind==='gtin'?'Identitätsnachweis beim Händler':'Produktseite des Herstellers'} ↗</a></dd><dt>Duftnoten</dt><dd><a href={fact.notes_source.url} target="_blank" rel="noreferrer">{fact.notes_source.kind==='manufacturer_product_facts'?'Herstellerangaben':'Dokumentierte Händlerangaben'} ↗</a></dd>{fact.volume_source_url&&<><dt>Volumennachweis</dt><dd><a href={fact.volume_source_url} target="_blank" rel="noreferrer">Quelle zur {fact.volume_ml}-ml-Variante ↗</a></dd></>}{fact.concentration_source_url&&<><dt>Konzentration</dt><dd><a href={fact.concentration_source_url} target="_blank" rel="noreferrer">Ergänzender Variantenbeleg ↗</a></dd></>}{fact.variant_evidence_note&&<><dt>Variantenhinweis</dt><dd>{fact.variant_evidence_note}</dd></>}<dt>Fakten geprüft</dt><dd>{fact.checked_at}</dd><dt>Darstellung</dt><dd>Neutrale DUFYND-Identitätskarte, kein Produktfoto. IMAGE_HOLD: Für diese exakte Variante ist kein Originalbild für diesen Platz freigegeben.</dd></dl></details>
  </section>
  {related.length>0&&<section className={styles.related}><p className={styles.eyebrow}>GEMEINSAME DUFTNOTEN</p><h2>Eine andere Facette entdecken.</h2><p>Gleiche dokumentierte Noten, keine Aussage über Duftähnlichkeit.</p><div>{related.map(({p,shared})=><a key={p.slug} href={`${publicMode?'/duft':'/review/duft'}/${p.slug}`}><strong>{canonicalBrand(p.fact.brand)} · {p.fact.name}</strong><span>Gemeinsam: {shared.map(noteLabel).join(', ')}</span></a>)}</div></section>}
  <footer className={styles.footer}><div><p className={styles.eyebrow}>WEITER ENTDECKEN</p><h2>Die nächste Duftgeschichte.</h2></div><nav aria-label="Review-Produktnavigation"><a href={`${publicMode?'/duft':'/review/duft'}/${previous.slug}`}><small>← Vorheriger Duft</small>{previous.fact.name}</a><a href={`${publicMode?'/duft':'/review/duft'}/${next.slug}`}><small>Nächster Duft →</small>{next.fact.name}</a></nav>{publicMode&&<details><summary>Alle {profiles.length} {publicMode?'Düfte dieser Kollektion':'Review-Düfte'}</summary><div className={styles.directory}>{profiles.map(p=><a key={p.slug} href={`${publicMode?'/duft':'/review/duft'}/${p.slug}`} aria-current={p.slug===pilot.slug?'page':undefined}>{canonicalBrand(p.fact.brand)} · {p.fact.name}<span>{p.fact.concentration} · {p.fact.volume_ml} ml</span></a>)}</div></details>}{!publicMode&&<QualifiedReviewExplorer profiles={profiles.map(reviewProfile)} />}</footer>
 </main>;
}
