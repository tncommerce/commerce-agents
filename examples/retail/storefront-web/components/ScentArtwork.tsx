import styles from './ScentArtwork.module.css';

/** Original CSS composition. It represents scent, never a bottle or packaging. */
export default function ScentArtwork({name, notes = [], tone = 'sage', compact = false}: {
  name: string; notes?: string[]; tone?: 'sage' | 'rose' | 'amber'; compact?: boolean;
}) {
  return <figure className={`${styles.art} ${styles[tone]} ${compact ? styles.compact : ''}`} data-scent-artwork>
    <span className={styles.edition}>DUFYND / OLFAKTIVE STUDIE</span>
    <div className={styles.composition} aria-hidden="true">
      <i className={styles.halo}/><i className={styles.sheet}/><i className={styles.fold}/><i className={styles.orbit}/>
    </div>
    <div className={styles.annotation}><span>01 / {notes[0] || name}</span><span>02 / {notes[1] || 'Duftkomposition'}</span></div>
    <figcaption>Duftillustration · kein Produktfoto</figcaption>
  </figure>;
}
