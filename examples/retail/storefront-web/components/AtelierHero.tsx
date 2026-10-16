"use client";

import AcquisitionInternalLink from "./AcquisitionInternalLink";
import PerfumeObject from "./PerfumeObject";
import { appendAcquisitionAttribution } from "@/lib/analytics";
import styles from "./VisualHome.module.css";

export default function AtelierHero() {
  return <section className={styles.hero} aria-labelledby="dufynd-home-discovery-heading">
    <div className={styles.heroBar}><span>Die Welt der Parfums</span><nav aria-label="Schnellzugriff"><AcquisitionInternalLink href="/marken">Marken A–Z</AcquisitionInternalLink><AcquisitionInternalLink href="/merkliste">Merkliste ↗</AcquisitionInternalLink></nav></div>
    <div className={styles.heroMain}>
      <div className={styles.heroCopy}>
        <div className={styles.titleBlock}><p className={styles.kicker}>Ein Duft. Ein Gefühl. Du.</p><h1 id="dufynd-home-discovery-heading">Parfum.<br /><em>Ganz du.</em></h1></div>
        <p className={styles.heroDescription}>Finde deine nächste Duftliebe.<br />Entdecke Parfums, vergleiche ihre Facetten<br className={styles.desktopBreak} /> und finde passende Händlerangebote.</p>
        <div className={styles.searchBlock}>
          <form action="/duft" method="get" role="search" aria-label="DUFYND Duftkatalog durchsuchen" className={`wow-search ${styles.search}`} onSubmit={event => {
            event.preventDefault();
            const query = String(new FormData(event.currentTarget).get("q") || "");
            const target = new URL("/duft", window.location.origin);
            target.searchParams.set("q", query);
            window.location.assign(appendAcquisitionAttribution(target.toString()));
          }}>
            <label htmlFor="dufynd-home-search" className="sr-only">Duft oder Marke suchen</label><span aria-hidden className={styles.searchIcon}>⌕</span>
            <input id="dufynd-home-search" name="q" type="search" maxLength={80} placeholder="Duft, Marke oder Note" />
            <button type="submit">Suchen <span aria-hidden>↗</span></button>
          </form>
          <AcquisitionInternalLink href="/duftfinder" className={`dufynd-hero-primary ${styles.advisorLink}`}>Noch keine Idee? Finde deinen Duft <span aria-hidden>→</span></AcquisitionInternalLink>
        </div>
      </div>
      <div className={styles.heroObject}><PerfumeObject /></div>
    </div>
    <nav className={styles.quickPaths} aria-label="Dein Weg zum Parfum">
      <AcquisitionInternalLink href="/duft"><span>01</span><strong>Düfte entdecken</strong><i aria-hidden>↗</i></AcquisitionInternalLink>
      <AcquisitionInternalLink href="/vergleich"><span>02</span><strong>Düfte vergleichen</strong><i aria-hidden>↗</i></AcquisitionInternalLink>
      <a href="#haendlerangebote"><span>03</span><strong>Händlerangebote finden</strong><i aria-hidden>↗</i></a>
    </nav>
  </section>;
}
