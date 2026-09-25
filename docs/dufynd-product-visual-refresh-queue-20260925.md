# DUFYND product visual refresh queue · 25 September 2026

This queue is based on the 32-source contact sheet, the safe-area simulation and a second edge-scan of the actual repository images. It separates **layout safety** from **product fidelity**: the new `FragranceVisual` treatment prevents CSS cropping, but it cannot repair a source image whose bottle/variant is wrong or whose aspect ratio is a poor fit for a given card.

## Findings

- All 32 catalog editorial sources are technically renderable.
- The current safe-area treatment now preserves complete source images; the original CSS cropping issue is therefore addressed at layout level.
- A follow-up pixel-edge audit found **no embedded white source borders** in any of the 32 editorial assets. The white bands visible in the portrait contact-sheet simulation were created by fitting 4:3 landscape artwork into a taller safe-area frame. The problem is therefore aspect-ratio mismatch, not corrupt source canvas.
- The catalog is visually cohesive but overuses the same Mediterranean/sunset/tabletop language. The repetition makes the generated library feel templated rather than like individual fragrance worlds.
- Naxos has a verified transparent product layer plus a dedicated bottle-free editorial backdrop. The verified cutout remains the only product-truth layer.
- Generated bottles must not be promoted to exact primary depictions unless variant, silhouette, cap, plaque/label, typography and visible size markings pass a reference check.

## P0 · rebuild before treating the artwork as an exact primary product image

| Product | Current issue | Next asset |
| --- | --- | --- |
| Creed Absolu Aventus 100 ml | The current DUFYND scene reads **75 ML / 2.5 FL.OZ.** while the catalog entry is 100 ml. Creed's current product page also uses a generic bottle image marked 75 ml while offering 50/100/490 ml selections, so the visual reference itself is variant-ambiguous. | Keep the current scene editorial-only; a future primary should use a 100 ml-faithful or volume-neutral exact-reference bottle depiction. |
| Prada L'Homme EDT 100 ml | Current live editorial remains unsuitable as product truth. A new neutral P0 candidate now captures the architectural bottle, black Saffiano treatment, mirrored silver face and silver cap substantially better. | Candidate stored at `/products/candidates/prada-lhomme-p0-v5.webp`; keep it inactive until direct exact-reference side-by-side QA passes. |
| Giorgio Armani Stronger With You Intensely 100 ml | Current live editorial remains unsuitable as product truth. A new neutral candidate now uses cognac-toned liquid, shoulder-shaped glass and a cast-iron-grey/gunmetal cap treatment much closer to Armani's current bottle description. | Candidate stored at `/products/candidates/armani-swy-intensely-p0-v2.webp`; keep it inactive until exact-reference side-by-side QA passes. |
| Sospiro Vibrato 100 ml | The exact 100 ml reference is locked and the current live 4:3 scene remains editorial-only. A new neutral candidate now follows the deep-green velvet bottle, oval gold plaque and sculpted gold cap direction. | Candidate stored at `/products/candidates/sospiro-vibrato-p0-v1.webp`; keep it inactive until direct exact-reference side-by-side QA passes. |

### Xerjoff Naxos 100 ml · P0 backdrop issue resolved

The inaccurate bottle-containing editorial has been removed from Naxos' structured visual set. DUFYND now uses the verified transparent cutout as product truth and a separate bottle-free Mediterranean/tobacco/honey editorial backdrop at `/products/naxos-bottle-free-backdrop.webp`. The legacy editorial file may remain in repository history, but current structured DUFYND surfaces must not render it.

### Sospiro Vibrato 100 ml · exact-reference checkpoint completed

The current official Sospiro product page confirms **Vibrato 100 ml Eau de Parfum** and provides a stable fidelity reference for the next primary-image attempt. The recognizable product cues are the deep-green velvet-style rounded bottle, gold oval front plaque and sculpted gold cap. This reference lock does **not** make the current DUFYND editorial image a verified product depiction; it remains editorial-only until a direct side-by-side bottle-fidelity review passes.

The source note data was also normalized to the current official presentation: top-note ordering now follows grapefruit → bergamot → mandarin → ginger → rosemary, and the base uses the more specific **Indian Sandalwood** rather than generic sandalwood. DUFYND keeps normalized internal terms such as `Damask Rose` / `Light Woods` where they map cleanly to the official wording.

Reference for fidelity/data verification only: https://sospirointernational.com/products/vibrato

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
- Valentino Uomo Born In Roma Intense

Do **not** trim these sources: the edge audit confirmed there is no embedded white canvas to remove. The proper fix is a dedicated portrait/square primary asset or verified transparent product layer, while the 4:3 image remains available for editorial/hero use.


## P2 · keep as editorial, then verify product fidelity product-by-product

The remaining generated visuals are attractive enough to keep in the current gallery/atmosphere layer, but are still stylized DUFYND artwork until an exact product-reference review passes:

- Afnan Supremacy Collector's Edition
- Afnan Turathi Blue
- Creed Aventus
- Louis Vuitton Imagination
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
