# DUFYND — original photographic editorial A/B (RESET38)

**Status:** LOCAL QA-ONLY / NOT_FINAL_YET / not an official current merchant
product photograph / no design approval. One deliberate alternative only.

## Grounded source and licensing

Photograph: **Beemwej**, *1 Million PL.JPG* (photographed 19 Dec 2011,
uploaded 2 May 2012), unmodified image 1424×2144. Author specifically labels
the depicted Paco Rabanne 1 Million bottle as **100ml**, and the bottle shows
a 100 ml volume marking. Original:
https://commons.wikimedia.org/wiki/File:1_Million_PL.JPG

The author licenses it under **Creative Commons Attribution-ShareAlike 3.0
Unported**, which permits commercial use subject to full attribution, a license
link, indication of any adaptations and ShareAlike for derivatives:
https://creativecommons.org/licenses/by-sa/3.0/

**Not independently verified:** GTIN **3349666007921**, contemporary package
revision, current Perfumetrader article **16978322**, current inventory/price,
endorsement by the photographer or Rabanne. It is a historical **editorial
photograph**, not the current product-identity source. No product schema,
merchant data or catalog picture is changed based on the caption alone.
Do not claim the photo is an approved Perfumetrader merchant asset.

## Visual direction

A single local-only opt-in `?dufynd_commons_study=1` on localhost renders a
dark umber/copper editorial cover. The real photograph is not modified or
cropped, never regenerated with invented label glyphs, and sits in a coherent
studio stage. The original functional homepage Hero remains the default,
including all original WebGL/interaction, finder, search and RC1 link.
Photo source and named author + CC BY-SA license are visibly linked. The
editorial image links to the published internal `/duft/rabanne-1-million#angebote`
route through the existing attribution-preserving component; no merchant
clickout is generated and no prices or stock are invented.

**Independent acceptance:** original QA captures at widths 320, 390, 1440,
image must actually decode (no fake success on blank/offline image), single
heading, a11y label, license/source links, intact first-fold search, no
horizontal overflow or tracking/consent writes. Assess against prior 3D
still for genuine large creative improvement, not another successful-but-bad
cosmetic patch. If source loading is inaccessible, mark failed; do NOT bypass
the test or activate by default. Do not present as 9.5 based on technical CI.

**Release gate:** verified exact variant/match and independent visual
evaluation at desktop + mobile, plus license/provenance policy review before
considering public use. Separate Owner GO for merge/deploy. No new asset
downloads, generating credits, paid providers or Supabase mutations.
