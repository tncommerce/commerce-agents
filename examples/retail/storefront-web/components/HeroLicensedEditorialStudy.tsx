"use client";

import AcquisitionInternalLink from "./AcquisitionInternalLink";
import styles from "./VisualHome.module.css";

/**
 * Not product truth, and not a merchant photo. Strictly localhost-only art
 * direction research with the exact independent source and visible license.
 * The Commons contributor describes their photograph as 1 Million 100 ml,
 * but no verified article GTIN can be read from its photographic provenance.
 */
export const COMMONS_EDITORIAL_STUDY_SOURCE = "https://upload.wikimedia.org/wikipedia/commons/2/27/1_Million_PL.JPG";
export const COMMONS_EDITORIAL_STUDY_PAGE =
  "https://commons.wikimedia.org/wiki/File:1_Million_PL.JPG";
export const COMMONS_EDITORIAL_STUDY_LICENSE =
  "https://creativecommons.org/licenses/by-sa/3.0/";

export default function HeroLicensedEditorialStudy() {
  return (
    <div className={styles.licensedStage} data-dufynd-licensed-study="research"
      aria-label="Interne DUFYND Editorial-Studie: echte historische 100-ml-Flakonfotografie">
      <div className={styles.licensedAmbient} aria-hidden="true" />
      <div className={styles.licensedPhotoFrame}>
        <AcquisitionInternalLink href="/duft/rabanne-1-million#angebote"
          data-dufynd-licensed-photo-link className={styles.licensedImageLink}
          aria-label="Rabanne 1 Million Eau de Toilette 100 ml · Duftprofil mit Händlerangeboten">
          {/* Original unchanged: no generated branding, crop, or object reconstruction. */}
          {/* eslint-disable-next-line @next/next/no-img-element */}
          <img src={COMMONS_EDITORIAL_STUDY_SOURCE}
            alt="Originalaufnahme eines goldfarbenen Paco Rabanne 1 Million Flakons; 100 ml laut Fotograf"
            width={1424} height={2144} decoding="async" loading="eager" fetchPriority="high"
            data-dufynd-licensed-source />
        </AcquisitionInternalLink>
        <div className={styles.licensedPhotoFooter}>
          <span>ECHTE AUFNAHME · 2011</span>
          <strong>1 Million</strong>
          <span>100 ml · historisches Motiv</span>
        </div>
      </div>
      <div className={styles.licensedAttribution}>
        Bild: <a href={COMMONS_EDITORIAL_STUDY_PAGE} target="_blank" rel="noopener noreferrer">
          Beemwej / Wikimedia Commons
        </a> · <a href={COMMONS_EDITORIAL_STUDY_LICENSE} target="_blank"
          rel="license noopener noreferrer">CC BY-SA 3.0</a>
        <span> · Quelle und Fotograf benannt · keine aktuelle Händleraufnahme</span>
      </div>
    </div>
  );
}
