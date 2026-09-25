# DUFYND product visual audit · 24 September 2026

Scope: the 41 local images referenced by `examples/retail/data/catalog.json`, and the product detail presentation in the storefront. This is an asset and layout audit, not a claim that every illustrated bottle matches its retail product.

## Inventory and image safety

| Finding | Count | Action |
| --- | ---: | --- |
| Local catalog images present and decodable | 41/41 | Keep the existing asset integrity gate. |
| DUFYND editorial scenes | 32 | Show as illustrations; keep product fidelity review separate. |
| Other catalog images | 9 | Retain their existing credits and provenance. |
| Square / landscape / portrait | 16 / 18 / 7 | Product detail hero now preserves all edges regardless of aspect ratio. |
| Verified transparent product cutout linked in catalog | 1 (Naxos) | Layer it over its editorial scene for the 3D pilot. |

The former detail hero used `object-cover`. In a square hero, each 4:3 landscape image lost up to 25% of its horizontal span, and each 4:5 portrait image lost up to 20% of its vertical span before any hover effect. Sixteen of the 32 editorial images have a non-square ratio. The detail hero uses `contain` and a blurred decorative fill from the same source image. The catalog grid also uses `contain`: its wide slots previously clipped portrait bottles, including the top of the Supremacy Collector's Edition bottle. The complete source image is now visible in the catalog card against a blurred fill.

The 32 editorial scenes are synthetic or stylized illustrations. Their presence in the catalog does not establish that the label, glass, cap or bottle shape is an exact product depiction. Detail pages identify these images as stylized and say that bottle details may differ. The Naxos cutout is the only currently linked transparent product layer; the background image remains decorative.

## DUFYND product-image policy

DUFYND does not treat an official manufacturer packshot as automatically preferable to a generated visual. The primary image may be a DUFYND-generated render when it is more compelling and fits the dynamic depth/3D presentation, but it must pass a product-fidelity gate first: complete bottle silhouette, cap, label/plaque, proportions, glass/material cues and visible typography must match the intended retail product closely enough that the image cannot mislead a shopper.

An external original image may be used only when its commercial-use basis is documented (for example an authorised affiliate/feed asset or another rights-cleared source). A publicly accessible manufacturer image is not assumed to be reusable merely because it is online.

For the storefront, the preferred asset stack is:

1. a complete, uncropped primary bottle visual with safe area;
2. an optional verified transparent bottle/cutout for interactive depth or true 3D;
3. one or more DUFYND editorial/macro visuals for attraction and atmosphere;
4. a real 3D model only after bottle geometry and surface details pass fidelity QA.

Generated editorial art must not silently become the source of truth for bottle geometry. When fidelity is not verified, it remains labelled/presented as stylised artwork.

## Affiliate-feed originals and image rights

Awin's current publisher documentation describes product feeds as a publisher-facing source of product links, prices, descriptions and images that partners can display when promoting advertiser products. DUFYND therefore treats an image coming from an authorised advertiser feed as a stronger rights basis than a publicly accessible manufacturer image copied from the open web.

That is still not a blanket licence for every advertiser asset. Before a feed image can become a DUFYND primary product visual, all of the following must be true:

- DUFYND is currently approved for the advertiser/program;
- the image comes from the advertiser's official affiliate feed or another documented authorised asset source;
- current advertiser/program terms do not add a conflicting restriction;
- the asset is used within the DUFYND publisher service and is not materially altered beyond presentation-safe resizing/cropping;
- exact product/variant/size identity is verified;
- provenance is recorded in the machine-readable rights registry.

If no documented source right exists, DUFYND should prefer its own generated editorial asset while clearly keeping product-fidelity and truth-in-depiction gates separate.

## Visual review pass · 25 September 2026

A contact-sheet audit of all 32 DUFYND editorial fragrance scenes was generated from the actual repository assets, together with a simulation of the current card safe-area treatment. This separates two different problems: **layout cropping** and **source-image fidelity**. The layout crop issue is structurally addressed by the new contain/safe-area treatment, but several source visuals still need replacement because the illustrated bottle itself is not reliable enough.

