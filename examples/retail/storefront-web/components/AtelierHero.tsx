"use client";
import AcquisitionInternalLink from "./AcquisitionInternalLink";
import { appendAcquisitionAttribution } from "@/lib/analytics";

export default function AtelierHero() {
  return <section className="wow-hero" aria-labelledby="dufynd-home-discovery-heading">
    <div className="wow-hero-top"><span className="wow-kicker">DUFYND / Das Duft-Atelier</span><AcquisitionInternalLink href="/marken">Marken A–Z ↗</AcquisitionInternalLink></div>
    <div className="wow-hero-composition">
      <div className="wow-hero-copy">
        <h1 id="dufynd-home-discovery-heading">Finde den Duft,<br />der zu dir <em>passt.</em></h1>
        <p>Parfum verstehen. Favoriten vergleichen.<br />Deinen Weg zum passenden Händler finden.</p>
        <form action="/duft" method="get" role="search" aria-label="DUFYND Duftkatalog durchsuchen" className="wow-search" onSubmit={event => {
          event.preventDefault(); const query = String(new FormData(event.currentTarget).get("q") || ""); const target = new URL("/duft", window.location.origin); target.searchParams.set("q", query); window.location.assign(appendAcquisitionAttribution(target.toString()));
        }}>
          <label htmlFor="dufynd-home-search" className="sr-only">Duft oder Marke suchen</label>
          <input id="dufynd-home-search" name="q" type="search" maxLength={80} placeholder="Duft, Marke, Note" />
          <button type="submit">Suchen <span aria-hidden>↗</span></button>
        </form>
        <div className="wow-hero-actions"><AcquisitionInternalLink className="dufynd-hero-primary" href="/duftfinder">Meinen Duft finden →</AcquisitionInternalLink><AcquisitionInternalLink href="/vergleich">Düfte vergleichen</AcquisitionInternalLink></div>
      </div>
      <a href="#duft-atlas" className="wow-hero-art" aria-label="Den interaktiven Duftnoten-Atlas entdecken">
        <span className="wow-art-coordinate">D / 01</span>
        <span className="wow-art-sphere" aria-hidden><i /><i /><i /><b>D</b></span>
        <span className="wow-art-caption">Die Architektur<br /><em>eines Duftes.</em></span>
        <span className="wow-art-invite">Atlas entdecken <span aria-hidden>↓</span></span>
      </a>
    </div>
    <div className="wow-hero-foot"><span>Duftwissen statt Blindkauf.</span><span>Entdecken · Vergleichen · Händler wählen</span></div>
  </section>;
}
