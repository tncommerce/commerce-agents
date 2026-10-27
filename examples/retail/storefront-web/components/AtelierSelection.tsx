"use client";
import { LIVE_FRAGRANCES, originalPhotoFor } from "@/lib/fragranceCatalog";
import { noteLabel } from "@/lib/noteLabels";
import { trackAnalyticsEvent } from "@/lib/analytics";
import AcquisitionInternalLink from "./AcquisitionInternalLink";
import FragranceVisual from "./FragranceVisual";
import ImageAttribution from "./ImageAttribution";

export default function AtelierSelection() {
  const items = ["SC-LANCOME-LA-VIE-EST-BELLE-EDP-100", "SC-YSL-LIBRE-EDP-90"].flatMap(id => {
    const p = LIVE_FRAGRANCES.find(p => p.product_id === id); const visual = p && originalPhotoFor(p); return p && visual ? [{p,visual}] : [];
  });
  return <section className="wow-selection" aria-labelledby="wow-selection-title">
    <div className="wow-section-heading"><div><p className="wow-kicker">01 / Im Detail</p><h2 id="wow-selection-title">Charakter zeigen.</h2></div></div>
    <div className="wow-selection-grid" data-dufynd-home-selected-stage>{items.map(({p,visual},i) => <article className="wow-selection-item" key={p.product_id}>
      <AcquisitionInternalLink data-dufynd-original-card href={`/duft/${p.slug}`} onClick={() => void trackAnalyticsEvent("product_open", { product_id:p.product_id,source:"homepage_spotlight" })} className="wow-selection-link">
        <div className="wow-selection-photo"><span className="wow-selection-number">0{i+1}</span><FragranceVisual imageUrl={visual.url} cutoutUrl={visual.url} alt={`${p.brand} ${p.name} · ${p.concentration} ${p.volume_ml} ml`} variant="card" mode="cutout" className="h-full w-full" /></div>
        <div className="wow-selection-copy"><span className="wow-kicker">{p.brand}</span><h3>{p.name}</h3><p>{p.concentration} · {p.volume_ml} ml</p><div className="wow-selection-notes">{[...p.notes.top,...p.notes.heart,...p.notes.base,...p.notes.key].slice(0,3).map(noteLabel).join(" / ")}</div><span className="wow-text-link">Duftprofil entdecken <span aria-hidden>↗</span></span></div>
      </AcquisitionInternalLink>
      <ImageAttribution visual={visual} />
    </article>)}</div>
  </section>;
}
