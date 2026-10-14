"use client";

import { useId, useState } from "react";
import { LIVE_FRAGRANCES, type StaticFragrance } from "@/lib/fragranceCatalog";
import { noteLabel } from "@/lib/noteLabels";
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
  const matching = selectedNote ? LIVE_FRAGRANCES.filter(p => p.product_id !== product.product_id && Object.values(p.notes).flat().some(note => note.trim().toLocaleLowerCase("en-US") === selectedNote.trim().toLocaleLowerCase("en-US"))).slice(0, 3) : [];
  return (
    <section className="wow-atlas" data-scent-atlas aria-labelledby={`${uid}-title`}>
      <div className="wow-atlas-top"><span className="wow-kicker">01 / Der Duftnoten-Atlas</span><span className="wow-edition">DUFYND STUDIO</span></div>
      <div className="wow-atlas-grid">
        <div className="wow-atlas-intro">
          <h2 id={`${uid}-title`}>Ein Duft.<br /><em>Mehrere Perspektiven.</em></h2>
          <p>Was steckt in einem Parfum? Wähle einen Duft und entdecke seine dokumentierten Noten.</p>
          <label className="wow-atlas-label" htmlFor={`${uid}-product`}>Dein Duft im Atlas</label>
          <select id={`${uid}-product`} value={productIndex} onChange={event => { setProductIndex(Number(event.target.value)); setLayer(0); setSelectedNote(null); }}>
            {choices.map((p, i) => <option value={i} key={p.product_id}>{p.brand} · {p.name}</option>)}
          </select>
          <p className="wow-atlas-variant">{product.concentration} · {product.volume_ml} ml</p>
        </div>
        <div className="wow-atlas-instrument" data-atlas-layer={layer}>
          <svg className="wow-atlas-orbits" style={{ transform: `rotate(${productIndex * 17 + (selectedNote ? (current?.notes.indexOf(selectedNote) || 0) * 12 : layer * 20)}deg)` }} viewBox="0 0 460 380" aria-hidden="true">
            <defs>
              <radialGradient id={`${uid}-glass`} cx="32%" cy="24%"><stop stopColor="#fff9e4" stopOpacity=".9" /><stop offset=".45" stopColor="#a18960" stopOpacity=".18" /><stop offset="1" stopColor="#524433" stopOpacity=".05" /></radialGradient>
              <linearGradient id={`${uid}-rim`} x2="1" y2="1"><stop stopColor="#e8d5aa" /><stop offset=".45" stopColor="#837557" stopOpacity=".25" /><stop offset="1" stopColor="#e8d5aa" /></linearGradient>
            </defs>
            <circle cx="230" cy="185" r="144" fill={`url(#${uid}-glass)`} stroke={`url(#${uid}-rim)`} />
            {[0,1,2].map((i) => <ellipse key={i} cx="230" cy="185" rx={172-i*20} ry={58+i*13} transform={`rotate(${i*60-30} 230 185)`} fill="none" stroke={`url(#${uid}-rim)`} strokeWidth={layer === i ? 2 : .7} className="wow-atlas-ring" />)}
            <path d="M230 12V46M230 326V360M40 185H72M388 185H420" stroke="#b6a788" strokeWidth=".6" />
            <circle cx="230" cy="185" r="4" fill="#e6c78e" />
          </svg>
          <div className="wow-atlas-core" aria-hidden="true">{selectedNote ? noteLabel(selectedNote) : "DUFT / ATLAS"}</div>
          <div className="wow-atlas-layer-buttons" aria-label="Duftnoten-Ebene wählen">
            {groups.map((group, i) => <button key={group.label} type="button" aria-pressed={layer === i} aria-controls={`${uid}-notes`} onClick={() => { setLayer(i); setSelectedNote(null); }}><span>0{i+1}</span>{group.label}</button>)}
          </div>
          <div id={`${uid}-notes`} className="wow-atlas-notes" aria-live="polite" aria-atomic="true">
            <span>{current?.label}</span>
            <p className="wow-note-hint">Eine Note wählen, verwandte Duftprofile finden.</p>
            <ul>{current?.notes.map(note => <li key={note}><button type="button" aria-pressed={selectedNote === note} onClick={() => setSelectedNote(note)}>{noteLabel(note)}</button></li>)}</ul>
          </div>
        </div>
      </div>
      <div className="wow-atlas-matches" aria-live="polite" data-atlas-matches>{selectedNote ? <><p>Auch mit {noteLabel(selectedNote)} dokumentiert</p>{matching.length ? matching.map(p => <AcquisitionInternalLink key={p.product_id} href={`/duft/${p.slug}`}>{p.brand} · {p.name} ↗</AcquisitionInternalLink>) : <span>Kein weiteres veröffentlichtes Duftprofil mit dieser Note.</span>}<small>Eine gemeinsame Note bedeutet nicht, dass Düfte gleich riechen.</small></> : <p>Deine nächste Entdeckung beginnt mit einer Note.</p>}</div>
      <div className="wow-atlas-bottom"><p>Abstrakte Visualisierung · keine Aussage über Stärke oder Dauer. Quelle: das dokumentierte DUFYND-Duftprofil.</p><AcquisitionInternalLink href={`/duft/${product.slug}#duftnoten`}>Zum vollständigen Duftprofil <span aria-hidden>↗</span></AcquisitionInternalLink></div>
    </section>
  );
}
