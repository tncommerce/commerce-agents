# DUFYND P0 product visual briefs · 25 September 2026

These briefs prepare the next exact-reference visual pass without authorising a paid generation. They are deliberately stricter than social/editorial prompts because these assets may eventually become primary product depictions.

## Shared fidelity gate

Every candidate must preserve the exact intended retail variant and pass all of these checks before activation:

- complete bottle silhouette, uncropped, with 12–15% safe area;
- cap/atomizer/shoulder geometry;
- label or plaque position, brand and product wording;
- no invented volume marking; if the reference is variant-ambiguous, omit or hide volume text rather than hallucinating it;
- material, glass transparency/opacity and liquid colour;
- no extra bottles, no warped typography, no duplicated hardware;
- neutral enough framing to work in card, detail hero and interactive depth layouts;
- separate editorial atmosphere from the bottle source of truth.

A visually attractive result that misses bottle truth remains editorial-only.

## Creed Absolu Aventus · 100 ml

**Current problem:** the DUFYND editorial scene visibly reads 75 ml / 2.5 fl oz while the catalog entry is 100 ml. Creed's current product page itself uses generic imagery across several selectable sizes, so visible volume text is an unreliable generation target.

**Reference for fidelity only:** https://www.creedfragrance.de/p/absolu-aventus/16281794/?variation=16281796

**Primary direction:** jet-black Absolu Aventus bottle, exact Creed crest/embossing and front plaque, controlled black-on-black luxury material study with a pale ivory/champagne architectural background. Full bottle centred with generous safe area.

**Hard constraints:** no visible 75 ml marking; no guessed 100 ml marking unless the exact reference clearly supports it; no bottle redesign, no smoke obscuring the lower bottle, no duplicated cap/plaque.

**Candidate status (25 Sep 2026):** a new volume-neutral black primary candidate was generated and stored at `/products/candidates/creed-absolu-aventus-p0-v1.webp`. It deliberately omits a visible 75 ml/100 ml marking and remains inactive because Creed's current 100 ml page still uses variant-ambiguous imagery.

**Editorial companion:** brighter gallery-world image inspired by DUFYND's mineral/noir atmosphere, with citrus/ginger accents kept clearly secondary to the product.

## Creed Aventus · 100 ml

**Current constraint:** Creed is actively transitioning Aventus packaging. The official German product page states that delivered packaging may differ from the imagery during this transition, while 100 ml remains one of the selectable sizes.

**Reference for fidelity only:** https://www.creedfragrance.de/p/aventus/12870029/

**Primary direction:** do not generate a new DUFYND primary until the exact 100 ml packaging/bottle variant to represent has been explicitly locked. Once locked, preserve the selected bottle/box generation consistently across all surfaces.

**Hard constraints:** do not mix old and new packaging cues; do not infer a box or label version from generic Aventus imagery; do not present a transition-period approximation as verified product truth.

**Editorial companion:** current editorial atmosphere may remain editorial-only as long as it is not used to claim exact packaging fidelity.

## Prada L'Homme Eau de Toilette · 100 ml

**Current problem:** the existing scene reads too bright/silver/clear and is not reliable enough against Prada's official architectural bottle presentation.

**Reference for fidelity only:** https://www.prada-beauty.com/fragrance/lhomme-prada/lhomme-prada-eau-de-toilette/8435137749607.html

**Primary direction:** exact 100 ml L'Homme bottle reference, architectural rectangular proportions, black Saffiano treatment, raised silver Prada branding, restrained silver/black studio environment, precise edge lighting.

**Hard constraints:** do not round or soften the bottle into a generic silver flask; do not replace the Saffiano treatment with plain mirror metal; preserve logo placement and cap geometry.

**Candidate status (25 Sep 2026):** a new neutral primary candidate was generated and stored at `/products/candidates/prada-lhomme-p0-v5.webp`. It is a major fidelity improvement over the live editorial but remains inactive pending direct exact-reference side-by-side QA.

