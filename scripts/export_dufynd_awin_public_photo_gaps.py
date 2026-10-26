"""Read-only bounded discovery for the 27 existing public missing-photo profiles.

Reuses the source-byte binding and field/secret filters of the six-photo exporter.
Name matches are leads only: no GTIN, size, rights or approval is inferred.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
import unicodedata
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "examples"))
from scripts.export_dufynd_awin_photo_offer_review import build_review  # noqa: E402

from retail.api.merchant_feed_reader import read_merchant_feed_rows  # noqa: E402


def norm(value: str) -> set[str]:
    value = unicodedata.normalize("NFKD", value).casefold()
    value = "".join(c for c in value if not unicodedata.combining(c))
    return set(re.findall(r"[a-z0-9]+", value)) - {"perfumes", "parfums"}


def build_discovery(
    rows: list[dict], metadata: dict, source: bytes, secret: str, gap: dict
) -> dict:
    items = gap.get("items", [])
    if (
        gap.get("status") != "DISCOVERY_ONLY_NO_VARIANT_OR_IMAGE_APPROVAL"
        or len(items) != 27
        or len({x.get("product_id") for x in items}) != 27
    ):
        raise ValueError("exact_existing_public_gap_manifest_required")
    candidates: dict[str, set[str]] = {}
    scope = []
    for item in items:
        identity = norm(item["brand"]) | norm(item["name"])
        matches = sorted(
            {
                str(row.get("merchant_product_id", ""))
                for row in rows
                if identity
                and identity <= norm(str(row.get("product_name", "")))
                and re.fullmatch(r"[0-9]{1,16}", str(row.get("merchant_product_id", "")))
            }
        )
        # Fail closed on unexpected expansion rather than silently truncating.
        if len(matches) > 24:
            raise ValueError("profile_match_bound_exceeded")
        scope.append(
            {
                **item,
                "matched_merchant_skus": matches,
                "status": "REVIEW_LEADS_ONLY" if matches else "NO_CURRENT_TOP_FEED_LEAD",
            }
        )
        for sku in matches:
            candidates.setdefault(sku, set()).add(item["product_id"])
    offer_only = gap.get("offer_only_existing_originals", [])
    if {x.get("merchant_product_id") for x in offer_only} != {
        "780879",
        "825869",
        "856448",
        "787670",
    }:
        raise ValueError("exact_existing_original_offer_scope_required")
    for item in offer_only:
        candidates.setdefault(item["merchant_product_id"], set()).add(item["product_id"])
    if len(candidates) > 60:
        raise ValueError("total_match_bound_exceeded")
    if not candidates:
        raise ValueError("no_current_source_candidates")
    report = build_review(
        rows, metadata, source, secret, targets={sku: None for sku in sorted(candidates)}
    )
    for row in report["rows"]:
        row["candidate_public_profile_ids"] = sorted(candidates[row["merchant_product_id"]])
    report["scope"] = scope
    report["offer_only_existing_originals"] = offer_only
    report["status"] = "PUBLIC_GAP_DISCOVERY_ONLY_NOT_VARIANT_APPROVED"
    report["source_website_head"] = gap["source_website_head"]
    report["existing_original_photos_excluded"] = 10
    report["no_size_or_gtin_inferred_from_filename"] = True
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--feed", required=True, type=Path)
    parser.add_argument("--metadata", required=True, type=Path)
    parser.add_argument("--gap-manifest", required=True, type=Path)
    args = parser.parse_args()
    try:
        report = build_discovery(
            read_merchant_feed_rows(args.feed),
            json.loads(args.metadata.read_text()),
            args.feed.read_bytes(),
            os.environ.get("AWIN_DATA_FEED_API_KEY", ""),
            json.loads(args.gap_manifest.read_text()),
        )
    except Exception:
        print("public_photo_gap_export_failed_closed", file=sys.stderr)
        return 2
    print("DUFYND_PUBLIC_PHOTO_GAP_REVIEW=" + json.dumps(report, ensure_ascii=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
