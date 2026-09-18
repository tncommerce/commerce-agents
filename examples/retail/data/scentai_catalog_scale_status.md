# SCENTAI Catalog Scale & Merchant Coverage Status

Status: active
Updated: 2026-09-18

## Current catalog

Live fragrances: **32**

Audited live target assignments:
- men: 32
- unisex: 16
- women: 2

A fragrance can have more than one target assignment, so these counts are not
intended to sum to 32.

The live catalog is therefore still strongly male-skewed.

## Verified staging pool

Staged fragrances: **30**

Batches:
- Batch 1: 10
- Batch 2: 10
- Batch 3: 10

Staged target assignments:
- women: 14
- men: 12
- unisex: 7

Researched merchant coverage:
- 30/30 have at least one verified merchant
- 20/30 have at least two verified merchants
- 2/30 have three researched merchants

Community status:
- 28/30 have non-provisional community/performance data
- 2/30 remain provisional:
  - Jean Paul Gaultier Fleur du Mâle (2026)
  - Dolce & Gabbana The One for Men Eau de Parfum (2025)

## Integration reality

Research coverage and production integration are intentionally separate.

Current staged integration:
- staged products with actual imported merchant offers: **0/30**
- staged products with current affiliate offers: **0/30**
- staged products with approved images: **0/30**
- staged products with resolved merchant-product mappings: **0/30**

The existing merchant-offer layer currently contains offers for the already
live Essential Parfums Bois Impérial product. Those offers do not make any of
the 30 staging products promotion-ready.

The single existing Notino mapping record for Bois Impérial still has no
verified SKU/EAN/GTIN and is unrelated to the 30 staging candidates.

## Current blockers

For the stable 28 candidates:
- approved product image missing
- current tracked affiliate offer missing

For the two provisional candidates:
- approved product image missing
- current tracked affiliate offer missing
- community/performance evidence still provisional

No product should be promoted by filling any of these fields with guessed data.

## Next 10-product worklist

The current planner prioritizes underrepresented live audiences while still
respecting promotion blockers, researched merchant coverage and community
sample size.

Current worklist:

1. Parfums de Marly Delina Eau de Parfum 75 ml
2. Dior Hypnotic Poison Eau de Toilette 100 ml
3. Yves Saint Laurent Black Opium Eau de Parfum 90 ml
4. Yves Saint Laurent Libre Eau de Parfum 90 ml
5. Guerlain Mon Guerlain Eau de Parfum 100 ml
6. Chloé Chloé Eau de Parfum 100 ml
7. Burberry Goddess Eau de Parfum 100 ml
8. Prada Paradoxe Eau de Parfum 90 ml
9. Lattafa Eclaire Eau de Parfum 100 ml
10. Parfums de Marly Valaya Exclusif Eau de Parfum 75 ml

All ten are currently blocked by the same two production requirements:
- approved image
- current tracked affiliate offer

This is a **work priority**, not a quality ranking of fragrances.

## Why the first worklist is women-heavy

The ordering is deliberate and data-driven.

The live catalog currently has only 2 women's target assignments compared with
32 men's assignments. The planner therefore gives the largest portfolio-gap
score to staged products that add women's coverage.

This portfolio-gap signal never bypasses:
- identity verification
- community QA
- image approval
- merchant mapping
- affiliate offer freshness
- promotion QA

## Merchant-feed workflow

When the approved affiliate feed becomes available:

1. Run feed preflight.
2. Review structural field coverage.
3. Review SCENTAI mapping coverage separately.
4. Resolve exact merchant SKU/EAN/GTIN mappings for selected canonical products.
5. Dry-run merchant-offer import.
6. Extract feed image candidates.
7. Visually approve exact product/image pairs.
8. Re-run merchant coverage and promotion readiness.
9. Promote only a 5-10 product mini-release after every hard gate passes.
10. Smoke-test the release before processing the next batch.

Broad merchant feeds can contain unrelated products. Low whole-feed SCENTAI
mapping coverage is therefore not itself a feed failure.

## Commands

Merchant integration reality:

```powershell
python scripts/report_scentai_merchant_coverage.py
```

Next work batch:

```powershell
python scripts/plan_scentai_promotion_batch.py --limit 10
```

Promotion readiness:

```powershell
python scripts/report_scentai_promotion_readiness.py
```

Actual promotion remains a separate guarded operation:

```powershell
python scripts/promote_scentai_catalog.py --product-id SC-EXAMPLE-100
```

No write should be attempted until the dry-run reports every selected product
as ready.
