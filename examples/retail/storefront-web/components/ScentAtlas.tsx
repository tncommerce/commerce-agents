"use client";

import { useId, useState } from "react";
import { LIVE_FRAGRANCES, type StaticFragrance } from "@/lib/fragranceCatalog";
import { noteLabel } from "@/lib/noteLabels";
import ScentComposition from "./ScentComposition";
import AcquisitionInternalLink from "./AcquisitionInternalLink";

const IDS = ["SC-LANCOME-LA-VIE-EST-BELLE-EDP-100", "SC-YSL-LIBRE-EDP-90", "SC-RABANNE-1-MILLION-EDT-100"];
const choices = IDS.flatMap(id => LIVE_FRAGRANCES.find(p => p.product_id === id) || []);

function groupsFor(product: StaticFragrance) {
  const notes = product.notes;
  const pyramid = [...notes.top, ...notes.heart, ...notes.base].length > 0;
  return (pyramid
    ? [{ label: "Kopf", notes: notes.top }, { label: "Herz", notes: notes.heart }, { label: "Basis", notes: notes.base }]
    : [{ label: "Schlüsselnoten", notes: notes.key }, { label: "Weitere Noten", notes: notes.supporting }]
  ).filter(group => group.notes.length);
}

/** An abstract index of documented notes, never a bottle or a strength/timing claim. */
export default function ScentAtlas() {
  const [productIndex, setProductIndex] = useState(0);
  const [layer, setLayer] = useState(0);
  const [selectedNote, setSelectedNote] = useState<string | null>(null);
  const uid = useId().replace(/:/g, "");
  if (!choices.length) return null;
  const product = choices[productIndex];
  const groups = groupsFor(product);
  const current = groups[layer] || groups[0];
  const activeNote = selectedNote || current?.notes[0] || null;
  const matching = activeNote ? LIVE_FRAGRANCES.filter(p => p.product_id !== product.product_id && Object.values(p.notes).flat().some(note => note.trim().toLocaleLowerCase("en-US") === activeNote.trim().toLocaleLowerCase("en-US"))).slice(0, 2) : [];
  return <section className="wow-atlas" data-scent-atlas aria-labelledby={`${uid}-title`}>
    <div className="wow-atlas-top"><div><p className="wow-kicker">01 / Der Duftnoten-Atlas</p><h2 id={`${uid}-title`}>Folge <em>einer Note.</em></h2></div><span className="wow-edition">DUFYND<br />STUDIO</span></div>
    <div className="wow-atlas-grid">
      <div className="wow-atlas-intro">
        <label className="wow-atlas-label" htmlFor={`${uid}-product`}>Dein Duft im Atlas</label>
        <select id={`${uid}-product`} value={productIndex} onChange={event => { setProductIndex(Number(event.target.value)); setLayer(0); setSelectedNote(null); }}>
          {choices.map((p, i) => <option value={i} key={p.product_id}>{p.brand} · {p.name}</option>)}
        </select>
        <p className="wow-atlas-variant">{product.concentration} · {product.volume_ml} ml</p>
      </div>
      <div className="wow-atlas-instrument" data-atlas-layer={layer}>
        <div className="wow-atlas-material"><ScentComposition phase={productIndex * 2 + Math.max(0, current?.notes.indexOf(activeNote || "") || 0)} /><div className="wow-atlas-core" aria-hidden="true"><small>Deine gewählte Note</small>{activeNote ? noteLabel(activeNote) : "Duftnoten"}</div></div>
      </div>
      <div className="wow-atlas-controls">
        <div className="wow-atlas-layer-buttons" aria-label="Duftnoten-Ebene wählen">
          {groups.length > 1 ? groups.map((group, i) => <button key={group.label} type="button" aria-pressed={layer === i} aria-controls={`${uid}-notes`} onClick={() => { setLayer(i); setSelectedNote(null); }}>{group.label}</button>) : <span>{current?.label}</span>}
        </div>
        <div id={`${uid}-notes`} className="wow-atlas-notes" aria-live="polite">
          <p className="wow-note-hint">Eine Note antippen. Weitere Düfte entdecken.</p>
          <ul>{current?.notes.map(note => <li key={note}><button type="button" aria-pressed={activeNote === note} onClick={() => setSelectedNote(note)}>{noteLabel(note)}</button></li>)}</ul>
        </div>
      </div>
      <div className="wow-atlas-matches" aria-live="polite" data-atlas-matches>
        <p>Auch mit {activeNote ? noteLabel(activeNote) : "dieser Note"} dokumentiert</p>
        <div className="wow-atlas-result-grid">{matching.length ? matching.map(p => <AcquisitionInternalLink key={p.product_id} href={`/duft/${p.slug}`}><span>{p.brand}</span><strong>{p.name}</strong><i aria-hidden>↗</i></AcquisitionInternalLink>) : <span className="wow-atlas-empty">Noch kein weiteres veröffentlichtes Profil mit dieser Note. Probiere eine andere.</span>}</div>
        <small>Eine gemeinsame Note bedeutet nicht den gleichen Duft.</small>
      </div>
    </div>
    <div className="wow-atlas-bottom"><details><summary>Über diese Ansicht</summary><p>Abstrakte Visualisierung dokumentierter Duftnoten. Keine Aussage über Stärke oder Dauer. Quelle: das jeweilige DUFYND-Duftprofil.</p></details><AcquisitionInternalLink href={`/duft/${product.slug}#duftnoten`}>Vollständiges Duftprofil ↗</AcquisitionInternalLink></div>
  </section>;
}
