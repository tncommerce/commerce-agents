"use client";

import { useEffect, useState, type ComponentType } from "react";
import AcquisitionInternalLink from "./AcquisitionInternalLink";
import PerfumeObject from "./PerfumeObject";
import { appendAcquisitionAttribution } from "@/lib/analytics";
import styles from "./VisualHome.module.css";

export default function AtelierHero() {
  // ONE internal, localhost-only art-direction A/B. Never served by public URL
  // parameters, never shipped as the default before independent still review.
  const [PhotoStudy, setPhotoStudy] = useState<ComponentType | null>(null);
  useEffect(() => {
    if (!["localhost", "127.0.0.1", "[::1]"].includes(window.location.hostname) ||
        !new URLSearchParams(window.location.search).has("dufynd_photo_study")) return;
    let cancelled = false;
    void import("./HeroPhotoFirstStudy").then(module => {
      if (!cancelled) setPhotoStudy(() => module.default);
    });
    return () => { cancelled = true; };
  }, []);
  return <section className={styles.hero} aria-labelledby="dufynd-home-discovery-heading">
    <div className={styles.heroBar}><span>Die Welt der Parfums</span><nav aria-label="Schnellzugriff"><AcquisitionInternalLink href="/marken">Marken A–Z</AcquisitionInternalLink><AcquisitionInternalLink href="/merkliste">Merkliste ↗</AcquisitionInternalLink></nav></div>
    <div className={styles.heroMain}>
      <div className={styles.heroCopy}>
        <div className={styles.titleBlock}><p className={styles.kicker}>Eine Welt. Deine Entdeckung.</p><h1 id="dufynd-home-discovery-heading">Parfum.<br /><em>Ganz du.</em></h1></div>
        <p className={styles.heroDescription}>Entdecke deinen Duft.<br className={styles.desktopBreak} /> Vergleiche deine Favoriten.</p>
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
      <div className={styles.heroObject}>{PhotoStudy
        ? <PhotoStudy />
        : <><span className={styles.objectIndex} aria-hidden>ÉTUDE 01 — LE FLACON</span><PerfumeObject /></>}</div>
    </div>
    <nav className={styles.quickPaths} aria-label="Dein Weg zum Parfum">
      <AcquisitionInternalLink href="/duft"><span>01</span><strong>Düfte entdecken</strong><i aria-hidden>↗</i></AcquisitionInternalLink>
      <AcquisitionInternalLink href="/vergleich"><span>02</span><strong>Düfte vergleichen</strong><i aria-hidden>↗</i></AcquisitionInternalLink>
      <a href="#haendlerangebote"><span>03</span><strong>Händlerangebote finden</strong><i aria-hidden>↗</i></a>
    </nav>
  </section>;
}
