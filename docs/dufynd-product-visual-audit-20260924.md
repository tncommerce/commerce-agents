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

The former detail hero used `object-cover`. In a square hero, each 4:3 landscape image lost up to 25% of its horizontal span, and each 4:5 portrait image lost up to 20% of its vertical span before any hover effect. Sixteen of the 32 editorial images have a non-square ratio. The new detail hero uses `contain` and a blurred decorative fill from the same source image. Card previews still intentionally fill their small slots; clicking a card reveals the complete image.

The 32 editorial scenes are synthetic or stylized illustrations. Their presence in the catalog does not establish that the label, glass, cap or bottle shape is an exact product depiction. Detail pages identify these images as stylized and say that bottle details may differ. The Naxos cutout is the only currently linked transparent product layer; the background image remains decorative.

## Release decisions for future visuals

| Item | Current decision | Missing evidence before a true product layer |
| --- | --- | --- |
| Naxos | Use existing verified cutout plus editorial depth background. | Visual QA at mobile and desktop sizes. |
| Bois Impérial | Keep the existing editorial scene; no new product cutout is linked. | A transparent, rights-cleared front bottle verified against the actual product, including cap, label, and glass. |
| Remaining 30 editorial products | Preserve original scene and uncropped detail presentation. | Product-by-product visual fidelity review and approved front packshot/cutout. |

The interactive depth treatment rotates and lights image layers; it is not a 3D mesh or an exploded view. An exploded view should wait for verified separate components or a faithful model. Do not infer cap geometry, atomizer, or bottle internals from generated artwork.

## QA checklist

- Confirm the complete bottle and text remain in view at 320, 390, 768 and 1440 CSS pixels.
- Verify that Naxos foreground and blurred background render as separate layers, with no doubled label in the foreground.
- Confirm reduced-motion preference removes perspective motion and glint.
- Check keyboard navigation and visible labels of offers, comparisons and related products.
- Review each proposed product cutout against a lawful source image before linking it as a verified layer.
