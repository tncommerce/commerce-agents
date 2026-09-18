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
