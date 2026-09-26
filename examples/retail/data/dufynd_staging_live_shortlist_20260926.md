# DUFYND staging to live: five product work queue

Prepared on 2026-09-26 from the PR #72 staging, mapping, image queue, live catalog and offer snapshots. This is an operational shortlist, not a release manifest or permission to publish. All five are women fragrances, none overlaps the 33 live fragrance identities, and all have non-provisional community data and deterministic recommendation profiles.

| Priority | Exact staged variant | Existing merchant mappings | Existing release | Image state | Current purchase offer |
| --- | --- | --- | --- | --- | --- |
| 1 | YSL Libre Eau de Parfum 90 ml (`SC-YSL-LIBRE-EDP-90`) | Douglas parent 5000005003, selected variant 289703; flaconi SKU 80041833-90; GTIN 3614272648425 | 01 | Source/rights check pending | Douglas €119, free shipping, in stock |
| 2 | Guerlain Mon Guerlain Eau de Parfum 100 ml (`SC-GUERLAIN-MON-GUERLAIN-EDP-100`) | Douglas parent 3001034674, selected variant 959272; perfumetrader SKU 60481349; GTIN 3346470131408 | 02 | Source/rights check pending | Douglas €119, free shipping, in stock |
| 3 | Burberry Goddess Eau de Parfum 100 ml (`SC-BURBERRY-GODDESS-EDP-100`) | Douglas parent 5011035040, selected variant 1122570; flaconi SKU 90001263-0001775; GTIN 3616302020652 | 02 | Source/rights check pending | Douglas €99, free shipping, in stock |
| 4 | Prada Paradoxe Eau de Parfum 90 ml (`SC-PRADA-PARADOXE-EDP-90`) | Douglas parent 5010687030, selected variant 1027980; flaconi SKU 80070411-90; GTIN 3614273760164 | 02 | Source/rights check pending | Douglas €119, free shipping, in stock |
| 5 | Parfums de Marly Delina Eau de Parfum 75 ml (`SC-PDM-DELINA-EDP-75`) | Douglas parent 5010758028, selected variant 968233; flaconi GTIN fallback 3700578501998 without a merchant SKU | 01 | Source/rights check pending | Douglas €285, free shipping, in stock |

The original mappings and manufacturer page evidence were researched on 2026-09-19. On 2026-09-26 at 04:44 UTC the five exact variants were checked on Douglas product pages in a browser; the selected size, regular price, free shipping, online stock and direct URL were visible. The conditional `Code:Online` discounts are deliberately not used as the offer price. Each snapshot row in `merchant_offers.json` has its own variant-specific `product_url` and timestamp; it expires under the 72-hour freshness gate and must be refreshed before release. No affiliate tracking link or image reuse right is asserted. flaconi showed a browser security challenge, so its price and stock were not verified. The two existing release manifests retain their sequence and write guards; this cross-release list does not bypass either.

The product-specific promotion dry run now reports **0 ready / 5 blocked**. Every product has one eligible direct purchase offer and zero tracked affiliate offers; the only remaining blocker on each is `missing_approved_image`. This is a time-limited result because offer freshness changes automatically.

## Product by product next work

1. Libre: Resolve permission to use an exact front bottle image. Refresh the 90 ml price, stock and link before release. The finished Libre social short is content support, not an automatically approved commerce image.
2. Mon Guerlain: Resolve source and reuse rights for the exact product image; refresh the 100 ml offer. Its finished short can support a later launch, not product imagery approval.
3. Goddess: Resolve exact-bottle image rights and refresh the 100 ml offer. Reject any future offer that points to Intense or a refill.
4. Paradoxe: Resolve the 90 ml EDP image rights and refresh the offer. Keep it distinct from Paradoxe Intense or the refill.
5. Delina: Resolve exact 75 ml EDP image rights and refresh the offer. The flaconi mapping has only a GTIN fallback and needs a separate exact landing-page review before import. Distinguish Delina from Exclusif and La Rosée.

## Guarded continuation

Affiliate routing is optional and may break a tie only at equal total customer price. Refresh the offers and confirm each link still opens the exact selected variant. Obtain an explicitly permitted feed, manufacturer or licensed image and visually approve the correct bottle. Then run staging QA, a product-specific promotion dry run, release gate and mobile product-page QA. Keep `write_enabled` and all existing manifest dependencies unchanged until a separate daytime release review.

**DAYTIME APPROVAL REQUIRED – LIVE RELEASE:** No product above is ready for a live write. Do not approve release based on this shortlist alone.