### P0 — replace before treating the scene as a trusted primary depiction

| Asset | Finding | Decision |
| --- | --- | --- |
| `creed-absolu-aventus-editorial.png` | The illustrated bottle itself reads **75 ML / 2.5 FL.OZ**, while the DUFYND catalog product is Absolu Aventus 100 ml. | Replace with a 100 ml-faithful DUFYND render; do not use this scene as product truth. |
| `xerjoff-naxos-editorial.png` | The illustrated rounded white bottle visibly conflicts with DUFYND's separately verified Naxos cutout geometry. | Keep only as a blurred/de-emphasised atmosphere until a bottle-free or faithful Naxos editorial is available. |
| `armani-swy-intensely-editorial.png` | The scene uses a glossy black spherical stopper. Armani describes the Stronger With You bottle as closed by its characteristic cast-iron-grey metal cap. | Replace with a geometry-faithful render based on an authorised/reference product image. |
| `prada-lhomme-editorial.png` | The scene presents a bright silver/clear front treatment. Prada describes L'Homme's bottle as cloaked in black Saffiano leather with a raised silver Prada logo. | Replace; current scene is attractive but not reliable enough as the primary product depiction. |

Reference checks for the two externally verified P0 items:
- Armani Stronger With You Intensely: https://www.armanibeauty.de/dufte/herrenduft/stronger-with-you/stronger-with-you-intensely-eau-de-parfum/3614272225718.html
- Prada L'Homme Eau de Toilette: https://www.prada-beauty.com/fragrance/lhomme-prada/lhomme-prada-eau-de-toilette/8435137749607.html

### P1 — visually strong enough to keep as editorial, but verify bottle details before promotion to product-truth status

Prioritise side-by-side verification for `al-haramain-detour-noir-editorial.png`, `creed-aventus-editorial.png`, `armaf-club-de-nuit-intense-man-editorial.png` and `maison-asrar-vanguard-editorial.png`. These scenes are visually usable, but distinctive bottle geometry, cap/ornament details or label typography should be checked against an authorised source before DUFYND presents them as exact product depictions.

### P2 — keep for now as editorial scenes

The remaining scenes pass the first composition review: the bottle is fully visible, the current safe-area treatment prevents layout clipping, and the presentation is consistent enough for the DUFYND editorial layer. This is **not** an assertion that every label and surface detail is exact. They remain subject to product-by-product fidelity review before becoming verified primary product layers.

The generated audit artifact itself is temporary QA evidence and must not be merged into the production website. The temporary CI artifact job should be removed after the visual review is complete.

## Release decisions for future visuals

| Item | Current decision | Missing evidence before a true product layer |
| --- | --- | --- |
| Naxos | Use the existing verified cutout on the clean dynamic product stage; do not layer the inaccurate editorial bottle behind it. | Visual QA at mobile and desktop sizes. |
| Bois Impérial | Keep the existing editorial scene; no new product cutout is linked. | A transparent, rights-cleared front bottle verified against the actual product, including cap, label, and glass. |
| Remaining 30 editorial products | Preserve original scene and uncropped detail presentation. | Product-by-product visual fidelity review and approved front packshot/cutout. |

The interactive depth treatment rotates and lights image layers; it is not a 3D mesh or an exploded view. An exploded view should wait for verified separate components or a faithful model. Do not infer cap geometry, atomizer, or bottle internals from generated artwork.

## QA checklist

- Browser screenshot verification at 320, 390, 768 and 1440 CSS pixels remains open. The cloud browser blocks the local preview URL; a passing static build is not visual proof.
- Verify that Naxos uses only the verified cutout on the dynamic product stage, with no second/inaccurate bottle visible behind it.
- Confirm reduced-motion preference removes perspective motion and glint.
- Check keyboard navigation and visible labels of offers, comparisons and related products.
- Review each proposed product cutout against a lawful source image before linking it as a verified layer.
