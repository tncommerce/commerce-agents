"""DUFYND zero-spend, offline-only fingerprint of an Awin-approved original PNG.

A fingerprint is NOT proof of image origin, owner authorization to mirror, or
current image-delivery availability. The script never fetches URLs or writes
public assets, and never activates affiliate products or merchant offers.
"""

from __future__ import annotations

import argparse
import json
from datetime import UTC, datetime, timedelta
from hashlib import sha256
from io import BytesIO
from pathlib import Path
from urllib.parse import urlsplit

from PIL import Image, UnidentifiedImageError

PRODUCT_ID = "SC-YSL-LIBRE-EDP-90"
SKU = "856448"
SOURCE_URL = "https://www.topparfuemerie.de/media/catalog/product/8/5/856448_3614272648425_051.png"
RIGHTS_BASIS = "awin_top_parfuemerie_feed_materials_20260928"
MAX_IMAGE_BYTES = 5 * 1024 * 1024
MAX_FEED_AGE = timedelta(days=7)


def _require(condition: bool, reason: str) -> None:
    if not condition:
        raise ValueError(reason)


def _checked_at(value: str, now: datetime) -> str:
    try:
        moment = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except (AttributeError, ValueError) as exc:
        raise ValueError("feed_checked_at_invalid") from exc
    _require(moment.tzinfo is not None, "feed_checked_at_missing_timezone")
    age = now.astimezone(UTC) - moment.astimezone(UTC)
    _require(timedelta(0) <= age <= MAX_FEED_AGE, "feed_not_current")
    return moment.astimezone(UTC).isoformat()


def check_original_photo_bytes(
    image: bytes,
    metadata: dict,
    readiness: dict,
    registry: list[dict],
    *,
    now: datetime,
) -> dict:
    """Validate only a supplied local file and sanitized first-party evidence.

    The byte source cannot be attested offline. Rehosting and live replacement
    remain explicitly disallowed regardless of checksum or visual metadata.
    """
    _require(now.tzinfo is not None, "now_requires_timezone")
    _require(
        metadata.get("source") == "awin_product_feed_list"
        and metadata.get("advertiser_id") == "31081"
        and metadata.get("feed_id") == "91379"
        and metadata.get("joined") is True
        and metadata.get("downloaded") is True
        and str(metadata.get("membership_status", "")).lower() == "active",
        "official_awin_membership_not_verified",
    )
    checked_at = _checked_at(str(metadata.get("checked_at") or ""), now)

    _require(readiness.get("provider") == "awin-top-parfuemerie-de", "feed_provider_mismatch")
    products = [p for p in readiness.get("products", []) if p.get("product_id") == PRODUCT_ID]
    _require(len(products) == 1, "libre_product_not_unique")
    product = products[0]
    _require(product.get("mapped") is True, "libre_not_mapped")
    _require(
        product.get("feed_image_candidate_count") == 1 and product.get("mapped_offer_count") == 1,
        "libre_feed_candidate_not_unique",
    )
    evidence = product.get("offer_evidence") or []
    _require(
        len(evidence) == 1
        and str(evidence[0].get("merchant_product_id")) == SKU
        and evidence[0].get("merchant_id") == "top-parfuemerie",
        "libre_merchant_sku_mismatch",
    )

    entries = [p for p in registry if p.get("product_id") == PRODUCT_ID]
    _require(len(entries) == 1, "approved_registry_not_unique")
    record = entries[0]
    source = urlsplit(str(record.get("url") or ""))
    _require(
        record.get("url") == SOURCE_URL
        and source.scheme == "https"
        and source.hostname == "www.topparfuemerie.de"
        and source.query == ""
        and source.fragment == ""
        and record.get("volume_ml") == 90
        and record.get("rights_basis_id") == RIGHTS_BASIS,
        "approved_image_identity_or_rights_mismatch",
    )

    _require(
        isinstance(image, bytes) and 32 <= len(image) <= MAX_IMAGE_BYTES,
        "photo_bytes_absent_or_out_of_bounds",
    )
    _require(image.startswith(b"\x89PNG\r\n\x1a\n"), "original_format_not_png")
    try:
        with Image.open(BytesIO(image)) as opened:
            _require(opened.format == "PNG", "original_format_not_png")
            width, height = opened.size
            _require(
                0 < width <= 10000 and 0 < height <= 10000,
                "photo_dimensions_out_of_bounds",
            )
            opened.verify()
    except (UnidentifiedImageError, OSError, SyntaxError) as exc:
        raise ValueError("photo_png_integrity_failed") from exc

    return {
        "status": "PRIVATE_BYTE_FINGERPRINT_ONLY",
        "product_id": PRODUCT_ID,
        "merchant": "top-parfuemerie",
        "merchant_product_id": SKU,
        "registered_source_url": SOURCE_URL,
        "rights_basis_id": RIGHTS_BASIS,
        "official_awin_feed_checked_at": checked_at,
        "source_image_sha256": sha256(image).hexdigest(),
        "source_image_size_bytes": len(image),
        "image_width": width,
        "image_height": height,
        "current_feed_candidate_count": 1,
        "exact_current_feed_image_url_verified": False,
        "image_origin_attested": False,
        "byte_match_to_owner_approved_source": False,
        "public_image_approval": False,
        "public_rehosting_authorized": False,
        "offer_activation_authorized": False,
        "missing_gates": [
            "prove_exact_bytes_from_official_awin_image_source",
            "compare_fingerprint_with_independently_verified_original",
            "reconfirm_unmodified_public_publisher_use_and_owner_go",
            "verify_real_browser_image_delivery_before_release",
        ],
        "new_spend_usd": 0,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--image-file", type=Path, required=True)
    parser.add_argument("--feed-metadata", type=Path, required=True)
    parser.add_argument("--release-readiness", type=Path, required=True)
    parser.add_argument(
        "--approved-registry",
        type=Path,
        default=Path("examples/retail/storefront-web/lib/generated/original-photos.json"),
    )
    args = parser.parse_args()
    try:
        _require(args.image_file.is_file(), "photo_file_missing")
        _require(
            args.image_file.stat().st_size <= MAX_IMAGE_BYTES,
            "photo_bytes_out_of_bounds",
        )
        report = check_original_photo_bytes(
            args.image_file.read_bytes(),
            json.loads(args.feed_metadata.read_text(encoding="utf-8")),
            json.loads(args.release_readiness.read_text(encoding="utf-8")),
            json.loads(args.approved_registry.read_text(encoding="utf-8")),
            now=datetime.now(UTC),
        )
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        parser.exit(2, f"photo_source_preflight_blocked:{exc}\n")
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
