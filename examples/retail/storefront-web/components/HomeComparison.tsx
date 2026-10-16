import { getLiveFragranceByProductId } from "@/lib/fragranceCatalog";
import { noteLabel } from "@/lib/noteLabels";
import AcquisitionInternalLink from "./AcquisitionInternalLink";
import styles from "./VisualHome.module.css";

/** Original note illustrations, not product pictures or intensity scores. */
function NoteMotif({ coffee }: { coffee: boolean }) {
  return <svg className={styles.noteMotif} viewBox="0 0 180 105" role="img" aria-label={`Duftnoten-Illustration: ${coffee ? "Kaffee" : "Lavendel"}`}>
    <circle cx="90" cy="53" r="46" fill={coffee ? "#c49b6c" : "#d6c5d4"} opacity={coffee ? ".15" : ".38"} />
    {coffee ? <g fill="#b79a7b" stroke="#e0cbb3" strokeWidth="1.2">
      <ellipse cx="73" cy="49" rx="20" ry="29" transform="rotate(-30 73 49)" /><path d="M64 24c-5 14 23 30 20 50" fill="none" stroke="#40362e" strokeWidth="3" />
      <ellipse cx="113" cy="66" rx="19" ry="27" transform="rotate(34 113 66)" /><path d="M124 44c-18 9-2 29-26 42" fill="none" stroke="#40362e" strokeWidth="3" />
    </g> : <g strokeLinecap="round"><path d="M84 96 69 29M89 96 91 15M96 96 118 31" stroke="#7c866c" strokeWidth="1.6" />{[[68,31],[72,46],[76,61],[91,20],[91,35],[91,50],[118,35],[113,49],[107,64]].map(([x,y],i)=><g key={i} fill={i%2 ? "#a593b2" : "#826d97"}><ellipse cx={x-3} cy={y} rx="4" ry="7" transform={`rotate(-30 ${x-3} ${y})`} /><ellipse cx={x+4} cy={y-3} rx="4" ry="7" transform={`rotate(30 ${x+4} ${y-3})`} /></g>)}</g>}
  </svg>;
}

export default function HomeComparison() {
  const pair = ["SC-YSL-LIBRE-EDP-90", "SC-YSL-BLACK-OPIUM-EDP-90"].map(getLiveFragranceByProductId);
  if (!pair[0] || !pair[1]) return null;
  const products = [pair[0], pair[1]];
  const href = `/vergleich?left=${pair[0].product_id}&right=${pair[1].product_id}`;
  return <section className={styles.comparison} aria-labelledby="home-comparison-title">
    <div className={styles.compareCopy}><p className={styles.kicker}>Deine Favoriten. Direkt nebeneinander.</p><h2 id="home-comparison-title">Zwei Düfte.<br /> <em>Deine Wahl.</em></h2><p>Duftnoten und Varianten auf einen Blick. Entdecke, was deine Favoriten verbindet — und unterscheidet.</p><AcquisitionInternalLink data-dufynd-comparison-entry href={href} className={styles.textLink}>Diese Düfte vergleichen <span aria-hidden>↗</span></AcquisitionInternalLink></div>
    <div className={styles.duel} aria-label="Libre und Black Opium im Vergleich">
      {products.map((product, index) => <div key={product.product_id} style={{display:"contents"}}>{index === 1 ? <span className={styles.duelJoin} aria-hidden>↔</span> : null}<div className={styles.duelItem} data-tone={index === 1 ? "dark" : "light"}><span>{product.brand}</span><NoteMotif coffee={index === 1} /><h3>{product.name}</h3><p>{product.concentration}<br />{product.volume_ml} ml</p><small>{[...new Set([...product.notes.top, ...product.notes.heart, ...product.notes.base, ...product.notes.key])].slice(0, 3).map(noteLabel).join(" · ")}</small></div></div>)}
    </div>
  </section>;
}