**Editorial companion:** silk/mineral world with brushed metal, dark leather texture and clean gallery light. Avoid generic sunset/citrus scenery.

## Giorgio Armani Stronger With You Intensely · 100 ml

**Current problem:** the current generated cap/shoulder treatment is not faithful enough to the characteristic official presentation.

**Reference for fidelity only:** https://www.armanibeauty.de/dufte/herrenduft/stronger-with-you/stronger-with-you-intensely-eau-de-parfum/3614272225718.html

**Primary direction:** exact 100 ml shoulder-shaped bottle, cognac/amber liquid, characteristic cast-iron-grey metal cap, warm amber studio set. Keep the bottle complete and dominant.

**Hard constraints:** no glossy black spherical stopper, no generic whisky decanter, no ornamental redesign of the shoulders or cap.

**Candidate status (25 Sep 2026):** a new neutral primary candidate was generated and stored at `/products/candidates/armani-swy-intensely-p0-v3.webp`. V3 now corrects the overly broad V2 body and reduces the cap/ring dominance while preserving the cognac liquid and gunmetal direction. It remains inactive pending final human side-by-side approval.

**Editorial companion:** amber/gourmand world using restrained chestnut, vanilla and spice cues. Avoid floating ingredient explosions around the bottle.

## Sospiro Vibrato · 100 ml

**Reference status:** exact-reference checkpoint completed against Sospiro International's current product page. The official page confirms Vibrato as 100ML Eau de Parfum and shows the distinctive deep-green velvet-style bottle, oval gold plaque and sculpted gold cap.

**Reference for fidelity only:** https://sospirointernational.com/products/vibrato

**Primary direction:** exact current 100 ml bottle only, with the complete rounded silhouette, deep-green velvet-style surface, oval gold front plaque and sculpted gold crown-style cap. Keep 12–15% safe area around the full bottle.

**Hard constraints:** no generic cylindrical or rectangular redesign; no black/silver substitute cap; no missing or reshaped oval plaque; no blue colour shift; no invented visible volume marking; no promotion to verified until side-by-side fidelity QA passes.

**Candidate status (25 Sep 2026):** a new neutral primary candidate was generated and stored at `/products/candidates/sospiro-vibrato-p0-v2.webp`. V2 narrows the silhouette, reduces the cap and medallion dominance, and aligns the plaque wording more closely with the current official presentation. It remains inactive pending final human side-by-side approval.

**Editorial companion:** bottle-free green/gold atmosphere using citrus, magnolia/rose, pale woods and refined amber cues. The current 4:3 DUFYND scene remains editorial-only.

## Xerjoff Naxos · 100 ml

**Current status:** DUFYND already has a separately verified transparent product cutout. That cutout remains the product-truth layer.

**Reference for fidelity only:** https://www.xerjoff.com/en-dk/products/naxos-eau-de-parfum

**Primary direction:** do **not** generate another bottle merely to fill the primary slot. Improve the verified cutout only through rights-safe source quality/upscaling if necessary.

**Editorial companion:** completed on PR #67. The approved bottle-free backdrop uses warm Mediterranean stone/light with tobacco, honey, citrus and lavender cues and contains no perfume bottle, packaging, branding or label-like product silhouette. It is stored separately from the verified cutout and remains editorial-only.

**3D direction:** true GLB activation waits until model proportions, cap, plaque, crown/top and surface materials pass side-by-side fidelity review. The current image-depth stage is not a true 3D mesh.

## Output requirements for the next approved generation batch

For each new primary candidate:

1. portrait or square master at high resolution;
2. full bottle fully inside frame;
3. no text outside the real bottle/packaging;
4. one clean reference-faithful primary;
5. optional separate editorial scene;
6. visual QA at 320, 390, 768 and 1440 CSS-pixel presentations;
7. provenance entry and explicit pass/fail decision before catalog activation.

The URLs above are fidelity references, not a declaration that their image files are licensed for republication. No paid generation should be launched from this document without explicit approval.
