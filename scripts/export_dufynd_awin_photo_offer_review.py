"""Emit six bounded current-feed rows for owner-approved photo/offer review.

Uses only the standard library. Never follows merchant or affiliate URLs and
never approves, activates, stores, or transforms a product image or offer.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import sys
from pathlib import Path
from urllib.parse import parse_qsl, unquote, urlsplit

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "examples"))
from scripts.export_dufynd_awin_four_rows import (  # noqa: E402
    FIELD_PATTERNS,
    _contains_secret,
    safe_url,
)

from retail.api.merchant_feed_reader import read_merchant_feed_rows  # noqa: E402

# Exact six visual candidates accepted by the owner on 2026-10-26. These GTINs
# identify the expected mapping; absent feed GTINs remain absent in `fields`.
TARGETS = {
    "924719": "3770010614630",  # Bois Imperial EDP 100 ml
    "707368": "3349666007921",  # 1 Million EDT 100 ml
    "849484": "3614272225718",  # Stronger With You Intensely EDP 100 ml
    "812773": "3700578502322",  # Layton EDP 125 ml
    "897029": "3614273790826",  # Uomo Born in Roma Intense EDP 100 ml
    "904707": "3700578504364",  # Althair EDP 125 ml
}
PATTERNS = {
    **FIELD_PATTERNS,
    "delivery_cost": r"[0-9]{1,7}(?:[.,][0-9]{1,4})?",
    "delivery_weight": r"[0-9., ]{1,20}(?:kg|g)?",
    "size": r"[0-9., ]{1,20}(?:ml|mL|cl|l)?",
    "volume": r"[0-9., ]{1,20}(?:ml|mL|cl|l)?",
    "product_size": r"[0-9., ]{1,20}(?:ml|mL|cl|l)?",
}
TEXT_LIMITS = {"product_name": 300, "brand_name": 150, "description": 6000}
URL_FIELDS = {
    "merchant_deep_link": "merchant_deep_link",
    "aw_deep_link": "aw_deep_link",
    "merchant_image_url": "merchant_image_url",
    "aw_image_url": "merchant_image_url",
    "large_image": "merchant_image_url",
    "alternate_image": "merchant_image_url",
    "alternate_image_two": "merchant_image_url",
    "alternate_image_three": "merchant_image_url",
    "alternate_image_four": "merchant_image_url",
}
FIELDS = (*PATTERNS, *TEXT_LIMITS, *URL_FIELDS)


def clean(value: str, secret: str) -> bool:
    decoded = value
    for _ in range(6):
        if _contains_secret(decoded, secret) or re.search(
            r"(?i)(apikey|api_key|access_token|authorization|/datafeed/)", decoded
        ):
            return False
        updated = unquote(decoded)
        if updated == decoded:
            return True
        decoded = updated
    return False


def safe_field_url(value: str, field: str, secret: str, targets: dict = TARGETS) -> bool:
    """Reuse existing URL policy; allow the same selector for these six SKUs."""
    if safe_url(value, field, secret):
        return True
    if field != "merchant_deep_link":
        return False
    try:
        parsed = urlsplit(value)
        params = parse_qsl(parsed.query, strict_parsing=True, keep_blank_values=True)
        # Retain the original URL only if the sole extra selector is a target SKU.
        return (
            len(params) == 1
            and params[0][0] == "sku"
            and params[0][1] in targets
            and safe_url(parsed._replace(query="").geturl(), field, secret)
        )
    except ValueError:
        return False


def build_review(
    rows: list[dict],
    metadata: dict,
    feed_bytes: bytes,
    secret: str,
    *,
    targets: dict = TARGETS,
) -> dict:
    if not secret:
        raise ValueError("secret_scan_unavailable")
    if not (
        metadata.get("advertiser_id") == "31081"
        and metadata.get("feed_id") == "91379"
        and metadata.get("joined") is True
        and metadata.get("downloaded") is True
        and metadata.get("download_sha256") == hashlib.sha256(feed_bytes).hexdigest()
        and metadata.get("downloaded_bytes") == len(feed_bytes)
    ):
        raise ValueError("current_feed_identity_or_bytes_not_verified")
    if (
        not targets
        or len(targets) > 100
        or any(
            not re.fullmatch(r"[0-9]{1,16}", str(sku))
            or (gtin is not None and not re.fullmatch(r"[0-9]{8,14}", str(gtin)))
            for sku, gtin in targets.items()
        )
    ):
        raise ValueError("bounded_exact_numeric_targets_required")
    selected = {sku: [] for sku in targets}
    for row in rows:
        sku = row.get("merchant_product_id")
        if sku in selected:
            selected[sku].append(row)
    output = []
    for sku, matches in selected.items():
        item = {"merchant_product_id": sku, "expected_gtin": targets[sku]}
        if len(matches) != 1:
            output.append({**item, "status": "HOLD", "matches": len(matches)})
            continue
        row = matches[0]
        fields, missing, withheld = {}, [], []
        for name in FIELDS:
            if name not in row:
                missing.append(name)
                continue
            value = row[name]
            allowed = isinstance(value, str) and clean(value, secret)
            if allowed and value:
                if name in URL_FIELDS:
                    allowed = safe_field_url(value, URL_FIELDS[name], secret, targets)
                elif name in PATTERNS:
                    allowed = bool(re.fullmatch(PATTERNS[name], value))
                else:
                    allowed = len(value) <= TEXT_LIMITS[name] and not re.search(
                        r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]", value
                    )
            if allowed:
                fields[name] = value
            else:
                withheld.append(name)
        output.append(
            {
                **item,
                "status": "REVIEW_ONLY_NOT_APPROVED",
                "source_row_canonical_json_sha256": hashlib.sha256(
                    json.dumps(row, ensure_ascii=False, sort_keys=True).encode()
                ).hexdigest(),
                "fields": fields,
                "missing_fields": missing,
                "withheld_fields": withheld,
            }
        )
    metadata_keys = (
        "checked_at",
        "source",
        "advertiser_id",
        "feed_id",
        "membership_status",
        "joined",
        "last_imported",
        "downloaded",
        "downloaded_bytes",
        "download_sha256",
    )
    report = {
        "schema_version": 1,
        "status": "CURRENT_SOURCE_REVIEW_ONLY",
        "feed": {k: metadata[k] for k in metadata_keys if k in metadata},
        "rows": output,
        "activation_allowed": False,
        "image_publication_allowed": False,
        "tracking_clicks_executed": 0,
        "price_verified_at_not_inferred_from_import": True,
    }
    if not clean(json.dumps(report), secret):
        raise ValueError("secret_scan_rejected")
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--feed", required=True, type=Path)
    parser.add_argument("--metadata", required=True, type=Path)
    args = parser.parse_args()
    try:
        report = build_review(
            read_merchant_feed_rows(args.feed),
            json.loads(args.metadata.read_text()),
            args.feed.read_bytes(),
            os.environ.get("AWIN_DATA_FEED_API_KEY", ""),
        )
    except Exception:
        print("photo_offer_review_export_failed_closed", file=sys.stderr)
        return 2
    # JSON escapes all field newlines/control characters; no workflow commands.
    print("DUFYND_BOUNDED_PHOTO_OFFER_REVIEW=" + json.dumps(report, ensure_ascii=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
