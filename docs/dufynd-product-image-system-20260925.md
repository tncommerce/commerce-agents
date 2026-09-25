# DUFYND product image system · 25 September 2026

The current audit confirms that one campaign image should not be forced into every DUFYND surface. The website already has a dynamic cutout/depth layer and optional true 3D support, so the visual library should be built around reusable product layers plus separate editorial worlds.

## Asset roles

### 1. Verified product layer — highest priority

Purpose: catalog cards, product-detail hero, comparison cards and the fallback before a true GLB model is ready.

Preferred deliverable:

- transparent PNG or WebP;
- canvas: 1600 × 2000 px (4:5) or larger at the same ratio;
- complete bottle, cap and base visible;
- 12–15% clear safe area around the silhouette;
- centered optical axis;
- no scenery, ingredients, hands, packaging box or typography outside the bottle;
- neutral studio lighting with material detail preserved;
- exact fragrance, concentration and intended retail variant;
- no invented logos, cap geometry, plaque shape, bottle engraving or volume marking.

A generated product layer is acceptable when it passes DUFYND's fidelity gate. It does not need to imitate a retailer photograph; it does need to depict the retail product faithfully.

### 2. Editorial hero

Purpose: emotional attraction and fragrance-world storytelling.

Preferred deliverable:

- 1920 × 1200 or 1600 × 1200 landscape;
- bottle may appear only if its geometry has already been verified;
- otherwise build a bottle-free ingredient/material world and let the verified product layer sit above it in the website;
- composition leaves a calm central/side region for the product layer;
- art direction follows the site's five visual worlds: amber, mineral, noir, silk and ember;
- do not repeat the same Mediterranean sunset/tabletop scene across the catalog.

This is the preferred method for DUFYND: **verified bottle layer + generated editorial world**. It gives the AI image much more creative freedom without risking a false product depiction.

### 3. Macro/detail

Purpose: gallery and premium storytelling.

Examples: cap material, plaque, embossed logo, glass edge, atomizer, velvet texture.

Only use a macro as product truth after exact-reference verification. Macro generations are more likely than wide scenes to invent typography or hardware, so they need a separate fidelity check.

### 4. Social vertical

Purpose: Shorts/Reels/TikTok.

- 1080 × 1920;
- may be much more cinematic;
- not automatically reused as catalog truth;
- exact bottle/reference rules still apply whenever the bottle is visible.

### 5. True 3D

Purpose: rotate, depth and future exploded-view interactions.

A GLB is activated only after silhouette, dimensions, cap, plaque/label and major materials pass visual QA. Until then the verified 2D product layer remains the source of truth.

## Website behavior

Catalog and product-detail layouts should never crop a verified product layer. `FragranceVisual` therefore uses containment and safe-area treatment for cutouts. Editorial backgrounds may crop decoratively because they are atmosphere, not the product source of truth.

For a 4:3 editorial source inside a portrait/tall product card, DUFYND should not zoom the image merely to fill the box. Prefer a dedicated product layer; the editorial image can remain in the gallery or as a blurred/background fill.

## First replacement batch

Priority order from the current audit:

1. **Creed Absolu Aventus 100 ml** — existing generated scene visibly says 75 ml / 2.5 fl oz; editorial only.
2. **Prada L'Homme EDT 100 ml** — current generated bottle treatment requires exact-reference rebuild.
3. **Giorgio Armani Stronger With You Intensely 100 ml** — cap/shoulder treatment requires exact-reference rebuild.
4. **Xerjoff Naxos 100 ml** — keep the existing verified cutout; replace the inaccurate bottle-bearing editorial backdrop with a bottle-free Naxos world.
5. **Creed Aventus 100 ml** — keep editorial status until the current packaging variant is deliberately chosen and verified.
6. **Sospiro Vibrato 100 ml** — next exact-reference review because the site already uses Vibrato heavily in content and the product layer should match the current house bottle precisely.

## Generation workflow

For every replacement:

1. record the authoritative product/reference source and variant;
2. create the verified product layer first;
3. compare silhouette, cap, label/plaque, typography and any visible volume marking side by side;
4. reject any mismatch rather than trying to hide it with scenery;
5. only after product-layer approval, create the matching editorial world;
6. run DUFYND mobile/desktop safe-area QA;
7. add provenance to the visual-rights registry;
8. only then switch the website primary asset.

No paid generation is implied or authorised by this document.
