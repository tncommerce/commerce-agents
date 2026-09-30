# DUFYND catalog readiness — 2026-09-30

Verified against `scentai-mvp` after PR #399 and the public storefront. This supersedes the 2026-09-29 snapshot for current planning. Counts describe existing data; they do not grant image rights or change release readiness.

| Measure | Current result |
| --- | ---: |
| Customer-visible fragrances | 34 |
| In-stock fragrance rows in the repository catalog | 35 |
| Visible Herren / Unisex / Damen | 17 / 16 / 1 |
| Staged records | 50 |
| Staged records already live | 2 |
| Remaining expansion candidates | 48 |
| Staged records with integrated merchant offers | 23 |
| Staged records with a fresh affiliate offer | 1 |
| Staged records with approved images | 2 |
| New candidates passing promotion dry-run | 0 |

`SC-WIDIAN-LONDON-EXTRAIT-50` remains in the catalog data but is hidden by its source validation blocker. It must not inflate homepage or storefront counts. The raw audience tags remain available for research; the storefront assigns each fragrance to exactly one audience, with Unisex taking priority.

Lancôme La Vie est Belle and Rabanne 1 Million are already live. Both also remain in staging, so the promotion report returns `already_live` for them. Its `blocked_count=50` includes those two records; it does not mean there are 50 unpublished candidates. The single fresh affiliate staging record is Rabanne 1 Million, rather than an additional ready expansion product.

The promotion dry-run reports 48 missing approved images, 27 missing current purchase destinations and 3 provisional community-data blockers. These sets overlap. Merchant research coverage alone does not establish an integrated or currently eligible purchase offer.

## Requested products requiring the next evidence

| Product / exact staging variant | Eligible purchase offers | Remaining promotion blockers |
| --- | ---: | --- |
| YSL Libre EDP 90 ml (`SC-YSL-LIBRE-EDP-90`) | 1 | Approved product image |
| Mon Guerlain EDP 100 ml (`SC-GUERLAIN-MON-GUERLAIN-EDP-100`) | 1 | Approved product image |
| JPG Le Male Elixir Parfum 125 ml (`SC-JPG-LE-MALE-ELIXIR-PARFUM-125`) | 1 | Approved product image |
| Tom Ford Oud Wood EDP 100 ml (`SC-TOM-FORD-OUD-WOOD-EDP-100`) | 0 | Approved image and current purchase destination |
| Dior Sauvage Elixir 100 ml (`SC-DIOR-SAUVAGE-ELIXIR-100`) | 0 | Approved image and current purchase destination |

Sauvage Elixir is distinct from the separately requested Sauvage EDP. Evidence and assets for one variant must not be reused to mark the other variant ready. The five existing true-3D rights-holder requests remain an independent external dependency; an automatic acknowledgement is not an asset or license grant.

## Live technical audit

- All 34 catalog product image URLs returned HTTP 200 with image content.
- All 34 customer-visible fragrance detail pages returned HTTP 200 with an H1.
- Live catalog filters returned 17 Herren, 16 Unisex and 1 Damen fragrance.
- Rabanne 1 Million showed Müller and Perfumetrader offers with separate partner labels and price priority.
- PR #399 visual QA completed 93 checks across 320, 390, 768 and 1440 px, with no horizontal overflow or visible broken images.
- Frontend and API Render deployments were live on commit `6e7358d576e3d5bf1c54840885fe82a93e268ccd`; post-merge CI and Production Smoke passed.

## Reproduce from the repository root

```sh
python -m scripts.report_scentai_merchant_coverage
python -m scripts.report_scentai_promotion_readiness
python -m scripts.plan_scentai_promotion_batch --limit 10
```

`storefront_fragrance_count`, `storefront_audience_counts` and `storefront_blocked_product_ids` describe customer-visible inventory. The original `live_fragrance_count` and `live_audience_counts` fields retain their raw repository meaning for compatibility.

## Expansion and promotion priority

The expansion-readiness report and promotion-batch planner use the visible,
exclusive storefront audiences for their gap scores. Their `--source` input
defaults to `scentai_products.json`, so the hidden Widian identity blocker is
excluded from the baseline. Source classification takes precedence over legacy
catalog tags; Unisex, including a combined Herren/Damen classification, counts
once. Unknown audiences receive no gap bonus.

Raw `live_audience_counts` remain available for research compatibility. The
`storefront_audience_counts`, `storefront_fragrance_count` and
`storefront_blocked_product_ids` fields explain the planning baseline. With the
current 17 Herren, 16 Unisex and 1 Damen entries, a women's candidate has a
9.41/10 audience-gap score, while a Unisex candidate has 0.59/10 even when its
raw tags also contain men and women. These scores do not clear image, merchant,
source or promotion blockers, and the plans do not publish catalog changes.
