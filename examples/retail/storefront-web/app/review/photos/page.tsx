import type { Metadata } from 'next';
import { notFound } from 'next/navigation';
import FragranceVisual from '@/components/FragranceVisual';
import { LIVE_FRAGRANCES } from '@/lib/fragranceCatalog';
import { PHOTO_REVIEW_ITEMS, PHOTO_REVIEW_ENABLED } from '@/lib/photoIntegrationReview';
export const metadata: Metadata = {title:'Originalflakons · top Parfümerie · Designprüfung',robots:{index:false,follow:false},alternates:{canonical:null}};
export default function PhotoReviewCatalog() {
  if(!PHOTO_REVIEW_ENABLED) notFound();
  return <main className="min-h-screen bg-(--surface) text-(--ink)" data-photo-review-catalog>
    <aside className="border-b border-(--line) bg-[#ede9df] px-5 py-3 text-center text-[12px]">Designprüfung · nicht veröffentlicht · deaktivierte Kaufbuttons</aside>
    <div className="mx-auto max-w-[1080px] px-5 py-10 sm:px-8 sm:py-14">
      <header className="mb-9 max-w-2xl"><p className="text-[11px] font-semibold uppercase tracking-[.16em] text-(--ink-soft)">DUFYND / TOP PARFÜMERIE</p>
        <h1 className="mt-3 text-[36px] font-semibold leading-[1.1] tracking-[-.04em] sm:text-[52px]">Der Flakon. Das Original.</h1>
        <p className="mt-4 max-w-xl text-[15px] leading-6 text-(--ink-soft)">Sechs Düfte aus dem Sortiment von top Parfümerie. Originalaufnahmen, exakte Größen und dokumentierte Duftprofile.</p>
      </header>
      <div className="grid gap-5 sm:grid-cols-2 lg:grid-cols-3">
        {PHOTO_REVIEW_ITEMS.map(photo=>{
          const f=LIVE_FRAGRANCES.find(f=>f.product_id===photo.product_id)!;
          return <article key={f.product_id} data-photo-review-card={f.product_id} className="overflow-hidden rounded-[22px] border border-(--line) bg-white">
            <a href={`/review/photos/${f.slug}`} className="block">
              <FragranceVisual imageUrl={photo.image_url} sourceSize={{width:photo.width,height:photo.height}} alt={`${f.brand} ${f.name} ${f.concentration} ${f.volume_ml} ml`} variant="card" mode="cutout" className="h-[280px] w-full" />
              <div className="border-t border-(--line) px-6 py-5"><p className="text-[10px] font-semibold uppercase tracking-[.12em] text-(--ink-soft)">{f.brand}</p><h2 className="mt-2 min-h-[52px] text-[21px] font-semibold leading-[1.2] tracking-[-.02em]">{f.name}</h2><p className="mt-3 text-[12px] text-(--ink-soft)">{f.concentration} · {f.volume_ml} ml</p><p className="mt-5 flex justify-between text-[12px] font-semibold">Duftporträt entdecken <span>↗</span></p></div>
            </a>
            <p className="border-t border-(--line) px-6 py-3 text-[10px] leading-4 text-(--ink-soft)">Bild: top Parfümerie · offizieller Awin-Feed</p>
          </article>;
        })}
      </div>
      <p className="mt-7 max-w-2xl text-[12px] leading-5 text-(--ink-soft)">Händlergebundene Entwicklungsvorschau. Die Fotos sind unverändert; Passende Top-Händlerangebote sind in den Duftporträts als Kandidaten prüfbar; Kaufbuttons und öffentlicher Release bleiben deaktiviert.</p>
    </div>
  </main>;
}
