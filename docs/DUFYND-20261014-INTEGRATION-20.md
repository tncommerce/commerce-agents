# DUFYND premium integration candidate

PR #774 at `a21ebf53a812c32d1817a5ca9a8e5e88d8797f9e` conflicts with the already released #780 brand directory at `8647495e5619d1acfaa1346949d586e3b27c4fab`. This isolated development merge preserves that release while retaining #774's catalog and release safeguards. It does not release either branch.

## Resolution

- Preserve all four released brand UI files from #780 as one coherent unit: index, brand detail, BrandDirectory and CSS module. Keep noindex, SITE_INDEXABLE-follow, exact existing product IDs and text-only product presentation.
- Retain #774's photo/release/public-export prebuild and postbuild gates. Add #780's brand-discovery test to prebuild without dependency or lockfile changes.
- Retain both visual-QA imports and test groups. No social-product, first-money-landing, note-sculpture or brand-discovery test block is dropped.
- Reuse the existing brand-discovery browser contract in the older brand-pages runner with its original four widths (320, 390, 768, 1440). The released text cards use data-brand-product, so the old catalog-card selectors no longer describe the actual UI. Product-count equality against the full public projection is retained; the shared contract also checks all exact product IDs, canonical/noindex, real navigation, page errors, overflow and absence of introduced images/offers.
- Brand identity and brand data modules are identical in both parents. The catalog navigation auto-merge retains the production mobile flex-wrap correction.

## Validation

- Existing targeted brand-discovery behavior test PASS: 29 brands, 37 public products, one blocked identity excluded, both indexing flag values checked.
- Existing brand-identity test PASS: aliases add no products.
- Both imported GROWTH-02 held-intake tests PASS by direct invocation. No staged identities or affiliate evidence promoted.
- Syntax checks for the two changed QA runners and git diff whitespace checks PASS.
- Fresh integrated standard Next.js 16.3.6 Turbopack build PASS, including TypeScript and all 105 generated static pages. The direct build does not claim the entire npm prebuild suite was rerun.
- A Webpack diagnostic build exposed the pre-existing global-only selector in FragranceVisual.module.css:96. This file is unchanged by the merge; standard Turbopack compilation passes. A narrow CSS-purity correction belongs to the downstream BUSINESS-20 delta, not this conflict-resolution commit.

New browser execution and screenshot inspection remain an explicit integration gate. No new 320/390/1440 visual PASS is claimed. The available cloud-browser artifact access was blocked and no shell-browser workaround was used.

## Release boundaries

Target this candidate at the #774 development branch only. #788 and the BUSINESS-20 delta remain later integrations; preserve their updated QA and funnel code when stacking. Existing exact-head CI for either parent is not a success claim for this new merge tree. New ordinary PR CI must pass; no manual rerun requested.

No protected branch, production deployment, product/offer/image release, migration, observer credential, cron, Nightshift runtime, publisher or social content changed. Separate Owner release approval is still required.
