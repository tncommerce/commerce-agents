# SCENTAI Affiliate Feed Activation Runbook

Status: prepared
Updated: 2026-09-19

## Purpose

Use this workflow after an affiliate program is approved and a real merchant
feed or export sample is available.

Do not guess network field names, merchant product IDs, EANs, GTINs, tracked
URLs, prices or image URLs before a real approved source exists.

The first guarded target is:

`examples/retail/data/scentai_release_batch_01.json`

## 1. Keep raw feed data out of source control

Store the downloaded feed locally in a temporary working path. Do not commit
affiliate credentials, private feed URLs, tokens, passwords or raw exports.

## 2. Create the provider field map from the real feed

Start from:

`examples/retail/data/scentai_affiliate_provider_config.example.json`

Map only columns that actually exist in the approved feed sample.

The provider config must normalize at least:
- offer ID
- one product identifier (merchant SKU, EAN or GTIN)
- price
- stock status
- product URL
- last-updated timestamp

For release promotion, the feed should additionally provide:
- tracked affiliate URL
- image URL

## 3. Run the release-specific read-only check

From the repository root:

```powershell
python scripts/check_scentai_release_feed.py --feed <LOCAL_FEED_FILE> --provider-config <PROVIDER_CONFIG>
```

Expected states:

- `BLOCKED`: feed structure itself is not safe to import.
- `REVIEW`: feed is structurally importable but Batch 01 mapping, affiliate
  offer coverage or feed-image coverage is incomplete.
- `READY_FOR_MANUAL_ASSET_REVIEW`: all five Batch 01 products have mapped,
  in-stock tracked offers and reviewable feed-image candidates.

A ready result does not approve images automatically.

## 4. Resolve exact product mappings

Only add a mapping after the merchant SKU/EAN/GTIN is verified against the
correct SCENTAI canonical fragrance, concentration and size.

Write verified mappings to:

`examples/retail/data/merchant_product_mappings.json`

Re-run the release checker after every mapping change.

## 5. Dry-run the existing merchant import

Use the existing merchant import pipeline with the same feed and provider
config. Do not write offers until the dry-run is clean.

The import pipeline already protects against:
- duplicate offer IDs
- invalid provider rows
- unknown product mappings
- changed feed/mapping snapshots during processing
- unsafe authoritative empty writes

## 6. Extract and manually review feed images

Use the existing feed-image extraction path. Feed images remain review-only
until the exact bottle/product pair is visually approved.

Never approve a generic brand image, wrong concentration, wrong bottle size,
gift set, tester, refill or legacy edition as the canonical product image.

## 7. Re-check Batch 01

After verified mappings, real tracked offers and approved images are present:

```powershell
python scripts/promote_scentai_catalog.py --manifest examples/retail/data/scentai_release_batch_01.json
```

The dry-run must report all five products ready.

## 8. Promote only as one guarded batch

Only after the dry-run reports 5 ready / 0 blocked:

```powershell
python scripts/promote_scentai_catalog.py --manifest examples/retail/data/scentai_release_batch_01.json --write
```

Partial release is intentionally refused.

## Ranking rule

Affiliate commission must never influence SCENTAI product recommendations or
merchant ranking. Merchant selection remains based on availability, total
customer price, trust, shipping and data freshness before commission.
