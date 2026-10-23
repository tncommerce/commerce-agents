"use client";

import AcquisitionInternalLink from "./AcquisitionInternalLink";
import FragranceVisual from "./FragranceVisual";
import ImageAttribution from "./ImageAttribution";
import { appendAcquisitionAttribution } from "@/lib/analytics";
import { LIVE_FRAGRANCES, originalPhotoFor } from "@/lib/fragranceCatalog";

// Featured only when the exact source-verified original is available.
// This is an editorial profile link, never an invented merchant deal.
const featured = LIVE_FRAGRANCES.find(
  (item) => item.product_id === "SC-YSL-BLACK-OPIUM-EDP-90",
);
const featuredVisual = featured ? originalPhotoFor(featured) : null;

export default function AtelierHero() {
  return (
    <section className="wow-hero vr-hero vr-gallery-hero" aria-labelledby="dufynd-home-discovery-heading">
      <div className="wow-hero-top vr-hero-top">
        <span className="wow-kicker">DUFYND / Der unabhängige Duftguide</span>
        <nav aria-label="Schnellzugriff">
          <AcquisitionInternalLink href="/duft">Düfte entdecken</AcquisitionInternalLink>
          <AcquisitionInternalLink href="/vergleich">Düfte vergleichen</AcquisitionInternalLink>
          <AcquisitionInternalLink href="/merkliste">Merkliste</AcquisitionInternalLink>
        </nav>
      </div>

      <div className="wow-hero-composition vr-hero-composition">
        <div className="wow-hero-copy vr-hero-copy">
          <p className="vr-hero-eyebrow">Gute Düfte. Klare Entscheidungen.</p>
          <h1 id="dufynd-home-discovery-heading">
            Nicht irgendein<br />Parfum.<br /><em>Deins.</em>
          </h1>
          <p className="vr-hero-intro">
            Entdecke, was wirklich zu dir passt. Vergleiche dokumentierte
            Duftprofile – und finde separat geprüfte Händlerangebote.
          </p>
          <form
            action="/duft"
            method="get"
            role="search"
            aria-label="DUFYND Duftkatalog durchsuchen"
            className="wow-search vr-hero-search"
            onSubmit={(event) => {
              event.preventDefault();
              const query = String(new FormData(event.currentTarget).get("q") || "");
              const target = new URL("/duft", window.location.origin);
              target.searchParams.set("q", query);
              window.location.assign(appendAcquisitionAttribution(target.toString()));
            }}
          >
            <label htmlFor="dufynd-home-search" className="sr-only">Duft oder Marke suchen</label>
            <input
              id="dufynd-home-search"
              name="q"
              type="search"
              maxLength={80}
              placeholder="Welcher Duft interessiert dich?"
            />
            <button type="submit">Suchen <span aria-hidden="true">↗</span></button>
          </form>
          <div className="wow-hero-actions vr-hero-actions">
            <AcquisitionInternalLink className="dufynd-hero-primary" href="/duftfinder">
              Deinen Duft finden <span aria-hidden="true">↗</span>
            </AcquisitionInternalLink>
            <AcquisitionInternalLink href="/duft">Alle Duftprofile ansehen <span aria-hidden="true">→</span></AcquisitionInternalLink>
          </div>
          <span className="vr-hero-aside">DUFYND ist ein unabhängiger Duftguide. Gekauft wird beim jeweiligen Händler.</span>
        </div>

        <div className="vr-hero-feature" data-dufynd-home-feature>
          <div className="vr-feature-overline">
            <span>Aus dem DUFYND Duftarchiv</span>
            <span>Im Fokus</span>
          </div>
          {featured && featuredVisual ? (
            <>
              <AcquisitionInternalLink
                href={"/duft/" + featured.slug}
                className="vr-feature-profile"
                aria-label={featured.brand + " " + featured.name + ", Duftprofil öffnen"}
              >
                <div className="vr-feature-photo">
                  <span aria-hidden="true" className="vr-gallery-backdrop-word">{featured.name}</span>
                  <FragranceVisual
                    imageUrl={featuredVisual.url}
                    cutoutUrl={featuredVisual.url}
                    alt={featured.brand + " " + featured.name + " " + featured.concentration + " " + featured.volume_ml + " ml"}
                    variant="hero"
                    mode="cutout"
                    world="noir"
                    priority
                    className="vr-feature-visual"
                  />
                </div>
                <div className="vr-feature-caption">
                  <span className="vr-feature-kicker">Duftprofil / Originalaufnahme</span>
                  <strong>{featured.name}</strong>
                  <span>{featured.brand} · {featured.concentration} · {featured.volume_ml} ml</span>
                  <span className="vr-feature-cta">Duftprofil ansehen <span aria-hidden="true">↗</span></span>
                </div>
              </AcquisitionInternalLink>
              <div className="vr-feature-credit"><ImageAttribution visual={featuredVisual} /></div>
            </>
          ) : (
            <div className="vr-feature-fallback">
              <span aria-hidden="true">D.</span>
              <p>Jede Vorliebe erzählt eine andere Duftgeschichte.</p>
            </div>
          )}
          <a href="#duft-atlas" className="wow-hero-art vr-feature-atlas">
            <span>Duftnoten-Atlas entdecken</span><span aria-hidden="true">↘</span>
          </a>
        </div>
      </div>
      <div className="wow-hero-foot vr-hero-foot" aria-label="So funktioniert DUFYND">
        <span><b>01</b> Finde deine Richtung</span>
        <span><b>02</b> Verstehe den Duft</span>
        <span><b>03</b> Prüfe das Angebot</span>
      </div>
    </section>
  );
}
