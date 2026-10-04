# DUFYND TECH handoff — Delina + Libre approved-feed-image launch contract

Status: business evidence complete; TECH implementation required  
Date: 2026-10-04  
Base business state: `ec61c7161a6604ade405cb178e33e188493ffbd2`

## Scope boundary

This handoff does **not** authorize a Business-side runtime fix, publication, partner activation, or weaker product-truth rule. TECH should reconcile the existing launch contract so an `approved_feed_image` can become explicit verified remote product truth **only when every existing identity, rights, freshness and commerce gate passes**.

Do not relabel a merchant-feed image as `licensed` merely to satisfy the current launch test.

## Delina evidence

- Product: `SC-PDM-DELINA-EDP-75`
- Exact variant: Parfums de Marly Delina Eau de Parfum 75 ml
- Community data: 8.0/10, 2,555 ratings, non-provisional
- Feed image: `https://www.topparfuemerie.de/media/catalog/product/8/2/825869_3700578501998_051.png`
- Image status: `approved_feed_image`
- Image reviewed: `2026-10-01T09:49:00Z`
- Rights basis: `awin_top_parfuemerie_feed_materials_20260928`
- Rights checked: `2026-09-28`
- Staging still says `catalog_ready=false` with `approved_product_image_pending`; this must transition through a defined contract, not manual blocker deletion.
- Affiliate merchant: Notino / CJ
- Merchant product ID: `PDM0227`
- Verified deep link exists in canonical offers.
- Notino program is approved and Delina is inside the explicit `verified_product_only` live-activation scope.
- Current public Notino evidence refreshed at `2026-10-04T09:44:49Z`: €285, free shipping, available.
- Refresh evidence: `examples/retail/data/dufynd_notino_delina_libre_offer_refresh_20261004.json`.
- Canonical `merchant_offers.json` remains intentionally untouched by this Business-only handoff because direct freshness mutation changes derived Jarvis state fingerprints. Its committed timestamp remains `2026-10-01T14:17:32Z` and expires under the 72-hour runtime gate at `2026-10-04T14:17:32Z` UTC / `16:17:32` Europe/Berlin.
- TECH/promotion must ingest/revalidate the fresh evidence through the canonical supported state path and rebuild required derived state; do not copy a timestamp merely to pass freshness.

## Libre evidence

- Product: `SC-YSL-LIBRE-EDP-90`
- Exact variant: Yves Saint Laurent Libre Eau de Parfum, refillable bottle, 90 ml
- Community data: 7.5/10, 2,203 ratings, non-provisional
- Feed image: `https://www.topparfuemerie.de/media/catalog/product/8/5/856448_3614272648425_051.png`
- Image status: `approved_feed_image`
- Image reviewed: `2026-10-01T09:49:00Z`
- Rights basis: `awin_top_parfuemerie_feed_materials_20260928`
- Rights checked: `2026-09-28`
- Staging still says `catalog_ready=false` with `approved_product_image_pending`; do not remove this by hand.
- Affiliate merchant: Notino / CJ
- Merchant product ID: `VZR11010`
- Verified deep link exists in canonical offers.
- Notino program is approved and Libre is inside the explicit `verified_product_only` live-activation scope.
- Current public Notino evidence refreshed at `2026-10-04T09:44:49Z`: €119, free shipping, available.
- Refresh evidence: `examples/retail/data/dufynd_notino_delina_libre_offer_refresh_20261004.json`.
- Canonical `merchant_offers.json` remains intentionally untouched by this Business-only handoff because direct freshness mutation changes derived Jarvis state fingerprints. Its committed timestamp remains `2026-10-01T16:21:51Z` and expires under the 72-hour runtime gate at `2026-10-04T16:21:51Z` UTC / `18:21:51` Europe/Berlin.
- TECH/promotion must ingest/revalidate the fresh evidence through the canonical supported state path and rebuild required derived state; do not copy a timestamp merely to pass freshness.

## Existing blocker proven by PR #657

The promotion builder maps `approved_feed_image` to visual provenance `merchant_feed`. Current launch integrity currently expects a remote verified primary/cutout live product-truth visual to use `licensed` provenance. PR #657 correctly failed rather than silently weakening that rule.

Other tests also encode Libre/approved-feed candidates as staged/non-live and fail when the product is inserted directly into the live catalog. Treat these failures as contract evidence, not fixtures to edit until green.

## TECH acceptance criteria

1. Define an explicit product-truth class for approved merchant/feed images. Keep provenance `merchant_feed`; do not falsely rename it `licensed`.
2. A feed image may become verified primary/cutout product truth only when exact canonical product + exact volume/variant mapping passes and the image record contains reviewed-at, rights-basis and rights-checked evidence.
3. Preserve the auditable feed/merchant source identity and rights metadata in the live source record. Promotion must not discard those fields.
4. Keep URL/security requirements fail-closed: public HTTPS only, no unreviewed/unknown source.
5. Keep image rights independent from merchant routing. top Parfümerie image rights do not authorize top Parfümerie clickout routing.
6. Keep affiliate activation independent from image approval. A live Notino offer still requires the exact product to be inside the approved CJ activation scope, a verified tracked deep link, exact SKU and a <=72h eligible offer at promotion time.
7. Replace `approved_product_image_pending` only through the explicit validated promotion transition. Never delete the blocker manually as the fix.
8. Preserve negative tests: missing rights basis, missing review timestamp, unverified exact variant, wrong volume, stale offer, unapproved affiliate scope, unverified remote image and mismatched product identity must all remain blocked.
9. Update positive tests to recognize the new approved-feed-image contract without broadening acceptance to arbitrary remote images.
10. Dry-run Delina and Libre separately. Both must report the expected eligible affiliate offer and zero unrelated products.
11. Full CI must pass: Python 3.11, Python 3.12, web build, repo consistency, no-PyPI fallback and the relevant visual/product-truth suites.
12. After merge, verify new `scentai-mvp` HEAD and Production Smoke. Then verify each product page, eligible offer response, affiliate disclosure and `src/cmp/content` attribution.
13. Do **not** promote on the stale snapshots above. Refresh the exact Notino variant price/availability immediately before the promotion PR.
14. No `main` change, no PR #1 change and no Control-Plane/Supervisor/Jarvis runtime change are part of this handoff.

## Definition of done

Delina and Libre can each pass the normal promotion path with provenance `merchant_feed` and retained rights/variant evidence, while the same path still rejects a feed image lacking any required proof. The resulting live product remains independently gated by fresh user-value-first merchant offers and explicit affiliate activation.

