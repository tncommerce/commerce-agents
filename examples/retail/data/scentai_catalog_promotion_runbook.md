# SCENTAI Catalog Promotion Runbook

Status: active
Updated: 2026-09-25

## Decision

Batch 4 may enter isolated pre-live staging in controlled groups, but live promotion remains gated.

DUFYND now has 30 verified candidates across Batches 1-3 plus a controlled five-product Batch 4 staging intake from the researched NEXT-10 wave. This raises isolated staging to 35 products while live remains at 33. The first Batch 4 intake is intentionally capped at five products and does not authorize publication.

## Current gates

- 35 products are now in isolated staging
- 33 fragrances are live
- 68 unique fragrance identities exist across live + staging with zero overlap
- Batch 4 intake is limited to candidates without unresolved source/version blockers
- Batch 4 still requires approved affiliate offers and approved product images before any live promotion
- Existing Batches 1-3 remain subject to the same affiliate/image/live-offer gates
- No staging intake authorizes a live write

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

## Catalog expansion cadence

Research and staging expansion may continue in controlled waves while live promotion stays blocked behind commerce and image gates.

Rules:
- stage at most 5 new products per controlled intake unless the manifest is explicitly changed
- never stage candidates with unresolved direct-source, edition or concentration conflicts
- never treat research merchant evidence as a live affiliate offer
- use real DUFYND no-result searches, product opens and clickouts increasingly as the catalog grows
- live promotion remains limited to 5-10 products at a time after all hard gates pass


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

## Merchant integration coverage report

Use this report to distinguish researched merchant availability from merchant
data that is actually integrated into SCENTAI:

```powershell
python scripts/report_scentai_merchant_coverage.py
```

It reports:
- researched merchant coverage from staging
- actual imported offers
- actual affiliate offers
- resolved merchant-product mappings
- approved image readiness
- current live-vs-staged audience distribution

This distinction matters because "verified merchant coverage" in staging means
the product was found at real merchants during research. It does **not** mean
SCENTAI already has a usable feed mapping, current tracked offer or approved
image for that product.

## Next promotion work batch

Generate the next 1-10 product worklist:

```powershell
python scripts/plan_scentai_promotion_batch.py --limit 10
```

The planner does not promote anything. It orders the existing staged pool by:
1. products already passing all hard promotion gates
2. non-provisional community data
3. fewer unresolved hard blockers
4. underrepresented audiences in the current live catalog
5. researched merchant coverage
6. community sample size

The generated rows include exact canonical concentration and volume so the
result can be used as a merchant-mapping worklist without guessing SKUs,
EANs or GTINs.

Save a point-in-time worklist:

```powershell
python scripts/plan_scentai_promotion_batch.py --limit 10 --output examples/retail/data/scentai_next_promotion_batch.json
```

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
- extracted rows carry only a `proposed_image_status`; they are not approved
  merely because they came from a feed
- only a reviewed candidate may later receive the
  `approved_feed_image` status used by the live-promotion gate

Offer import remains a separate dry-run/write workflow through
`import_merchant_feed.py`.

## Affiliate feed preflight

Before importing any newly approved CJ/Awin feed, run a read-only
technical preflight first:

```powershell
python -m retail.api.preflight_merchant_feed --feed PATH_TO_FEED.csv --provider-config PATH_TO_PROVIDER_CONFIG.json
```

The preflight does not modify SCENTAI data. It checks every adapted feed row
for:
- merchant product identifier: SKU, EAN or GTIN
- valid positive price and three-letter currency
- parseable stock value
- valid product URL
- parseable update timestamp
- affiliate/tracking URL
- product image URL
- canonical merchant/source metadata required by the importer

Statuses:
- `READY` / exit 0: every row is offer-import ready and also has a usable
  affiliate link plus image URL
- `REVIEW` / exit 10: offer data is importable, but one or more rows still
  lack usable promotion assets such as tracking links or product images
- `BLOCKED` / exit 20: one or more rows fail core import requirements such
  as identifier, price, stock, product URL or timestamp

For automation:

```powershell
python -m retail.api.preflight_merchant_feed --feed PATH_TO_FEED.csv --provider-config PATH_TO_PROVIDER_CONFIG.json --machine-readable
```

The preflight also reports **SCENTAI mapping coverage** against
`merchant_product_mappings.json`. This mapping percentage is informational,
not a whole-feed pass/fail gate: approved merchant feeds can contain thousands
of products that SCENTAI does not intend to catalog.

Only after a satisfactory preflight should the normal merchant import dry-run
and the separate feed-image extraction be executed.

## Feed image approval gate

After extracting affiliate-feed image candidates, review the product identity
and bottle image manually before changing staging data.

Dry-run one exact candidate:

```powershell
python scripts/approve_scentai_feed_image.py --product-id SC-EXAMPLE-100 --image-url "https://cdn.example.com/product.jpg"
```

Apply only after the candidate has been visually verified:

```powershell
python scripts/approve_scentai_feed_image.py --product-id SC-EXAMPLE-100 --image-url "https://cdn.example.com/product.jpg" --write
```

Safety rules:
- the exact product/image pair must exist in the extracted review queue
- the candidate file must remain explicitly marked `review_only_not_live`
- image URLs are revalidated as HTTP/HTTPS at approval time
- the candidate must explicitly propose `approved_feed_image`
- unknown or rejected candidates cannot be approved
- an already approved different image is never overwritten silently
- replacing an approved image requires the explicit
  `--replace-approved-image` flag
- approvals are idempotent when the same image is already approved
- a successful write updates staging to `approved_feed_image` and records
  the review timestamp

Image approval alone does not promote a fragrance. The normal promotion command
still requires every other hard gate, including a current tracked affiliate
offer.

