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

## Release decisions for future visuals

| Item | Current decision | Missing evidence before a true product layer |
| --- | --- | --- |
| Naxos | Use existing verified cutout plus editorial depth background. | Visual QA at mobile and desktop sizes. |
| Bois Impérial | Keep the existing editorial scene; no new product cutout is linked. | A transparent, rights-cleared front bottle verified against the actual product, including cap, label, and glass. |
| Remaining 30 editorial products | Preserve original scene and uncropped detail presentation. | Product-by-product visual fidelity review and approved front packshot/cutout. |

The interactive depth treatment rotates and lights image layers; it is not a 3D mesh or an exploded view. An exploded view should wait for verified separate components or a faithful model. Do not infer cap geometry, atomizer, or bottle internals from generated artwork.

## QA checklist

- Browser screenshot verification at 320, 390, 768 and 1440 CSS pixels remains open. The cloud browser blocks the local preview URL; a passing static build is not visual proof.
- Verify that Naxos foreground and blurred background render as separate layers, with no doubled label in the foreground.
- Confirm reduced-motion preference removes perspective motion and glint.
- Check keyboard navigation and visible labels of offers, comparisons and related products.
- Review each proposed product cutout against a lawful source image before linking it as a verified layer.
