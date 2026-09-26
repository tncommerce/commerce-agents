# SCENTAI Catalog Scale & Merchant Coverage Status

Status: active
Updated: 2026-09-19

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
- 29/30 have at least one verified current-edition merchant
- 29/30 have at least two verified merchants
- 5/30 have three researched merchants
- 1/30 currently has no verified current-edition retail channel:
  - Jean Paul Gaultier Fleur du Mâle (2026)

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
- staged products with resolved merchant-product mappings: **28/30**

The existing merchant-offer layer currently contains offers for the already
live Essential Parfums Bois Impérial product. Those offers do not make any of
the 30 staging products promotion-ready.

The merchant-mapping file retains verified Douglas and flaconi identifiers for
the already-live Bois Impérial record. In addition, all twenty-five products across
Release Batches 01 through 05 have resolved merchant-product mappings with
GTIN/EAN fallback identifiers. In addition, Kayali Yum Boujee Marshmallow | 81,
Lattafa Angham and Lattafa Eclaire are pre-mapped for future affiliate-feed
activation without being assigned to a release.

This means identity/mapping readiness is **28/30** for the staged expansion
pool, while release-planned coverage remains **25/30** and live-offer readiness
remains **0/30**. Mapping readiness must not be
described as affiliate approval, current pricing or image approval.

## Current blockers

For the stable 28 candidates:
- approved product image missing
- current tracked affiliate offer missing

For the two provisional candidates:
- approved product image missing
- current tracked affiliate offer missing
- community/performance evidence still provisional

Additional retail-channel blocker:
- Jean Paul Gaultier Fleur du Mâle (2026): verified current merchant still pending

No product should be promoted by filling any of these fields with guessed data.

## Next 10-product worklist

The current planner prioritizes underrepresented live audiences while still
respecting promotion blockers, researched merchant coverage and community
sample size.

Current worklist:

1. Lancôme La Vie est Belle Eau de Parfum 100 ml
2. Parfums de Marly Delina Eau de Parfum 75 ml
3. Dior Hypnotic Poison Eau de Toilette 100 ml
4. Yves Saint Laurent Black Opium Eau de Parfum 90 ml
5. Yves Saint Laurent Libre Eau de Parfum 90 ml
6. Guerlain Mon Guerlain Eau de Parfum 100 ml
7. Narciso Rodriguez for her PURE MUSC Eau de Parfum 100 ml
8. Chloé Chloé Eau de Parfum 100 ml
9. Burberry Goddess Eau de Parfum 100 ml
10. Prada Paradoxe Eau de Parfum 90 ml

All ten are currently blocked by the same two production requirements:
- approved image
- current tracked affiliate offer

## Phase 4L merchant-coverage progress

On 2026-09-19, verified merchant research was expanded for:
- Lancôme La Vie est Belle
- Viktor & Rolf Spicebomb Extreme
- Narciso Rodriguez for her PURE MUSC
- Amouage Guidance 46
- Parfums de Marly Herod
- Tom Ford Ombré Leather Eau de Parfum
- Nishane Ani
- Lattafa Angham
- Kayali Yum Boujee Marshmallow | 81

Jean Paul Gaultier Fleur du Mâle (2026) is now intentionally recorded with
zero verified current-edition retail channels. The official German Gaultier
page still exposes the return as a teaser, while the indexed Notino page cannot
be distinguished safely from the discontinued 2007 edition. Legacy or
edition-ambiguous retailer pages must not be counted toward the 2026 re-edition
until the current edition is explicit.

This correction reduces headline merchant coverage from 30/30 to 29/30. That is
a deliberate data-quality improvement, not a regression.

A regression test now checks that the promotion queue never declares fewer researched merchants than verification data explicitly marks as available.

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


## Affiliate activation preparation

All currently applied Awin programs and the pending CJ Notino application now
have normalized merchant IDs and matching entries in `merchant_partners.json`.

Every not-yet-approved partner remains:
- `pending_affiliate_link`
- without an affiliate URL
- without an activation timestamp

A regression test now prevents an applied/pending affiliate program from being
missing from the partner registry or being activated before real tracking is
configured.


## Release batch 01

The first guarded mini-release is now frozen in
`scentai_release_batch_01.json` with five products:

1. Lancôme La Vie est Belle Eau de Parfum 100 ml
2. Parfums de Marly Delina Eau de Parfum 75 ml
3. Dior Hypnotic Poison Eau de Toilette 100 ml
4. Yves Saint Laurent Black Opium Eau de Parfum 90 ml
5. Yves Saint Laurent Libre Eau de Parfum 90 ml

This is an operational release batch, not a fragrance quality ranking.

The promotion CLI accepts the manifest directly:

```powershell
python scripts/promote_scentai_catalog.py --manifest examples/retail/data/scentai_release_batch_01.json
```

The command is a dry-run by default. The eventual write command is allowed only
after all five products pass every gate:

```powershell
python scripts/promote_scentai_catalog.py --manifest examples/retail/data/scentai_release_batch_01.json --write
```

Partial promotion is refused. The manifest itself is also tested for size,
duplicate product IDs, staging existence, non-provisional community data and
minimum researched merchant coverage.


## Affiliate feed activation readiness

A release-specific, read-only feed checker is now available:

