"use client";

import { useState } from "react";
import AcquisitionInternalLink from "@/components/AcquisitionInternalLink";
import { brandKey, canonicalBrand } from "@/lib/brandIdentity";
import styles from "@/app/marken/brands.module.css";

type Brand = { slug: string; name: string; count: number };

export default function BrandDirectory({ brands }: { brands: Brand[] }) {
  const [query, setQuery] = useState("");
  const searched = brandKey(canonicalBrand(query));
  const visible = brands.filter((brand) => brandKey(brand.name).includes(searched));
  const letters = [...new Set(visible.map((brand) => brandKey(brand.name)[0].toUpperCase()))];
  const totalProducts = visible.reduce((sum, brand) => sum + brand.count, 0);

  return (
    <section className={styles.indexSection} id="marken-finden" aria-labelledby="marken-finden-titel">
      <div className={styles.indexTopline}>
        <div>
          <span className={styles.sectionEyebrow}>DEIN INDEX / A — Z</span>
          <h2 id="marken-finden-titel">Finde deine{" "}<span>Marke.</span></h2>
        </div>
        <p>Alle Einträge führen ausschließlich zu bereits veröffentlichten DUFYND-Duftprofilen.</p>
      </div>

      <div className={styles.searchPanel}>
        <label className={styles.searchLabel} htmlFor="brand-search">MARKENNAMEN SUCHEN</label>
        <div className={styles.searchControl}>
          <span className={styles.searchGlyph} aria-hidden="true" />
          <input
            id="brand-search"
            type="search"
            value={query}
            onChange={(event) => setQuery(event.target.value)}
            placeholder="Chanel, Prada, Yves Saint Laurent …"
            autoComplete="off"
          />
          {query && (
            <button type="button" onClick={() => setQuery("")} aria-label="Suche löschen" className={styles.clearButton}>
              ×
            </button>
          )}
        </div>
        <div className={styles.searchPanelBottom}>
          <p role="status" className={styles.count}>
            <strong>{visible.length}</strong> {visible.length === 1 ? "Marke" : "Marken"}
            <span aria-hidden="true"> / </span>
            <strong>{totalProducts}</strong> {totalProducts === 1 ? "Duftprofil" : "Duftprofile"}
          </p>
          <span className={styles.indexIndicator}>DUFYND VERZEICHNIS</span>
        </div>
      </div>

      {visible.length > 0 ? (
        <>
          <nav className={styles.alphabet} aria-label="Marken nach Anfangsbuchstabe">
            <span className={styles.alphabetLabel}>SPRINGE ZU</span>
            <div className={styles.alphabetLetters}>
              {letters.map((letter) => (
                <a key={letter} href={`#marke-${letter}`} aria-label={`Zum Buchstaben ${letter}`}>
                  {letter}
                </a>
              ))}
            </div>
          </nav>
          <div className={styles.brandGroups}>
            {letters.map((letter) => (
              <section key={letter} id={`marke-${letter}`} className={styles.letterGroup}>
                <div className={styles.letterHeading}>
                  <span className={styles.letterIndex}>BUCHSTABE</span>
                  <h3>{letter}</h3>
                </div>
                <div className={styles.brandGrid}>
                  {visible.filter((brand) => brandKey(brand.name)[0].toUpperCase() === letter).map((brand) => (
                    <AcquisitionInternalLink
                      data-brand-slug={brand.slug}
                      key={brand.slug}
                      href={`/marken/${brand.slug}`}
                      className={styles.brandCard}
                    >
                      <span className={styles.brandCardTop}>DUFYND / MARKE</span>
                      <span className={styles.brandName}>{brand.name}</span>
                      <small className={styles.brandCount}>
                        {brand.count} {brand.count === 1 ? "Duftprofil" : "Duftprofile"}
                      </small>
                      <span className={styles.brandArrow} aria-hidden="true">↗</span>
                    </AcquisitionInternalLink>
                  ))}
                </div>
              </section>
            ))}
          </div>
        </>
      ) : (
        <div className={styles.emptyState}>
          <span className={styles.emptySymbol} aria-hidden="true">?</span>
          <strong>Keine passende Marke gefunden.</strong>
          <p>Versuche eine andere Schreibweise oder sieh dir alle Marken an.</p>
          <button type="button" onClick={() => setQuery("")}>Alle Marken anzeigen ↗</button>
        </div>
      )}
      <p className={styles.indexNote}>
        Noch nicht jede Duftmarke ist hier vertreten. Der Index zeigt ausschließlich
        Marken mit bereits öffentlichen DUFYND-Duftprofilen.
      </p>
    </section>
  );
}
