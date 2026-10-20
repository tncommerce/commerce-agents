"use client";

import { useEffect, useMemo, useState } from "react";
import FragranceComparisonEvidence from "./FragranceComparisonEvidence";
import FragranceVariant from "./FragranceVariant";
import { noteLabel } from "@/lib/noteLabels";
import styles from "@/app/review/duft/[slug]/review.module.css";

// Only qualified facts are passed here. No staging, community, merchant or image rows.
export type ReviewProfile = {
  id: string;
  slug: string;
  brand: string;
  name: string;
  concentration: string;
  volume: number;
  checkedAt: string;
  source: string;
  notes: { top: string[]; heart: string[]; base: string[]; key: string[]; supporting: string[] };
};
type Selection = { query: string; brand: string; ids: string[] };
const storageKey = "dufynd-private-review-selection-v1";
const emptySelection: Selection = { query: "", brand: "", ids: [] };
const normalize = (value: string) => value.normalize("NFKC").toLocaleLowerCase("de-DE");

export default function QualifiedReviewExplorer({ profiles }: { profiles: ReviewProfile[] }) {
  const [selection, setSelection] = useState<Selection>(emptySelection);
  const [ready, setReady] = useState(false);
  const [comparing, setComparing] = useState(false);
  const [limit, setLimit] = useState(12);
  useEffect(() => {
    try {
      const saved = JSON.parse(sessionStorage.getItem(storageKey) || "null");
      if (saved && typeof saved.query === "string" && typeof saved.brand === "string" && Array.isArray(saved.ids)) {
        setSelection({ query: saved.query.slice(0, 120), brand: profiles.some(p => p.brand === saved.brand) ? saved.brand : "",
          ids: [...new Set<string>(saved.ids.filter((id: unknown) => profiles.some(p => p.id === id)))].slice(0, 2) });
      }
    } catch { /* Browsing remains usable when session storage is unavailable. */ }
    setReady(true);
    const onBack = () => setComparing(location.hash === "#review-vergleich");
    onBack();
    window.addEventListener("popstate", onBack);
    return () => window.removeEventListener("popstate", onBack);
  }, [profiles]);
  useEffect(() => {
    if (ready) try { sessionStorage.setItem(storageKey, JSON.stringify(selection)); } catch { /* Optional local state only. */ }
  }, [ready, selection]);
  useEffect(() => {
    if (ready && comparing) document.getElementById("review-vergleich")?.focus();
  }, [ready, comparing]);
  const filtered = useMemo(() => profiles.filter(p => {
    const searchable = [p.brand, p.name, p.concentration, `${p.volume} ml`, ...Object.values(p.notes).flat().map(noteLabel)].join(" ");
    return (!selection.brand || p.brand === selection.brand) && normalize(searchable).includes(normalize(selection.query.trim()));
  }), [profiles, selection]);
  const selected = selection.ids.flatMap(id => profiles.filter(p => p.id === id));
  const brands = [...new Set(profiles.map(p => p.brand))].sort((a, b) => a.localeCompare(b, "de"));
  function toggle(id: string) {
    setSelection(current => ({ ...current, ids: current.ids.includes(id) ? current.ids.filter(value => value !== id) : [...current.ids, id].slice(0, 2) }));
  }
  function openComparison() {
    if (selected.length !== 2) return;
    history.pushState(null, "", "#review-vergleich");
    setComparing(true);
  }
  function backToSelection() {
    history.replaceState(null, "", "#review-auswahl");
    setComparing(false);
  }
  return <section id="review-auswahl" className={styles.explorer} data-private-review-explorer data-review-ready={ready} aria-busy={!ready}>
    <p className={styles.eyebrow}>PRIVATE DUFTAUSWAHL · NICHT VERÖFFENTLICHT</p>
    <h2>Fakten entdecken. Zwei Düfte vergleichen.</h2>
    <p className={styles.explorerIntro}>Exakte Varianten und dokumentierte Noten. Die Auswahl bleibt in diesem Tab erhalten. Originalfotos: IMAGE_HOLD. Keine Händlerangebote oder Messung.</p>
    {comparing && selected.length === 2 ? <div id="review-vergleich" tabIndex={-1} data-private-review-comparison>
      <button className={styles.reviewButton} onClick={backToSelection}>← Zurück zur Auswahl</button>
      <div className={styles.compareIdentities}>{selected.map(p => <article key={p.id} data-review-comparison-product={p.id}>
        <p className={styles.eyebrow}>{p.brand}</p><h3>{p.name}</h3>
        <FragranceVariant concentration={p.concentration} volume={p.volume} />
        <a href={`/review/duft/${p.slug}`}>Duftprofil & Quellen ansehen →</a>
        <p>Duftdaten: {p.checkedAt} · <a href={p.source} target="_blank" rel="noreferrer">Originalquelle ↗</a></p>
      </article>)}</div>
      <FragranceComparisonEvidence left={{ ...selected[0], accords: [] }} right={{ ...selected[1], accords: [] }} />
    </div> : <>
      <div className={styles.reviewFilters}>
        <label>Review-Düfte suchen<input type="search" disabled={!ready} value={selection.query} maxLength={120} placeholder="Marke, Duft oder dokumentierte Note" onChange={e => { setSelection({ ...selection, query: e.target.value }); setLimit(12); }} /></label>
        <label>Marke<select disabled={!ready} value={selection.brand} onChange={e => { setSelection({ ...selection, brand: e.target.value }); setLimit(12); }}><option value="">Alle Marken</option>{brands.map(brand => <option key={brand}>{brand}</option>)}</select></label>
      </div>
      <div className={styles.selectionBar}>
        <div><p role="status">{selected.length} von 2 Düften ausgewählt</p><p>{selected.length ? selected.map(p => `${p.brand} ${p.name} · ${p.volume} ml`).join(" / ") : "Wähle zwei exakte Varianten für den Vergleich."}</p></div>
        <button className={styles.reviewButton} disabled={!ready || selected.length !== 2} onClick={openComparison}>Zwei Düfte vergleichen</button>
        {selected.length > 0 && <button className={styles.reviewReset} onClick={() => setSelection({ ...selection, ids: [] })}>Auswahl leeren</button>}
      </div>
      <p className={styles.resultCount}>{filtered.length} private Review-Profile · {selection.query || selection.brand ? <button onClick={() => { setSelection({ ...selection, query: "", brand: "" }); setLimit(12); }}>Suche & Filter zurücksetzen</button> : "Keine öffentliche Produktfreigabe"}</p>
      <div className={styles.reviewGrid}>{filtered.slice(0, limit).map(p => <article key={p.id} className={styles.reviewCard} data-review-card={p.id}>
        <p className={styles.eyebrow}>{p.brand}</p><h3><a href={`/review/duft/${p.slug}`}>{p.name}</a></h3>
        <FragranceVariant concentration={p.concentration} volume={p.volume} />
        <p className={styles.reviewNotes}>{[...new Set(Object.values(p.notes).flat())].slice(0, 4).map(noteLabel).join(" · ")}</p>
        <p className={styles.reviewImageHold}>Originalfoto in Prüfung · IMAGE_HOLD</p>
        <button className={styles.reviewSelect} aria-pressed={selection.ids.includes(p.id)} aria-label={`${p.brand} ${p.name}, ${p.concentration}, ${p.volume} ml ${selection.ids.includes(p.id) ? "abwählen" : "auswählen"}`} disabled={!ready || (selected.length === 2 && !selection.ids.includes(p.id))} onClick={() => toggle(p.id)}>{selection.ids.includes(p.id) ? "✓ Ausgewählt" : "Zum Vergleich auswählen"}</button>
      </article>)}</div>
      {!filtered.length && <p className={styles.reviewEmpty}>Keine belegte Variante zu dieser Suche. Setze Suche und Filter zurück, um alle privaten Profile zu sehen.</p>}
      {filtered.length > limit && <button className={styles.reviewButton} onClick={() => setLimit(limit + 12)}>Weitere Review-Düfte anzeigen</button>}
    </>}
  </section>;
}
