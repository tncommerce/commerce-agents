# DUFYND storefront visual standard — 29 September 2026

## Goal

DUFYND fragrance imagery must read as one premium brand system even when the underlying product-truth asset comes from a different production workflow. Product correctness and storefront art direction are separate concerns and must never overwrite each other.

## Two visual layers

### Product truth

Used for structured product data, fidelity-sensitive product views, exact-variant checks, comparison truth and future 3D/model verification.

Requirements:

- exact fragrance, concentration and size;
- verified silhouette, cap, plaque/label and visible typography;
- no invented bottle geometry;
- no fake 3D transformation;
- provenance retained;
- a newly verified studio image does **not** automatically become the preferred discovery artwork.

### Storefront presentation

Used for homepage selections, catalog/discovery cards and related-product discovery.

Selection order:

1. verified product truth + approved bottle-free editorial backdrop;
2. existing DUFYND editorial `product_scene`;
3. verified product-truth stage when no editorial presentation exists;
4. other editorial fallback;
5. neutral missing-image state.

This keeps the website visually coherent while product truth remains independently auditable.

## DUFYND house language

Target direction: **luxury fragrance editorial × Apple product staging × immersive depth**.

Across products, keep these constants:

- the bottle remains the dominant subject;
- optical centering and generous safe area;
- premium material detail and controlled specular light;
- dark/deep presentation stage for product-layer compositions;
- restrained mist, reflections, particles and accord-driven light;
- consistent card framing and mobile containment;
- no gaming HUD, sci-fi interface or fake product transformation.

Per-fragrance variation belongs in the **world behind the bottle**: amber, mineral, noir, silk or ember, driven by the actual fragrance profile. Variety is intentional; layout and rendering grammar remain consistent.

## Transition rule for existing AI scenes

Existing DUFYND AI product scenes may remain on discovery/card surfaces while the verified product layer is stored separately. They should not be deleted merely because a white/studio fidelity asset is approved.

The long-term upgrade path is:

**verified bottle layer + bottle-free DUFYND editorial world**

This avoids regenerating bottle geometry in every background scene and lets the same verified product layer serve catalog, hero, comparison and future 3D-adjacent experiences.

## Surface policy

| Surface | Visual source |
| --- | --- |
| Homepage spotlight | verified layer + bottle-free backdrop when available; otherwise DUFYND presentation |
| Homepage product cards | storefront presentation |
| /duft discovery hero | storefront presentation |
| /duft catalog cards | storefront presentation |
| Related-product cards | storefront presentation |
| Product-detail primary hero | product truth first |
| Product JSON-LD / metadata | verified product truth only |
| Fidelity QA | verified product truth only |
| Editorial gallery | editorial assets, clearly separated from product truth |

## Machine-readable monitoring

`scripts/report_dufynd_visual_coverage.py` reports product-truth coverage and storefront-presentation coverage separately. The presentation backlog is a report, **not a second approval queue**.

No generation spend is authorized by this standard. New paid generations still require the existing financial approval boundary.