```powershell
python scripts/check_scentai_release_feed.py --feed <LOCAL_FEED_FILE> --provider-config <PROVIDER_CONFIG>
```

It evaluates the real approved feed against Release Batch 01 and reports:
- structural feed import readiness
- Batch 01 product mapping coverage
- in-stock tracked affiliate-offer coverage
- reviewable feed-image coverage
- per-product gaps

The checker performs no writes and never approves images automatically.

The full post-approval operating procedure is documented in
`scentai_affiliate_feed_activation_runbook.md`.

Current state remains intentionally blocked because no approved production feed
has yet supplied real Batch 01 product identifiers, tracked offers or approved
images.


## Release batch 02

The second guarded mini-release is prepared in
`scentai_release_batch_02.json` with five additional stable candidates:

1. Guerlain Mon Guerlain Eau de Parfum 100 ml
2. Narciso Rodriguez for her PURE MUSC Eau de Parfum 100 ml
3. Chloé Chloé Eau de Parfum 100 ml
4. Burberry Goddess Eau de Parfum 100 ml
5. Prada Paradoxe Eau de Parfum 90 ml

All five now have at least two merchant mapping rows plus GTIN/EAN fallback
identifiers.

Release 02 is intentionally **write-locked** at manifest level. Dry-runs remain
allowed, but `--write` is rejected until Release 01 has completed the real
purchase-destination, manual image-approval, promotion and smoke-test workflow.

Release 01 remains write-capable only in the narrow sense that the CLI may
attempt a write after every existing product-level gate passes. At the current
state, Release 01 is still blocked because no current verified purchase destinations
or approved production images exist for its five products.


## Release batch 03

Release 03 is prepared in `scentai_release_batch_03.json` with:

1. Parfums de Marly Valaya Exclusif Eau de Parfum 75 ml
2. Amouage Guidance 46 Extrait de Parfum 100 ml
3. Tom Ford Ombré Leather Eau de Parfum 100 ml
4. Parfums de Marly Herod Eau de Parfum 125 ml
5. Nishane Ani Extrait de Parfum 100 ml

The selection adds a feed-readiness constraint on top of the catalog priority
signals. Lattafa Eclaire, Kayali Yum Boujee Marshmallow | 81 and Lattafa
Angham remain higher portfolio-gap candidates, but their currently verified
merchant coverage is not yet aligned strongly enough with SCENTAI's applied
production affiliate feeds. They remain in staging rather than being forced
into Release 03.

All five Release 03 products have redundant merchant mappings at Douglas,
flaconi or parfumdreams and have GTIN/EAN fallback identifiers.

Release 03 is write-locked. It may be dry-run checked, but cannot be written
live until the earlier release sequence has been validated operationally.


## Release batch 04

Release 04 is prepared in `scentai_release_batch_04.json` with:

1. Jean Paul Gaultier Le Male Le Parfum 125 ml
2. Viktor & Rolf Spicebomb Extreme 90 ml
3. Hugo Boss BOSS Bottled Absolu 100 ml
4. Yves Saint Laurent MYSLF Le Parfum 100 ml
5. Dior Sauvage Elixir 100 ml

All five have redundant mapping paths across merchants already represented in
SCENTAI's affiliate application registry. Release 04 is write-locked until the
earlier release sequence is operationally validated.

## Release batch 05

Release 05 is prepared in `scentai_release_batch_05.json` with:

1. Hugo Boss BOSS Bottled Eau de Toilette 100 ml
2. Prada L'Homme Intense Eau de Parfum 100 ml
3. Amouage Reflection Man Eau de Parfum 100 ml
4. Initio Side Effect Eau de Parfum 90 ml
5. Yves Saint Laurent La Nuit de L'Homme Eau de Toilette 100 ml

Reflection Man and Side Effect retain alternate packaging/barcode evidence
explicitly in verification data rather than pretending that one barcode must
describe every market package. Release 05 is write-locked until Releases 01-04
have completed the real feed, image approval, promotion and smoke-test flow.

## Deferred five-product backlog

After Releases 01-05, exactly five staged products remain outside a prepared
release:

- Jean Paul Gaultier Fleur du Mâle (2026)
- Dolce & Gabbana The One for Men Eau de Parfum (2025)
- Kayali Yum Boujee Marshmallow | 81
- Lattafa Angham
- Lattafa Eclaire

The first two remain blocked by provisional/version-sensitive evidence and are
the only two staging products that intentionally remain unmapped. The other
three now have identity mappings prepared, but remain outside a release because
their currently verified merchant coverage is not yet aligned strongly enough
with a production-ready SCENTAI affiliate feed.

The machine-readable source of truth is
`scentai_release_deferred_backlog.json`.

This is intentional. SCENTAI should preserve data quality and operational
readiness rather than chase a cosmetic 30/30 mapping number.


## Release pipeline operator report

The five prepared release manifests can now be checked in one command:

```powershell
python scripts/report_scentai_release_pipeline.py
```

Machine-readable output:

```powershell
python scripts/report_scentai_release_pipeline.py --machine-readable
```

The report keeps separate:
- merchant mapping readiness
- GTIN fallback readiness
- current tracked affiliate offers
- approved product images
- product-level promotion blockers
- manifest-level write locks

A release can therefore be product-ready without being write-ready. This is
intentional and prevents later batches from bypassing the operational sequence.
