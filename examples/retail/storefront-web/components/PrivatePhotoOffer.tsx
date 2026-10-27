import { formatMoney } from "web-shared";
import candidates from "../../data/dufynd_photo_offer_review.json";
import styles from "./FragranceOffers.module.css";

/** Owner-only source review: existing offer fields/styles, no request or link. */
export default function PrivatePhotoOffer({ productId }: { productId: string }) {
  if (process.env.DUFYND_CATALOG_REVIEW !== "1") return null;
  const offer = candidates.offers.find(row => row.product_id === productId);
  if (!offer) return null;
  return <section data-photo-offer-candidate={offer.merchant_product_id} aria-label="Händlerkandidat für die Freigabe" className="mt-5 rounded-2xl border border-(--line) bg-(--card) p-4 sm:p-5">
    <h2 className="text-[17px] font-semibold text-(--ink)">Passendes Händlerangebot zur Freigabe</h2>
    <p className="mt-2 text-[12px] leading-5 text-(--ink-soft)">Privater Kandidat · noch nicht veröffentlicht. Originalfoto und vorbereitetes Angebot stammen von {offer.merchant_name}.</p>
    <div className={`${styles.offer} ${styles.focusedOffer} mt-4 flex flex-wrap items-center justify-between rounded-2xl border`}>
      <div className="min-w-0">
        <p className="font-semibold text-(--ink)">{offer.merchant_name}</p>
        <p data-photo-offer-variant className="mt-2 text-[13px] leading-5 text-(--ink-soft)">{offer.variant_label}</p>
        <p className="mt-2 flex flex-wrap items-baseline gap-2"><strong className={styles.total}>{formatMoney(offer.total_price, offer.currency)}</strong><span className="text-[13px] text-(--ink-soft)">Gesamtpreis inkl. Versand</span></p>
        <dl className={styles.breakdown}><div><dt>Artikel</dt><dd>{formatMoney(offer.price, offer.currency)}</dd></div><div><dt>Versand nach Deutschland</dt><dd>{formatMoney(offer.shipping_cost, offer.currency)}</dd></div></dl>
        <p className="mt-2 text-[12px] leading-5 text-(--ink-soft)">Preis & Bestand geprüft: {new Date(offer.last_updated_at).toLocaleString("de-DE", {timeZone:"Europe/Berlin",day:"2-digit",month:"2-digit",year:"numeric",hour:"2-digit",minute:"2-digit"})}</p>
      </div>
      <button type="button" disabled className={`${styles.merchantAction} inline-flex w-full items-center justify-center rounded-xl bg-(--ink) px-4 py-3 text-[13px] font-semibold text-white opacity-60 sm:w-auto`}>Kaufbutton noch deaktiviert</button>
    </div>
  </section>;
}
