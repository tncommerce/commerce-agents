import AcquisitionInternalLink from "@/components/AcquisitionInternalLink";
import LegalFooter from "@/components/LegalFooter";
import scentaiProducts from "../../../data/scentai_products.json";

type LicensedVisual = {
  role?: string;
  url?: string;
  license_name?: string | null;
  license_url?: string | null;
  attribution_text?: string | null;
  share_alike_required?: boolean | null;
};

type ProductRow = {
  product_id: string;
  brand: string;
  name: string;
  concentration: string;
  volume_ml: number;
  visuals?: LicensedVisual[];
};

export const metadata = {
  title: "Bildnachweise",
  description: "Lizenz- und Urheberhinweise zu extern lizenzierten Produktbildern bei DUFYND.",
  alternates: {
    canonical: "/bildnachweise",
  },
  robots: {
    index: false,
    follow: true,
  },
};

const credits = (scentaiProducts.products as ProductRow[])
  .flatMap((product) =>
    (product.visuals || [])
      .filter(
        (visual) =>
          Boolean(visual.attribution_text?.trim()) &&
          Boolean(visual.license_name?.trim()),
      )
      .map((visual) => ({ product, visual })),
  )
  .sort((a, b) =>
    `${a.product.brand} ${a.product.name}`.localeCompare(
      `${b.product.brand} ${b.product.name}`,
      "de",
    ),
  );

export default function ImageCreditsPage() {
  return (
    <main className="min-h-screen bg-(--ground) px-4 py-10 text-(--ink) sm:px-6">
      <div className="mx-auto max-w-3xl">
        <article className="rounded-2xl border border-(--line) bg-(--card) p-6 shadow-(--shadow-sm) sm:p-8">
          <AcquisitionInternalLink
            href="/"
            className="text-[13px] font-semibold text-(--accent-ink) hover:underline"
          >
            ← Zurück zu DUFYND
          </AcquisitionInternalLink>

          <h1 className="mt-5 text-3xl font-semibold tracking-[-0.03em]">
            Bildnachweise
          </h1>
          <p className="mt-2 text-[13px] leading-5 text-(--ink-soft)">
            Hier dokumentiert DUFYND Urheber-, Lizenz- und
            Weiterverwendungshinweise für extern lizenzierte Produktbilder.
          </p>

          {credits.length ? (
            <div className="mt-6 space-y-4">
              {credits.map(({ product, visual }) => (
                <section
                  key={`${product.product_id}:${visual.url}`}
                  className="rounded-xl border border-(--line) bg-(--surface) p-4"
                >
                  <h2 className="text-[15px] font-semibold text-(--ink)">
                    {product.brand} {product.name} · {product.concentration}{" "}
                    {product.volume_ml} ml
                  </h2>
                  <p className="mt-2 text-[13px] leading-5 text-(--ink-soft)">
                    Bild: {visual.attribution_text}
                  </p>
                  <p className="mt-1 text-[13px] leading-5 text-(--ink-soft)">
                    Lizenz:{" "}
                    {visual.license_url ? (
                      <a
                        href={visual.license_url}
                        target="_blank"
                        rel="license noopener noreferrer"
                        className="font-medium text-(--accent-ink) hover:underline"
                      >
                        {visual.license_name}
                      </a>
                    ) : (
                      visual.license_name
                    )}
                    {visual.share_alike_required ? " · ShareAlike" : ""}
                  </p>
                </section>
              ))}
            </div>
          ) : (
            <p className="mt-6 rounded-xl border border-(--line) bg-(--well)/50 p-4 text-[13px] leading-5 text-(--ink-soft)">
              Aktuell sind keine extern lizenzierten Produktbilder im
              öffentlichen DUFYND-Katalog aktiv.
            </p>
          )}
        </article>

        <LegalFooter />
      </div>
    </main>
  );
}
