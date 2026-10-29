"""Awin Enhanced JSONL is a *candidate* source, never a live certificate."""

from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from scripts.review_dufynd_awin_enhanced_feed import (
    read_selected_jsonl,
    review_enhanced_candidates,
)

ROOT = Path("examples/retail/data")
NOW = datetime(2026, 10, 27, 12, 0, tzinfo=UTC)


def context():
    offers = json.loads((ROOT / "merchant_offers.json").read_text(encoding="utf-8"))
    top = next(
        item
        for item in offers["offers"]
        if item["offer_id"] == "top-parfuemerie-rabanne-1-million-edt-100"
    )
    partner = json.loads((ROOT / "merchant_partners.json").read_text(encoding="utf-8"))
    mappings = json.loads((ROOT / "merchant_product_mappings.json").read_text(encoding="utf-8"))
    catalog = json.loads((ROOT / "catalog.json").read_text(encoding="utf-8"))
    return top, partner, mappings, catalog


def sample_row():
    return {
        "id": "707368",
        "gtin": "3349666007921",
        "brand": "Rabanne",
        "size": "100 ml",
        "unit_pricing_measure": "100 ml",
        "availability": "in_stock",
        "price": "92.95 EUR",
        "shipping": [{"country": "DE", "price": "0.00 EUR"}],
        # A foreign URL must never overwrite canonical merchant/affiliate URLs.
        "link": "https://untrusted.example.invalid/click?tracking=fake",
    }


def scan(tmp_path: Path, rows):
    path = tmp_path / "synthetic-enhanced-feed.jsonl"
    payload = b"".join((json.dumps(item, sort_keys=True) + "\n").encode("utf-8") for item in rows)
    path.write_bytes(payload)
    selected, sha, scanned = read_selected_jsonl(path, {"707368"})
    return selected, sha, scanned


def receipt(sha):
    return {
        "publisher_id": "3099222",
        "advertiser_id": "31081",
        "source_type": "awin_enhanced_retail_jsonl",
        "download_sha256": sha,
        "downloaded_at": NOW.isoformat(),
    }


def analyze(rows, sha, *, receipt_override=None):
    top, partners, mappings, catalog = context()
    return review_enhanced_candidates(
        [top],
        partners,
        mappings,
        catalog,
        selected_rows=rows,
        publisher_source=receipt_override or receipt(sha),
        original_digest=sha,
        now=NOW,
    )


def test_exact_variant_fields_are_only_review_candidates(tmp_path):
    rows, sha, scanned = scan(tmp_path, [sample_row()])
    report = analyze(rows, sha)
    assert scanned == 1
    assert report["counts"] == {
        "FIELD_COMPLETE_REVIEW_ONLY": 1,
        "BLOCKED_SOURCE_FIELDS": 0,
    }
    assert report["status"] == "ENHANCED_FEED_FIELD_TRIAGE_ONLY_NOT_CERTIFIED"
    assert report["source_rows_authenticated_by_this_script"] is False
    assert report["per_sku_price_timestamp_verified"] is False
    assert report["not_a_purchase_price_certificate"] is True
    assert report["public_offer_activations"] == 0
    assert report["database_writes"] == 0
    assert report["affiliate_clickouts"] == 0
    public_report = json.dumps(report)
    assert "92.95" not in public_report
    assert "untrusted.example.invalid" not in public_report
    assert "pclick" not in public_report


