# DUFYND multi-visual product spec · 25 September 2026

DUFYND should stop treating one image as the answer to every product surface. The next storefront increment should support multiple explicit visual roles while remaining backward-compatible with the current catalog.

## Goal

A fragrance detail page can have several visuals without confusing editorial art with product truth:

- **primary** — exact or fidelity-approved product depiction;
- **cutout** — transparent product-truth layer for depth/compositing;
- **editorial** — DUFYND atmosphere/campaign image;
- **macro** — verified close-up of cap, plaque, label, glass or material;
- **model_3d** — verified GLB/USDZ-style interactive object when available.

The UI should always know which role it is rendering. An editorial scene must never silently become the product-truth layer just because no primary exists.

## Proposed source shape

Keep the existing fields during migration, then add a structured optional visual collection to the fragrance source data:

```json
{
  "visuals": [
    {
      "role": "primary",
      "url": "/products/...",
      "provenance": "dufynd_generated",
      "fidelity_status": "verified",
      "variant": "100ml"
    },
    {
      "role": "editorial",
      "url": "/products/...",
      "provenance": "dufynd_generated",
      "fidelity_status": "editorial_only"
    },
    {
      "role": "cutout",
      "url": "/products/...",
      "provenance": "rights_cleared",
      "fidelity_status": "verified"
    }
  ]
}
```

Do not put free-form rights claims in the public UI. Provenance should be backed by the existing internal rights/audit records.

## Migration order

1. Preserve `image_url` as the current editorial fallback so no existing page breaks.
2. Preserve `product_cutout_url` and `product_model_3d_url`.
3. Add `visuals` as optional structured data.
4. Teach the catalog adapter to select:
   - verified primary first;
   - verified cutout second;
   - editorial fallback last.
5. Detail pages may expose a compact gallery when two or more distinct visuals exist.
6. Catalog cards should use one stable primary/card asset, not rotate through editorial images.
7. Social/content assets remain outside the storefront gallery unless explicitly approved for product use.

## UI behaviour

### Catalog card

Use one image only. Priority:

1. verified primary;
2. verified cutout on DUFYND stage;
3. editorial image with safe-area treatment.

Avoid carousels inside catalog cards; they add friction and make comparison harder.

### Product detail hero

Use the best verified truth layer if available. The current accord-driven background remains around it.

If only editorial exists, keep the existing visible disclosure that the image is a stylized DUFYND staging and bottle details may differ.

### Detail gallery

Add only when at least two useful roles exist. Suggested order:

1. primary/truth;
2. editorial;
3. macro;
4. alternate editorial;
5. 3D entry point as a separate interaction rather than a fake still.

On mobile, gallery controls must remain thumb-friendly and should not increase the initial hero height excessively.

## 3D relationship

3D is a visual role, not a replacement for all still imagery. Even a verified GLB still needs a lightweight poster/primary image for loading, accessibility, social previews and devices where WebGL is unavailable.

The current `FragranceModel3D` fallback pattern is therefore correct: poster/cutout first, interactive model only when a validated model URL exists and the viewer is ready.

## Quality gates

Every proposed primary/cutout/macro/model must carry an explicit status:

- `verified`
- `pending_review`
- `editorial_only`
- `rejected`

Only `verified` assets may be treated as product truth.

Minimum verification for generated primaries:

- exact product/concentration/variant;
- full uncropped silhouette;
- cap/atomizer and shoulder geometry;
- plaque/label position and wording;
- no contradictory volume text;
- material and colour plausible against the reference;
- 320 / 390 / 768 / 1440 presentation check;
- source/reference and generation provenance recorded.

## First migration candidates

Use products where the benefit is clearest:

1. **Naxos** — verified cutout + existing editorial + future bottle-free editorial; ideal first gallery/depth test.
2. **Creed Absolu Aventus** — current editorial stays editorial; future reference-faithful primary can be added without deleting the scene.
3. **Prada L'Homme** — future verified primary + current scene retained only if useful as editorial.
4. **Stronger With You Intensely** — same pattern as Prada.
5. **Bois Impérial** — editorial now; verified cutout later if rights/fidelity are solved.

## Implementation status · 25 September 2026

The first backward-compatible slice is now implemented on the integration branch:

- `StaticFragrance` understands structured `visuals` metadata with explicit role and fidelity status;
- Naxos is the first pilot with a verified cutout plus separate editorial artwork;
- the fragrance detail page shows a compact `Weitere Ansichten` gallery only when at least two explicit visuals exist;
- editorial and verified-product roles remain visibly distinct;
- regression tests validate role/status values, prevent duplicate visual URLs and keep the Naxos verified cutout aligned with the legacy catalog field;
- existing fragrances without `visuals` continue to use current still-image fallbacks;
- `model_3d` is a structured visual role, but only an explicitly `verified` model asset can reach the interactive viewer; legacy model attributes cannot bypass the fidelity gate.

The card/hero selection layer now follows the documented priority centrally: verified `primary` first, verified `cutout` second, then an editorial fallback. Legacy cutouts without structured verification are not silently promoted to product truth. Naxos therefore continues to use its verified cutout, while the other current catalog products remain editorial until a fidelity-approved truth asset is added.

The remaining visual block is narrower: add more verified assets when they are approved, extend the gallery with approved macro assets, and continue browser QA across mobile and desktop. No current P0 editorial image has been promoted to product truth.

## Next implementation block

The original multi-visual implementation block is complete on PR #67. The remaining work should build on that system rather than recreate it:

- review the responsive browser-QA captures at 320 / 390 / 768 / 1440 and fix only reproducible layout/fidelity defects;
- keep Naxos on its verified cutout and add a bottle-free editorial background only when a suitable asset is approved;
- add future `primary` / `macro` / `model_3d` assets only after the fidelity gate passes;
- keep Creed Absolu Aventus, Prada L'Homme, Stronger With You Intensely, Sospiro Vibrato and other unverified scenes editorial-only until exact-reference review is complete;
- extend structured visual metadata product-by-product instead of reviving legacy implicit cutout priority;
- do not start paid generation, merge or deploy without user sign-off.
