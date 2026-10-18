# DUFYND — original photographic editorial A/B (RESET38)

**Status:** VISUAL REJECT / ROLLED BACK / historical source evidence only.
Not an approved current merchant photograph, product image or Hero.

## Independent RESET38 decision — 17 October 2026

**VISUAL REJECT after examining the original screenshots.** The original
[CI #39066798822](https://github.com/tncommerce/commerce-agents/actions/runs/39066798822)
passed all seven active jobs, including responsive QA. Its
[source-matched artifact #12113737031](https://github.com/tncommerce/commerce-agents/actions/runs/39066798822/artifacts/12113737031)
contains genuine `licensed-original-{320,390,1440}-hero-study.png` and
`visual-reset-{320,390,1440}-first.png` screenshot comparisons.

The licensed photograph has authentic photographed gold/reflections and
immediate perfume recognition. Nevertheless, on desktop it remains a
rectangular historical product photo inside an unrelated modern art direction.
On iPhone 390/320 it becomes a small framed photograph with 2011/product
captions and author/license disclosures squeezed into tiny text. This is
not an independently defensible premium 9.5/10 Hero. Its 2011 package
does not prove the actual current Awin/Perfumetrader variant.

The experiment is **removed, not polished**: restore pre-RESET38 app Hero,
CSS and normal visual QA exactly, delete the local-only photo module, keep
this licensed-source research as historical evidence, and leave the default
visitor experience, consent, purchase/affiliate integration, analytics and
RESET37 social preview unchanged. No production deployment occurred.

**Exactly one P0 dependency for the next visual promotion:** first obtain
a truly premium, rights-cleared, accurately contextualised **original**
editorial perfume still, and independently accept that still at 320, 390
and 1440 px **before writing another Hero implementation**. Do not use
an unverified current-product claim or another generic framed shot. If no
original still qualifies within 0 EUR, hold visual release rather than
churning through shader/crop variants.

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

## Rejected local visual direction (historical only)

The removed, strictly local opt-in `?dufynd_commons_study=1` rendered a
dark umber/copper editorial cover. The genuine photograph was not modified or cropped, nor regenerated with
invented label glyphs. The original functional homepage Hero remains the default,
including all original WebGL/interaction, finder, search and RC1 link.
The experiment visibly linked the source, author and CC BY-SA license and
used the published internal `/duft/rabanne-1-million#angebote` link via the
existing attribution-preserving component. No merchant clickout, invented
price or stock assertion was added.

**QA completed:** original QA captured at 320, 390 and 1440 px. The actual
image decoded; heading, label, credit/license, first-fold search, no overflow
and zero blocked merchant/analytics mutations were asserted. The variant
passed technical CI, but failed the independent visual acceptance.

**Release gate:** not eligible for release. A new source would need independently
verified rights, depictive identity and >9.5/10 original desktop/mobile stills
before any new app integration. Any later merge/deploy requires separate Owner
GO. No new paid assets, generation or Supabase mutations.
