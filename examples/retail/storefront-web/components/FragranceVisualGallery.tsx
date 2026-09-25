import FragranceVisual from "@/components/FragranceVisual";
import {
  isVerifiedProductTruthVisual,
  type FragranceVisualAsset,
} from "@/lib/fragranceCatalog";

const ROLE_LABELS: Record<FragranceVisualAsset["role"], string> = {
  primary: "Produktansicht",
  cutout: "Freisteller",
  editorial: "DUFYND Inszenierung",
  macro: "Detailansicht",
  model_3d: "3D-Modell",
};

const STATUS_LABELS: Partial<
  Record<FragranceVisualAsset["fidelity_status"], string>
> = {
  verified: "Verifiziert",
  editorial_only: "Editorial",
  pending_review: "In Prüfung",
};

export default function FragranceVisualGallery({
  assets,
  alt,
}: {
  assets: FragranceVisualAsset[];
  alt: string;
}) {
  const stillAssets = assets.filter(
    (asset) => asset.role !== "model_3d",
  );
  const unique = stillAssets.filter(
    (asset, index, all) =>
      all.findIndex((candidate) => candidate.url === asset.url) === index,
  );

  if (unique.length < 2) return null;

  return (
    <section
      aria-labelledby="dufynd-visual-gallery-heading"
      className="mt-5 rounded-2xl border border-(--line) bg-(--card) p-4 shadow-(--shadow-sm) sm:p-5"
    >
      <div className="flex flex-wrap items-end justify-between gap-2">
        <div>
          <h2
            id="dufynd-visual-gallery-heading"
            className="text-[17px] font-semibold text-(--ink)"
          >
            Weitere Ansichten
          </h2>
          <p className="mt-1 max-w-2xl text-[11.5px] leading-5 text-(--ink-soft)">
            Produktdarstellung und redaktionelle DUFYND-Welt bleiben bewusst
            getrennt.
          </p>
        </div>
      </div>

      <div className="mt-3 grid gap-3 sm:grid-cols-2">
        {unique.map((asset) => {
          const isProductTruth =
            isVerifiedProductTruthVisual(asset);
          const status = STATUS_LABELS[asset.fidelity_status];

          return (
            <figure
              key={`${asset.role}:${asset.url}`}
              className="overflow-hidden rounded-xl border border-(--line) bg-(--surface)"
            >
              <FragranceVisual
                imageUrl={asset.url}
                cutoutUrl={isProductTruth ? asset.url : undefined}
                alt={`${alt} – ${ROLE_LABELS[asset.role]}`}
                variant="card"
                mode={isProductTruth ? "cutout" : "editorial"}
                className="h-48 w-full sm:h-56"
              />
              <figcaption className="flex flex-wrap items-center justify-between gap-2 border-t border-(--line) px-3 py-2.5">
                <span className="text-[11.5px] font-semibold text-(--ink)">
                  {ROLE_LABELS[asset.role]}
                </span>
                {status ? (
                  <span className="rounded-full border border-(--line) bg-(--well) px-2 py-0.5 text-[9.5px] font-semibold uppercase tracking-[0.06em] text-(--ink-soft)">
                    {status}
                  </span>
                ) : null}
              </figcaption>
            </figure>
          );
        })}
      </div>
    </section>
  );
}
