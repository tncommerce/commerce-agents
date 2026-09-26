# DUFYND staging to live: five product work queue

Prepared on 2026-09-26 from the PR #72 staging, mapping, image queue, live catalog and offer snapshots. This is an operational shortlist, not a release manifest or permission to publish. All five are women fragrances, none overlaps the 33 live fragrance identities, and all have non-provisional community data and deterministic recommendation profiles.

| Priority | Exact staged variant | Existing merchant mappings | Existing release | Image state | Current purchase offer |
| --- | --- | --- | --- | --- | --- |
| 1 | YSL Libre Eau de Parfum 90 ml (`SC-YSL-LIBRE-EDP-90`) | Douglas SKU 5000005003; flaconi SKU 80041833-90; GTIN 3614272648425 | 01 | Source/rights check pending | None |
| 2 | Guerlain Mon Guerlain Eau de Parfum 100 ml (`SC-GUERLAIN-MON-GUERLAIN-EDP-100`) | Douglas SKU 3001034674; perfumetrader SKU 60481349; GTIN 3346470131408 | 02 | Source/rights check pending | None |
| 3 | Burberry Goddess Eau de Parfum 100 ml (`SC-BURBERRY-GODDESS-EDP-100`) | Douglas SKU 5011035040; flaconi SKU 90001263-0001775; GTIN 3616302020652 | 02 | Source/rights check pending | None |
| 4 | Prada Paradoxe Eau de Parfum 90 ml (`SC-PRADA-PARADOXE-EDP-90`) | Douglas SKU 5010687030; flaconi SKU 80070411-90; GTIN 3614273760164 | 02 | Source/rights check pending | None |
| 5 | Parfums de Marly Delina Eau de Parfum 75 ml (`SC-PDM-DELINA-EDP-75`) | Douglas SKU 5010758028; flaconi GTIN fallback 3700578501998 without a merchant SKU | 01 | Source/rights check pending | None |

The mappings and manufacturer page evidence were researched on 2026-09-19. They establish a starting point for checking the exact variant; they do not establish current price, stock, clickout validity or image reuse rights. The merchant offer snapshot contains four rows for existing live fragrances and zero rows for any staged fragrance. All five fail `missing_current_purchase_destination` and `missing_approved_image` in a dry run. The two old release manifests also retain their sequence and write guards; this cross-release list does not bypass either.

## Product by product next work

1. Libre: Verify the 90 ml merchant product and price including shipping, stock, and destination URL against GTIN 3614272648425. Resolve permission to use an exact front bottle image. The finished Libre social short is content support, not an automatically approved commerce image.
2. Mon Guerlain: Verify the 100 ml variant at Douglas or perfumetrader, current total price and destination. Resolve source and reuse rights for the product image. Its finished short can support a later launch, not product imagery approval.
3. Goddess: Verify the 100 ml merchant SKU/GTIN and source permissions. Reject any offer that points to the Intense or refill variant.
4. Paradoxe: Verify the 90 ml EDP rather than Paradoxe Intense or a refill. Check image rights independently of product identity.
5. Delina: Verify the 75 ml EDP against the Douglas SKU; the flaconi mapping has only GTIN fallback and needs exact landing-page review before import. Distinguish Delina from Exclusif and La Rosée.

## Guarded continuation

For each offer, record the actual merchant product URL, exact variant, checked timestamp, EUR price, shipping, stock and mapping evidence. Affiliate routing is optional and may break a tie only at equal total customer price. Confirm the link opens the exact product. Obtain an explicitly permitted feed, manufacturer or licensed image and visually approve the correct bottle. Then run staging QA, a product-specific promotion dry run, release gate and mobile product-page QA. Keep `write_enabled` and all existing manifest dependencies unchanged until a separate daytime release review.

**DAYTIME APPROVAL REQUIRED – LIVE RELEASE:** No product above is ready for a live write. Do not approve release based on this shortlist alone.
