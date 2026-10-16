# DUFYND visual homepage

The homepage makes perfume recognition and the next useful action visible
before the secondary notes atlas. It does not change the public product
projection, merchant offers, tracking contract, analytics consent or release gate.

## Composition

1. `AtelierHero`: original generic glass bottle, catalogue search, discovery,
   comparison and offer-section navigation.
2. `AtelierSelection`: an offset editorial sequence of three original photographs
   in an explicitly named top Parfümerie showcase, with merchant-only destinations.
3. `HomeComparison`: two actual published fragrances and documented notes,
   linked to a preselected comparison. No fabricated product photography.
4. `HomeOffers`: independently licensed Lancôme photograph and the purchase
   path, with an internal Rabanne offer entry. No hard-coded price or stock.
5. Existing audience/profile catalogue paths, `ScentWorlds` native notes-atlas
   disclosure, advisor, personal library, partner discovery and disclosures.

`VisualHome.module.css` scopes the new homepage layout. Existing catalogue and
product styles are unchanged. Existing attribution-aware internal links and
native GET search continue to work. The homepage uses no new analytics event.

## Hero material and fallback

`PerfumeObject` presents an original generic study, not a product sold by DUFYND.
`perfumeSpatialRenderer` uses pinned Three.js with authored volumetric geometry,
separate liquid/glass/atomizer/cap meshes and a procedural studio environment.
It loads no model, HDRI, remote texture, video or paid asset. A prerendered image
of the same scene is present in server HTML before JavaScript or WebGL starts.

The renderer is dynamically imported only for visible, eligible devices after an
idle opportunity. Reduced motion, Save-Data, slow connections, low reported memory
or core count, unavailable WebGL and identified software renderers retain the
image path. Initialisation failure and context loss also restore the image.
Changing to reduced motion during import cannot reactivate WebGL afterwards.
Static mode still offers closed/open images through the same button; no-JavaScript
mode presents the closed object without a nonfunctional control.

An explicit keyboard/touch button opens the cap and atomizer over 880 ms. Liquid
remains contained. Fine pointers can inspect the object through restrained tilt.
The renderer sleeps at rest, outside the viewport and in hidden documents; it
disposes GPU resources on unmount. Pixel ratio is capped independently for mobile
and desktop. Local software-GPU evidence cannot establish hardware-GPU performance.

Motion has one purpose: reveal the object or indicate an actionable element.
Links and product hover use short 180–220 ms transitions; content is never hidden
behind a scroll-reveal prerequisite. Reduced motion removes those transitions.
The editorial Bodoni Moda font is self-hosted by Next; its OFL is bundled under
`public/fonts`. Three.js's MIT license is under `public/licenses`.

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

`public/visual-notes/sources.json` and `CREDITS.md` record botanical illustration
provenance, author, exact download, license, transformation and checksum. These
assets illustrate documented note profiles; they are not branded product
photographs, ingredient evidence or formula claims. The comparison exposes native
image credits next to the visual, independently of the product-photo contract.

## Verification

Run `node scripts/test-home-visual-assets.mjs` in the storefront for exact
identity, merchant-destination, attribution and fail-closed checks. It is also
part of prebuild. `node scripts/test-botanical-assets.mjs` checks the five reviewed
botanical source bindings, file hashes and displayed credits, including negative
cases for changed bytes, provenance, roles and removed attribution. It does not
infer permission from the image host. Run `npm run build` for the existing public
export gates.

`scripts/visual-reset-qa.mjs` accepts `--base-url` and `--out` and only permits
a local server. It captures 320/390/768/1024/1440 px, scroll journeys, search,
comparison navigation, photo contexts, denied-consent analytics suppression,
real WebGL geometry and part movement, sleeping frames, device fallback paths,
reduced-motion preference races, keyboard interaction, missing images and no
JavaScript. The software-GPU QA fixture changes browser capability reporting only;
there is no application URL or production override that bypasses device gates.
All API calls are local fixtures and merchant clickout routes are blocked.
Its LCP/CLS values are local diagnostics, not production field measurements.
The existing full visual suite includes this check and retains catalogue,
offer, search, attribution and consent coverage.

Screenshots certify the reviewed source/build only. A production release
requires its own owner/release gate; a development PR is not deployment approval.