@pytest.mark.parametrize(
    ("changed", "expected"),
    [
        ({"gtin": "3614272648425"}, "GTIN_MISSING_OR_DIFFERENT"),
        ({"size": "50 ml"}, "SIZE_MISSING_OR_DIFFERENT"),
        ({"availability": "out_of_stock"}, "EXACT_VARIANT_NOT_CONFIRMED_IN_STOCK"),
        ({"price": "0.00 EUR"}, "EUR_PRICE_MISSING_OR_INVALID"),
        ({"price": "95.99 USD"}, "EUR_PRICE_MISSING_OR_INVALID"),
        ({"sale_price": "90.00 EUR"}, "PROMOTIONAL_PRICE_NEEDS_APPROVAL"),
        ({"shipping": []}, "DE_SHIPPING_MISSING_OR_AMBIGUOUS"),
        (
            {"shipping": [{"country": "DE", "region": "NW", "price": "0.00 EUR"}]},
            "DE_SHIPPING_REGION_SPECIFIC",
        ),
        ({"shipping": [{"country": "DE", "price": "5.00 USD"}]}, "DE_SHIPPING_PRICE_UNCONFIRMED"),
        (
            {
                "shipping": [
                    {"country": "DE", "price": "0.00 EUR"},
                    {"country": "DE", "price": "4.99 EUR"},
                ]
            },
            "DE_SHIPPING_MISSING_OR_AMBIGUOUS",
        ),
        ({"brand": "Other Brand"}, "BRAND_NEEDS_REVIEW"),
    ],
)
def test_invalid_exact_merchant_quote_remains_blocked(tmp_path, changed, expected):
    row = sample_row() | changed
    selected, sha, _ = scan(tmp_path, [row])
    report = analyze(selected, sha)
    assert report["counts"]["FIELD_COMPLETE_REVIEW_ONLY"] == 0
    assert report["items"][0]["reason"] == expected


def test_identical_sku_source_rows_never_use_last_row_wins(tmp_path):
    rows, sha, scanned = scan(tmp_path, [sample_row(), sample_row()])
    result = analyze(rows, sha)
    assert scanned == 2
    assert result["items"][0]["reason"] == "DUPLICATE_ENHANCED_SKU"


def test_unmatched_source_never_creates_a_public_product(tmp_path):
    row = sample_row() | {"id": "not-an-existing-merchant-sku"}
    found, sha, count = scan(tmp_path, [row])
    result = analyze(found, sha)
    assert count == 1
    assert result["items"][0]["reason"] == "EXACT_MERCHANT_SKU_ABSENT"
    assert result["offer_count"] == 1


def test_wrong_publisher_or_stale_feed_receipt_fails_closed(tmp_path):
    rows, sha, _ = scan(tmp_path, [sample_row()])
    bad_publisher = receipt(sha) | {"publisher_id": "9999999"}
    with pytest.raises(ValueError, match="enhanced_feed_provenance_not_attested"):
        analyze(rows, sha, receipt_override=bad_publisher)
    old = receipt(sha) | {"downloaded_at": (NOW - timedelta(hours=73)).isoformat()}
    with pytest.raises(ValueError, match="feed_download_too_old_or_future"):
        analyze(rows, sha, receipt_override=old)
    fake_sha = receipt(sha) | {"download_sha256": "f" * 64}
    with pytest.raises(ValueError, match="enhanced_feed_provenance_not_attested"):
        analyze(rows, sha, receipt_override=fake_sha)


def test_source_hash_covers_every_line_not_only_selected_skus(tmp_path):
    other = sample_row() | {"id": "does-not-match-any-canonical"}
    selected, sha, scanned = scan(tmp_path, [sample_row(), other])
    assert scanned == 2
    assert (
        sha
        != hashlib.sha256(
            (json.dumps(sample_row(), sort_keys=True) + "\n").encode("utf-8")
        ).hexdigest()
    )
    assert len(selected["707368"]) == 1
    assert analyze(selected, sha)["counts"]["FIELD_COMPLETE_REVIEW_ONLY"] == 1


@pytest.mark.parametrize("text", [b"{not-json\n", b"null\n", b'{"id":"707368","price":NaN}\n'])
def test_untrusted_jsonl_errors_fail_entire_source(tmp_path, text):
    path = tmp_path / "bad.jsonl"
    path.write_bytes(text)
    with pytest.raises(ValueError, match="invalid_enhanced_source"):
        read_selected_jsonl(path, {"707368"})
