# Photo review integrity — development only, 2026-10-12

PR #776 reused the stricter existing matcher and regression cases from PR #774 at `b5a6afa24cfb10d479d537d925678c6d35ce1cd8`: exact brand, name, concentration and size; bounded observed aliases; rejection of flankers, multipacks and conflicting mapped GTINs. Only the two photo-review script/test files were shared, not the catalog release.

A further reproduced bug counted duplicate merchant SKUs only after excluding unsafe or absent image URLs. This hid conflicting rows and also allowed ambiguous name-only candidates. The fix counts all numeric SKU rows before image screening, rejects duplicate candidates through both paths and reports `duplicate_feed_sku_hold`, preserving `duplicate_pinned_feed_sku_hold`. A single unusable image still produces no candidate.

Validation: old code failed the new regression suite; corrected code passed 99 tests across `test_dufynd_public_photo_feed_leads.py` and `test_dufynd_catalog_photo_wave.py`; Ruff check and format pass. Fixtures exercise valid, empty and disallowed duplicate URLs in both input orders. No network, new image, new rights claim, registration, offer, database write or public deployment. All candidates remain manual review holds.
