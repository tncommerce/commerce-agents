import type { ReactNode } from "react";
import AcquisitionInternalLink from "./AcquisitionInternalLink";
import styles from "./ScentWorlds.module.css";

const WORLDS = [
  { kind: "vanilla", label: "Vanille", source: "/visual-notes/vanilla-koehler.jpg", width: 500, height: 672 },
  { kind: "rose", label: "Rose", source: "/visual-notes/rose-koehler.jpg", width: 500, height: 685 },
  { kind: "citrus", label: "Zitrus", source: "/visual-notes/citrus-koehler.jpg", width: 500, height: 628 },
] as const;

/** Historical botanical plates, separately licensed from all product photographs. */
export default function ScentWorlds({ children }: { children: ReactNode }) {
  return <details id="duft-atlas" className={styles.worlds} data-atlas-disclosure data-dufynd-scent-worlds>
    <summary>
      <span className={styles.copy}><small>Duftwelten</small><strong>Folge einer <em>Note.</em></strong><span className={styles.openLabel}>Duftnoten-Atlas öffnen <i aria-hidden="true">+</i></span></span>
      <span className={styles.studies} aria-hidden="true">{WORLDS.map(world => <span key={world.kind} data-material={world.kind}><span className={styles.studyImage}><img src={world.source} width={world.width} height={world.height} loading="lazy" decoding="async" alt="" /></span><b>{world.label}</b></span>)}</span>
    </summary>
    <nav className={styles.links} aria-label="Duftnoten im Katalog"><span>Im Katalog entdecken</span><AcquisitionInternalLink href="/duft?q=Vanille">Vanille ↗</AcquisitionInternalLink><AcquisitionInternalLink href="/duft?q=Rose">Rose ↗</AcquisitionInternalLink><AcquisitionInternalLink href="/duft?profil=freshness">Frische Düfte ↗</AcquisitionInternalLink></nav>
    <p className={styles.credit}>Botanische Bildausschnitte aus Köhlers Medizinal-Pflanzen: <a href="https://commons.wikimedia.org/wiki/File:K%C3%B6hler%27s_Medizinal-Pflanzen_in_naturgetreuen_Abbildungen_mit_kurz_erl%C3%A4uterndem_Texte_(Plate_114)_(8232785888).jpg" target="_blank" rel="noopener noreferrer">Vanille</a> und <a href="https://commons.wikimedia.org/wiki/File:K%C3%B6hler%27s_Medizinal-Pflanzen_in_naturgetreuen_Abbildungen_mit_kurz_erl%C3%A4uterndem_Texte_(Plate_124)_(8232791024).jpg" target="_blank" rel="noopener noreferrer">Rose</a> (1890), Biodiversity Heritage Library, <a href="https://creativecommons.org/licenses/by/2.0/" target="_blank" rel="noopener noreferrer">CC BY 2.0 / gemeinfrei</a>; <a href="https://commons.wikimedia.org/wiki/File:Citrus_limonum_(K%C3%B6hler).jpg" target="_blank" rel="noopener noreferrer">Zitrone</a> (1887), Hermann Adolf Köhler, <a href="https://creativecommons.org/publicdomain/mark/1.0/" target="_blank" rel="noopener noreferrer">gemeinfrei</a>. Keine Produktabbildungen.</p>
    {children}
  </details>;
}
