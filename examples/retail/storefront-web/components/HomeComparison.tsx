import { getLiveFragranceByProductId } from "@/lib/fragranceCatalog";
import { noteLabel } from "@/lib/noteLabels";
import AcquisitionInternalLink from "./AcquisitionInternalLink";
import styles from "./HomeComparison.module.css";

/** Exact catalogue variants, accompanied by licensed photographs illustrating documented notes. */
export default function HomeComparison() {
  const pair = ["SC-YSL-LIBRE-EDP-90", "SC-YSL-BLACK-OPIUM-EDP-90"].map(getLiveFragranceByProductId);
  if (!pair[0] || !pair[1]) return null;
  const products = [pair[0], pair[1]];
  const href = `/vergleich?left=${pair[0].product_id}&right=${pair[1].product_id}`;
  return <section className={styles.comparison} aria-labelledby="home-comparison-title">
    <div className={styles.heading}><div><p className={styles.kicker}>Direkt vergleichen</p><h2 id="home-comparison-title">Zwei Düfte. <em>Deine Wahl.</em></h2></div><p>Duftnoten. Varianten. Unterschiede.</p></div>
    <div className={styles.diptych} aria-label="Libre und Black Opium im Vergleich">
      {products.map((product, index) => <article key={product.product_id} className={styles.product} data-tone={index ? "coffee" : "lavender"}>
        <div className={styles.identity}><span>{product.brand}</span><h3>{product.name}</h3><p>{product.concentration} · {product.volume_ml} ml</p></div>
        <figure className={styles.material}><img src={index ? "/visual-notes/coffee-nate-steiner.jpg" : "/visual-notes/lavender-norbert-nagel.jpg"} width={index ? 1280 : 960} height={index ? 960 : 1463} loading="lazy" decoding="async" alt={index ? "Kaffeebohnen in einer Makroaufnahme" : "Lavendelblüte in einer botanischen Nahaufnahme"} /><figcaption>{index ? "Kaffee" : "Lavendel"}</figcaption></figure>
        <p className={styles.notes}>{[...new Set([...product.notes.top, ...product.notes.heart, ...product.notes.base, ...product.notes.key])].slice(0, 3).map(noteLabel).join(" · ")}</p>
      </article>)}
      <span className={styles.bridge} aria-hidden="true">↔</span>
    </div>
    <div className={styles.footer}><span>Duftnoten, keine Produktbilder.</span><AcquisitionInternalLink data-dufynd-comparison-entry href={href}>Diese Düfte vergleichen <i aria-hidden="true">↗</i></AcquisitionInternalLink></div>
    <details className={styles.credits}><summary>Bildnachweise</summary><p>Lavendel: <a href="https://commons.wikimedia.org/wiki/File:Lavandula_angustifolia_-_lavender_-_Lavendel_-_01.jpg" target="_blank" rel="noopener noreferrer">Norbert Nagel</a>, <a href="https://creativecommons.org/licenses/by-sa/3.0/" target="_blank" rel="noopener noreferrer">CC BY-SA 3.0</a>. Kaffee: <a href="https://commons.wikimedia.org/wiki/File:Coffee_Beans_closeup.jpg" target="_blank" rel="noopener noreferrer">Nate Steiner</a>, <a href="https://creativecommons.org/licenses/by/2.0/" target="_blank" rel="noopener noreferrer">CC BY 2.0</a>. Unveränderte Wikimedia-Vorschaudateien; im Layout als Bildausschnitt dargestellt. Der Lavendel-Bildausschnitt steht ebenfalls unter CC BY-SA 3.0.</p></details>
  </section>;
}
