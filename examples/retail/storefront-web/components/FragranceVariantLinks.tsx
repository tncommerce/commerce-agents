import AcquisitionInternalLink from "@/components/AcquisitionInternalLink";
import { LIVE_FRAGRANCES } from "@/lib/fragranceCatalog";

export default function FragranceVariantLinks() {
  const directProductIds = [
    "SC-RABANNE-1-MILLION-EDT-100",
    "SC-YSL-LIBRE-EDP-90",
    "SC-YSL-BLACK-OPIUM-EDP-90",
    "SC-PDM-DELINA-EDP-75",
  ];
  const directFragrances = directProductIds.flatMap((productId) =>
    LIVE_FRAGRANCES.filter((fragrance) => fragrance.product_id === productId),
  );

  return (
    <nav aria-label="Direkt zu diesen Duftvarianten" className="mt-4 border-t border-(--line) pt-4">
      <p className="mb-2 text-[11.5px] font-semibold text-(--ink-soft)">
        Direkt zu diesen Varianten
      </p>
      <ul className="grid gap-2 sm:grid-cols-2">
        {directFragrances.map((fragrance) => (
          <li key={fragrance.product_id}>
            <AcquisitionInternalLink
              href={`/duft/${fragrance.slug}`}
              className="flex min-h-14 flex-col justify-center rounded-xl border border-(--line) bg-[#fffdf8] px-3 py-2 transition hover:border-(--accent) focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-(--accent)"
            >
              <span className="text-[12px] font-semibold">{fragrance.brand} {fragrance.name}</span>
              <span className="text-[11px] text-(--ink-soft)">{fragrance.concentration} · {fragrance.volume_ml} ml</span>
            </AcquisitionInternalLink>
          </li>
        ))}
      </ul>
    </nav>
  );
}
