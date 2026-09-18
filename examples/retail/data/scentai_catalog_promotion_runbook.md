# SCENTAI Catalog Promotion Runbook

Status: active
Updated: 2026-09-18

## Decision

Do not start Batch 4 yet.

SCENTAI already has 30 verified candidates across Batches 1-3. The bottleneck is no longer discovery; it is controlled promotion into the live catalog. New research work pauses until the promotion pipeline is operational.

## Current gates

- 30/30 identity verified
- 30/30 community QA completed
- 30/30 have verified merchant coverage
- 20/30 have multi-merchant coverage
- 0/30 have approved affiliate links
- 0/30 have approved feed/manufacturer images prepared for live use
- 0 unresolved identity/version blockers
- 2 provisional community-performance cases that must not receive strong performance claims yet

## Promotion order

### Tier A — first live promotion pool
Candidates with:
- verified identity
- completed community QA
- at least two verified merchants
- no unresolved identity/version blocker
- stable enough community data

Once affiliate approval + approved images are available, promote these first.

### Tier B — second live promotion pool
Candidates with:
- verified identity
- completed community QA
- only one verified merchant

Promote after Tier A or once a second approved merchant/feed appears.

### Tier C — hold/recheck
Very new or reformulated products where performance/community evidence is still immature.

Current examples:
- Jean Paul Gaultier Fleur du Mâle (2026)
- Dolce & Gabbana The One for Men Eau de Parfum (2025)

These may still become live products, but SCENTAI must avoid overstating Haltbarkeit/Ausstrahlung until the evidence matures.

## Affiliate approval workflow

When an approval arrives:
1. Update `scentai_affiliate_programs.json` from applied -> approved.
2. Record network/program ID and permitted feed/link method.
3. Import feed or tracked links into the merchant-offer layer.
4. Match merchant products to canonical SCENTAI products; never create duplicate canonical fragrances per merchant.
5. Store current merchant price/availability with timestamps.
6. Never use commission in recommendation or merchant ranking.

## Image workflow

Preferred order:
1. Approved affiliate product-feed image
2. Manufacturer image with an appropriate permitted usage route
3. Other explicitly licensed source

Do not use AI-generated bottle lookalikes as live commerce product images.

## Live promotion workflow

Promote only 5-10 products at a time.

For each mini-release:
1. Create live catalog records.
2. Attach current merchant offers.
3. Confirm mobile cards/detail views.
4. Test exact-name search.
5. Test typo search.
6. Test gender/unisex/feminine-leaning request handling.
7. Test price/budget behavior.
8. Test merchant clickout.
9. Check analytics events.
10. Only then promote the next mini-release.

## Catalog expansion resumes when

Resume Batch 4 after at least one of these is true:
- first 10 verified candidates are live with approved images/offers, or
- affiliate/feed delays persist long enough that a separate content-only catalog strategy is explicitly approved.

At that point, new candidate selection should use real SCENTAI no-result searches, product opens and clickouts in addition to retailer/community demand.


## Promotion command

Dry-run one product before any live change:

```powershell
python scripts/promote_scentai_catalog.py --product-id SC-EXAMPLE-100
```

Dry-run up to 10 products from a verified batch:

```powershell
python scripts/promote_scentai_catalog.py --batch 1 --limit 10
```

A live write is only allowed after every selected product passes every gate:

```powershell
python scripts/promote_scentai_catalog.py --product-id SC-EXAMPLE-100 --write
```

The command refuses partial writes. If even one selected product is blocked, nothing is promoted.

Default hard gates enforced by the tool:
- approved product image
- complete deterministic recommendation profile
- current in-stock affiliate offer with tracking URL
- non-provisional community data
- product not already live

The recommendation profile is an internal deterministic retrieval feature derived from verified community accords. It is not a customer-facing fragrance rating and must not be described as objective measurement.


## Staging recommendation QA

Run the isolated pre-live QA at any time while affiliate approvals are pending:

```powershell
python scripts/qa_scentai_staging.py
```

The QA currently checks:
- structural completeness for all staged products
- exact-name lookup for every staged fragrance
- typo handling across a representative set of names/brands
- men/women/unisex audience scoring
- non-provisional community performance completeness

Budget and merchant-offer QA remains intentionally deferred until real current affiliate offers exist.

Live promotion now automatically reruns this staging QA before writing to `catalog.json`. A failing recommendation QA blocks the live write.

## Promotion readiness report

Before doing new catalog research, inspect the current staging bottlenecks:

```powershell
python scripts/report_scentai_promotion_readiness.py
```

The report calculates readiness live from:
- staged SCENTAI products
- current live catalog
- current merchant offers
- approved image status
- recommendation-profile and audience gates
- provisional community-data status

It also groups candidates into:
- Tier A: stable candidate with at least two verified merchants
- Tier B: stable candidate with one verified merchant
- Tier C: provisional or weak merchant coverage

For machine-readable automation:

```powershell
python scripts/report_scentai_promotion_readiness.py --machine-readable
```

To save a point-in-time JSON snapshot:

```powershell
python scripts/report_scentai_promotion_readiness.py --output examples/retail/data/scentai_promotion_readiness.json
```

This report is advisory. The actual live write still goes through
`promote_scentai_catalog.py` and all of its hard gates.

## Affiliate feed image intake

When an approved CJ/Awin merchant feed becomes available, keep offer import
and product-image review separate.

First configure the real feed columns in
`scentai_affiliate_provider_config.example.json` or a copy of it, including
`image_url` when the approved feed exposes a usable product image.

Extract review-only image candidates:

```powershell
python -m retail.api.extract_merchant_feed_assets --feed PATH_TO_FEED.csv --provider-config PATH_TO_PROVIDER_CONFIG.json
```

The command writes
`examples/retail/data/merchant_feed_image_candidates.json`.

Important:
- extracted images are not promoted automatically
- unmatched products remain visible for mapping review
- invalid/non-HTTP image URLs are rejected
- duplicate product/image pairs are collapsed
- only a reviewed candidate may later receive the
  `approved_feed_image` status used by the live-promotion gate

Offer import remains a separate dry-run/write workflow through
`import_merchant_feed.py`.

