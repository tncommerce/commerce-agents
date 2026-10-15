import manifest from '../../data/dufynd_photo_integration_review.json';
import { LIVE_FRAGRANCES } from './fragranceCatalog';

// This server-side catalogue is never the public original-photo registry.
// Public routes cannot request this placement through URL parameters.
export const PHOTO_REVIEW_ENABLED = process.env.DUFYND_CATALOG_REVIEW === '1';
export const PHOTO_REVIEW_ITEMS = PHOTO_REVIEW_ENABLED ? manifest.items.map(item => {
  const fragrance = LIVE_FRAGRANCES.find(f => f.product_id === item.product_id);
  if (!fragrance || fragrance.volume_ml !== item.volume_ml || fragrance.concentration !== item.concentration ||
      !item.owner_visual_approved || !item.exact_variant_verified || item.publication_authorized || item.offer_activation_authorized ||
      item.placement !== 'top_parfuemerie_private_review_only' || item.merchant_id !== 'top-parfuemerie' ||
      item.rights_basis_id !== 'awin_top_parfuemerie_feed_materials_20260928' || !/^[a-f0-9]{64}$/.test(item.image_sha256)) {
    throw new Error(`Invalid merchant-bound photo review: ${item.product_id}`);
  }
  return {...item, slug: fragrance.slug, image_url: `/__review-photos/${item.merchant_product_id}-${item.image_sha256}.png`};
}) : [];

export function photoReviewFor(productId: string) {
  return PHOTO_REVIEW_ITEMS.find(item => item.product_id === productId) || null;
}
