# DUFYND visual homepage

The homepage makes perfume recognition and the next useful action visible
before the secondary notes atlas. It does not change the public product
projection, merchant offers, tracking contract, analytics consent or release gate.

## Composition

1. `AtelierHero`: original generic glass bottle, catalogue search, discovery,
   comparison and offer-section navigation.
2. `AtelierSelection`: three original photographs in an explicitly named
   top Parfümerie partner showcase, with merchant-only destinations.
3. `HomeComparison`: two actual published fragrances and documented notes,
   linked to a preselected comparison. No fabricated product photography.
4. `HomeOffers`: independently licensed Lancôme photograph and the purchase
   path, with an internal Rabanne offer entry. No hard-coded price or stock.
5. Existing audience/profile catalogue paths, notes atlas, advisor, personal
   library, partner discovery and disclosures.

`VisualHome.module.css` scopes the new homepage layout. Existing catalogue and
product styles are unchanged. Existing attribution-aware internal links and
native GET search continue to work. The homepage uses no new analytics event.

## Hero material and fallback

`PerfumeObject` is original SVG geometry with layered gradients and CSS
perspective, not a photograph or a product sold by DUFYND. The complete shape
is server rendered. It needs no WebGL context, model download, video, external
library or image generation. Fine pointers can tilt it by a few degrees.
An explicit keyboard/touch button lifts the cap to reveal the atomizer.
There is no autoplay or continuous render loop. Reduced motion disables
transitions and tilt; the static object and all navigation remain available.

## Photo placement contract

`lib/homeVisualAssets.ts` requires an exact existing public photo registration,
variant and source URL. Fidelity alone does not establish permission.

| Placement | Product | Basis and constraint |
| --- | --- | --- |
| Internal editorial | La Vie est Belle EDP 100 ml | Existing Open Beauty Facts CC BY-SA 3.0 source, full bitmap, visible credit/license/ShareAlike |
| TOP showcase | Libre EDP 90 ml | Existing TOP original, TOP product-family destination only |
| TOP showcase | Delina EDP 75 ml | Existing TOP original, TOP product-family destination only |
| TOP showcase | Black Opium EDP 90 ml | Existing TOP original, TOP product-family destination only |

TOP's 2026-10-06 written permission covers DUFYND/Affiliate integration with
purchase conclusion at TOP. The showcase does not redirect its photographs
to Notino offers or claim general website/social image rights. TOP destinations
can default to 30 ml, so pictured size and size selection at the merchant are
explicit. These plain merchant links establish no new verified tracking mapping.
No price, stock or popularity claim is inferred. Native anchors prevent Next
prefetch; QA never follows them. `rel=sponsored noopener noreferrer` preserves
the explicit commercial context and suppresses referrer data.

Rabanne remains image-free. Historical generated branded cutouts, private
photo-review rows and unproven exact-size Commons candidates are excluded.
Existing product-page imagery is not broadened by this homepage change.

## Verification

Run `node scripts/test-home-visual-assets.mjs` in the storefront for exact
identity, merchant-destination, attribution and fail-closed checks. It is also
part of prebuild. Run `npm run build` for the existing public export gates.

`scripts/visual-reset-qa.mjs` accepts `--base-url` and `--out` and only permits
a local server. It captures 320/390/768/1024/1440 px, scroll journeys, search,
comparison navigation, photo contexts, denied-consent analytics suppression,
reduced motion, keyboard interaction, missing images and no JavaScript.
All API calls are local fixtures and merchant clickout routes are blocked.
Its LCP/CLS values are local diagnostics, not production field measurements.
The existing full visual suite includes this check and retains catalogue,
offer, search, attribution and consent coverage.

Screenshots certify the reviewed source/build only. A production release
requires its own owner/release gate; a development PR is not deployment approval.
