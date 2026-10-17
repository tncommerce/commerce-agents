import {
  originalPhotoFor,
  type FragranceVisualAsset,
  type StaticFragrance,
} from "./fragranceCatalog";

// Placement is part of the permission. Feed access and verified fidelity alone
// never authorize a photograph on a new surface or beside another merchant.
export const HOME_EDITORIAL_PRODUCT_ID =
  "SC-LANCOME-LA-VIE-EST-BELLE-EDP-100";

const EDITORIAL_IMAGE_URL =
  "https://fooddrinkssuppliers.com/media/cosmetics/3605533286555.webp";

export const HOME_PARTNER_PRODUCTS = [
  {
    productId: "SC-YSL-LIBRE-EDP-90",
    imageUrl:
      "https://www.topparfuemerie.de/media/catalog/product/8/5/856448_3614272648425_051.png",
    merchantProductUrl:
      "https://www.topparfuemerie.de/yves-saint-laurent-libre-edp-vapo",
    displayedVolumeMl: 90,
    destinationRequiresSizeSelection: true,
  },
  {
    productId: "SC-PDM-DELINA-EDP-75",
    imageUrl:
      "https://www.topparfuemerie.de/media/catalog/product/8/2/825869_3700578501998_051.png",
    merchantProductUrl:
      "https://www.topparfuemerie.de/parfums-de-marly-delina-edp-nat-spray",
    displayedVolumeMl: 75,
    destinationRequiresSizeSelection: true,
  },
  {
    productId: "SC-YSL-BLACK-OPIUM-EDP-90",
    imageUrl:
      "https://www.topparfuemerie.de/media/catalog/product/7/8/787670_3365440787971_051.png",
    merchantProductUrl:
      "https://www.topparfuemerie.de/yves-saint-laurent-black-opium-edp-nat-spray",
    displayedVolumeMl: 90,
    destinationRequiresSizeSelection: true,
  },
] as const;

export type HomeVisualPlacement =
  | { kind: "editorial" }
  | {
      kind: "merchant_showcase";
      merchantId: "top-parfuemerie";
      destinationUrl: string;
    };

/**
 * Homepage-only eligibility, narrower than historical catalogue presentation.
 * TOP's 2026-10-06 permission is merchant-bound. Its product-family destinations
 * default to 30 ml; cards must identify the pictured size and ask the visitor to
 * select a size at the merchant. This contract establishes no offer or tracking.
 * Keep the original bitmap contained and render any photograph attribution.
 */
export function getHomeVisual(
  fragrance: StaticFragrance,
  placement: HomeVisualPlacement,
): FragranceVisualAsset | null {
  if (fragrance.concentration !== "Eau de Parfum") return null;

  const original = originalPhotoFor(fragrance);
  if (!original || original.fidelity_status !== "verified") return null;

  if (placement.kind === "editorial") {
    return fragrance.product_id === HOME_EDITORIAL_PRODUCT_ID &&
      fragrance.volume_ml === 100 &&
      original.url === EDITORIAL_IMAGE_URL &&
      original.provenance === "licensed" &&
      original.license_name === "CC BY-SA 3.0" &&
      original.license_url === "https://creativecommons.org/licenses/by-sa/3.0/" &&
      original.attribution_text === "Open Beauty Facts contributors" &&
      original.share_alike_required === true
      ? original
      : null;
  }

  if (
    placement.kind !== "merchant_showcase" ||
    placement.merchantId !== "top-parfuemerie"
  ) return null;

  const approved = HOME_PARTNER_PRODUCTS.find(
    (entry) => entry.productId === fragrance.product_id,
  );
  return approved &&
    fragrance.volume_ml === approved.displayedVolumeMl &&
    original.url === approved.imageUrl &&
    original.provenance === "merchant_feed" &&
    placement.destinationUrl === approved.merchantProductUrl
    ? original
    : null;
}
