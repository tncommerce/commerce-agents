# Social → product → merchant: targeted conversion changes

Development only, PR #774. No release, offer activation, merchant requests or new tracking stack.

## Entry evidence

- Instagram website field read through Windsor on 2026-10-12 still points directly to `/duft/rabanne-1-million?src=instagram&cmp=fms_1m_bottle_first_20261005&content=one_million_bottle_first_20261005_01`.
- YouTube's header/About link was verified in `ops.social_to_shop_activation_20261010`: same product route, `src=youtube`, `cmp=yt_1million_v8DlVXi-Fj8_p1`, `content=one_million_example61_01`. This is inherited evidence dated October 10, not a new account capability claim.
- TikTok's website field was confirmed unavailable by the owner in that checkpoint. Tagged events do not prove a clickable profile link. No account or post changes.
- `/start` already has exact variant links and search; Instagram and YouTube do not require this intermediate step. Existing navigation and attribution tests are retained.

## Reproducible friction and changes

Baseline: commit `4d66653421a74384572315d782cbb4b05b1fda93`, successful CI `38226342285`, artifact `11737185328` (`dufynd-visual-qa-774`). The real browser images `rabanne-1-million-390.png` and `rabanne-1-million-1440.png` show a large blank image stage. On mobile the offer chapter starts below the first screen; on desktop the blank stage occupies half the hero.

1. For a product with no rights-approved public photo, the shared detail component now renders the existing rights notice in a compact stage. It preserves exact identity, concentration, size, notes and the internal offers CTA. Public licensed photos and private merchant photo reviews retain their image stages.
2. Offer totals now explicitly say **Gesamtpreis inkl. Versand** when `total_price` is known. Previously a bare total next to a shipping amount could be read as requiring shipping on top. Unknown totals still say shipping may be additional.
3. A single offer no longer receives a comparative best-price badge. For multiple offers the existing ranking badge explicitly applies to the listed selection. No prices, sorting, affiliate destinations or availability gates are changed.

## Isolated verification and owner review

`social-product-entry-qa.mjs` extends the existing visual QA runner, not the production funnel. Instagram short keys and YouTube UTM aliases are tested at 390 and 1440 px. It checks variant identity, compact-stage geometry, initial CTA/offer visibility, overflow, campaign-bearing catalog and clickout hrefs, affiliate disclosure, session identity, internal anchor navigation and QA-classified analytics.

All APIs are intercepted locally; external requests and all clickouts are blocked. The artificial offer is 90 EUR + 5 EUR shipping, clearly separate from the historic real Perfumetrader observation of 71.90 EUR + 4.99 EUR. Additional states cover unknown shipping and multiple offers. No merchant anchor is clicked.

The CI artifact contains:

- `rabanne-1-million-{390,1440}.png`: after images comparable to the baseline's API-unavailable fallback state.
- `social-product-fixture-{390,1440}.png` and `-viewport.png`: actual browser renderings with the synthetic successful-offer fixture; these are not live merchant quotes.
- `report.json`: dimensions, attribution results and existing regression checks, including private photo review coverage elsewhere in the artifact.

Owner decision: assess the compact layout and price clarity using the before/after images. A successful CI does not certify 9.5/10 design quality or authorize publication. No new original photo is approved by this change. The five top-Parfümerie images remain private and merchant-bound; Althaïr remains held. Public release still needs separate owner approval. Independent network revenue remains unknown until an authorized original report is supplied.
