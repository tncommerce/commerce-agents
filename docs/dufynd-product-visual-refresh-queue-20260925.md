# DUFYND product visual refresh queue · 25 September 2026

This queue is based on the 32-source contact sheet, the safe-area simulation and a second edge-scan of the actual repository images. It separates **layout safety** from **product fidelity**: the new `FragranceVisual` treatment prevents CSS cropping, but it cannot repair a source image whose bottle/variant is wrong or whose aspect ratio is a poor fit for a given card.

## Findings

- All 32 catalog editorial sources are technically renderable.
- The current safe-area treatment now preserves complete source images; the original CSS cropping issue is therefore addressed at layout level.
- A follow-up pixel-edge audit found **no embedded white source borders** in any of the 32 editorial assets. The white bands visible in the portrait contact-sheet simulation were created by fitting 4:3 landscape artwork into a taller safe-area frame. The problem is therefore aspect-ratio mismatch, not corrupt source canvas.
- The catalog is visually cohesive but overuses the same Mediterranean/sunset/tabletop language. The repetition makes the generated library feel templated rather than like individual fragrance worlds.
- Only Naxos currently has a verified transparent product layer. Its generated editorial image should remain atmosphere/background rather than the bottle source of truth.
- Generated bottles must not be promoted to exact primary depictions unless variant, silhouette, cap, plaque/label, typography and visible size markings pass a reference check.

## P0 · rebuild before treating the artwork as an exact primary product image

| Product | Current issue | Next asset |
| --- | --- | --- |
| Creed Absolu Aventus 100 ml | Current generated bottle visibly reads **75 ML / 2.5 FL.OZ.**, while the catalog entry is 100 ml. | New DUFYND primary render from an exact current 100 ml reference; current image may remain editorial only. |
| Prada L'Homme EDT 100 ml | Current silver rounded render does not match Prada's official description of the architectural L'Homme bottle wrapped in black Saffiano with raised silver branding. | Rebuild from an exact 100 ml official/rights-cleared reference. |
| Xerjoff Naxos 100 ml | Generated editorial bottle is not the verified product layer. | Keep the existing verified cutout as primary; use editorial only as atmosphere. |
| Louis Vuitton Imagination 100 ml | Attractive image, but bottle details have not yet passed an exact-reference fidelity check. | Exact-reference DUFYND render or verified cutout before calling it the primary bottle depiction. |
| Creed Aventus 100 ml | Attractive editorial, but current Creed packaging is in transition and the generated label/bottle should not be assumed exact. | Rebuild/verify against the exact current 100 ml variant. |

## P1 · landscape assets that need a dedicated primary format

The following 4:3 editorial scenes are visually valid source files, but they become smaller/letterboxed when a complete uncropped scene is placed inside a taller product stage:

- Al Ambra Dubai Musk
- Arabiyat Prestige Marwa Extrait
- Armaf Club de Nuit Intense Man
- Creed Aventus
- Al Wataniah Kayaan Classic
- Maison Asrar Regent
- Maison Asrar Vanguard
- Montblanc Explorer
- Orientica Royal Bleu
- Parfums de Marly Althaïr
- Sospiro Vibrato
- Valentino Uomo Born In Roma Intense

Do **not** trim these sources: the edge audit confirmed there is no embedded white canvas to remove. The proper fix is a dedicated portrait/square primary asset or verified transparent product layer, while the 4:3 image remains available for editorial/hero use.

## P2 · keep as editorial, then verify product fidelity product-by-product

The remaining generated visuals are attractive enough to keep in the current gallery/atmosphere layer, but are still stylized DUFYND artwork until an exact product-reference review passes:

- Afnan Supremacy Collector's Edition
- Afnan Turathi Blue
- Al Haramain Détour Noir
- Arabiyat Prestige Marwa EDP
- Giorgio Armani Stronger With You Intensely
- Bleu de Chanel EDP
- Essential Parfums Bois Impérial
- Bujairami Hectic
- Bvlgari Le Gemme Tygar
- Clive Christian Jump Up and Kiss Me Hedonistic
- Dior Homme Intense
- Dior Sauvage EDP
- French Avenue Liquid Brun
- Nusuk Ateeq
- Parfums de Marly Layton
- Rayhaan Italia

## New DUFYND asset standard

Each important fragrance should eventually have separate assets for separate jobs instead of forcing one campaign image into every surface:

1. **Primary product layer** — exact bottle, complete silhouette, no crop, 12–15% safe area, neutral/transparent or restrained tonal background.
2. **Editorial hero** — scent-driven DUFYND world, more cinematic and expressive, allowed to use ingredients/lighting/architecture.
3. **Macro/detail** — cap, plaque, glass, embossing or material detail; exact-reference only.
4. **Interactive depth/3D** — verified cutout or GLB; never inferred from an unverified editorial image.
5. **Social asset** — may be more dramatic, but cannot silently become the product-data source of truth.

For the next generation batch, vary the worlds by accord and brand instead of repeating the same sunset/stone/citrus tableau. The website's existing amber/mineral/noir/silk/ember atmosphere system should guide the art direction so the still assets and dynamic 3D treatment feel like one DUFYND visual language.

## Release gate for a generated primary image

A generated image can replace an external/original primary image only after all of the following pass:

- exact fragrance + concentration + intended size/variant;
- bottle silhouette and proportions;
- cap/atomizer geometry;
- plaque/label placement and legible brand/product text;
- visible volume marking does not contradict the catalog;
- material/color/transparency are plausible;
- complete bottle remains inside the safe area on mobile and desktop;
- source/reference rights and generated-asset provenance are recorded.

Until then, display it as **stilisierte DUFYND-Inszenierung**, not as an exact packshot.
