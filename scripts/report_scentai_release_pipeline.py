from __future__ import annotations

import argparse
import json
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from scripts.promote_scentai_catalog import (
    eligible_affiliate_offers,
    eligible_purchase_offers,
    load_json,
    promotion_blockers,
    release_manifest_write_enabled,
)

DATA_DIR = Path("examples/retail/data")
DEFAULT_STAGING = DATA_DIR / "scentai_catalog_staging.json"
DEFAULT_OFFERS = DATA_DIR / "merchant_offers.json"
DEFAULT_MAPPINGS = DATA_DIR / "merchant_product_mappings.json"
DEFAULT_RELEASE_GLOB = "scentai_release_batch_*.json"


def load_release_manifests(
    directory: Path = DATA_DIR,
    pattern: str = DEFAULT_RELEASE_GLOB,
) -> list[tuple[Path, dict]]:
    rows: list[tuple[Path, dict]] = []

    for path in sorted(directory.glob(pattern)):
        payload = load_json(path)
        if not str(payload.get("release_id") or "").strip():
            continue
        if not isinstance(payload.get("product_ids"), list):
            continue
        rows.append((path, payload))

    return rows


def mapping_index(mappings_payload: dict) -> dict[str, list[dict]]:
    rows = mappings_payload.get("mappings", [])
    index: dict[str, list[dict]] = {}

    for row in rows:
        product_id = str(row.get("product_id") or "").strip()
        if not product_id:
            continue
        index.setdefault(product_id, []).append(row)

    return index


def build_release_pipeline_report(
    releases: list[tuple[Path, dict]],
    staging: dict,
    offers_payload: dict,
    mappings_payload: dict,
    *,
    now: datetime,
    max_offer_age_hours: float = 72.0,
) -> dict[str, Any]:
    staged_by_id = {
        str(product.get("product_id") or ""): product
        for product in staging.get("products", [])
        if str(product.get("product_id") or "").strip()
    }
    mappings_by_id = mapping_index(mappings_payload)
    offers = offers_payload.get(
        "offers",
        offers_payload if isinstance(offers_payload, list) else [],
    )

    release_rows: list[dict[str, Any]] = []
    all_release_product_ids: set[str] = set()

    for manifest_path, manifest in releases:
        product_ids = [
            str(product_id).strip()
            for product_id in manifest.get("product_ids", [])
            if str(product_id).strip()
        ]
        all_release_product_ids.update(product_ids)

        product_rows: list[dict[str, Any]] = []
        blocker_counts: Counter = Counter()

        for product_id in product_ids:
            product = staged_by_id.get(product_id)
            mapping_rows = mappings_by_id.get(product_id, [])

            has_mapping = bool(mapping_rows)
            has_redundant_mapping = len(mapping_rows) >= 2
            has_gtin_fallback = any(
                str(row.get("ean") or "").strip() and str(row.get("gtin") or "").strip()
                for row in mapping_rows
            )

            product_blockers: list[str] = []
            affiliate_offer_count = 0
            purchase_offer_count = 0

            if product is None:
                product_blockers.append("missing_staging_product")
            else:
                product_blockers.extend(
                    promotion_blockers(
                        product,
                        offers,
                        now=now,
                        max_offer_age_hours=max_offer_age_hours,
                    )
                )
                affiliate_offer_count = len(
                    eligible_affiliate_offers(
                        offers,
                        product_id=product_id,
                        now=now,
                        max_age_hours=max_offer_age_hours,
                    )
                )
                purchase_offer_count = len(
                    eligible_purchase_offers(
                        offers,
                        product_id=product_id,
                        now=now,
                        max_age_hours=max_offer_age_hours,
                    )
                )

            if not has_mapping:
                product_blockers.append("missing_merchant_mapping")
            elif not has_redundant_mapping:
                product_blockers.append("single_merchant_mapping_only")

            if not has_gtin_fallback:
                product_blockers.append("missing_gtin_fallback")

            blocker_counts.update(product_blockers)

            product_rows.append(
                {
                    "product_id": product_id,
                    "mapping_count": len(mapping_rows),
                    "mapped_merchants": sorted(
                        {
                            str(row.get("merchant") or "").strip()
                            for row in mapping_rows
                            if str(row.get("merchant") or "").strip()
                        }
                    ),
                    "has_gtin_fallback": has_gtin_fallback,
                    "eligible_affiliate_offers": affiliate_offer_count,
                    "eligible_purchase_offers": purchase_offer_count,
                    "ready": not product_blockers,
                    "blockers": product_blockers,
                }
            )

        write_enabled = manifest.get("write_enabled") is True and release_manifest_write_enabled(
            manifest_path
        )
        ready_products = sum(1 for row in product_rows if row["ready"])
        all_products_ready = bool(product_rows) and ready_products == len(product_rows)

        release_blockers = list(blocker for blocker, _count in blocker_counts.most_common())
        if not write_enabled:
            release_blockers.append("manifest_write_locked")

        release_rows.append(
            {
                "release_id": manifest["release_id"],
                "manifest": str(manifest_path),
                "manifest_status": manifest.get("status"),
                "write_enabled": write_enabled,
                "product_count": len(product_rows),
                "mapped_product_count": sum(1 for row in product_rows if row["mapping_count"] > 0),
                "redundantly_mapped_product_count": sum(
                    1 for row in product_rows if row["mapping_count"] >= 2
                ),
                "gtin_fallback_product_count": sum(
                    1 for row in product_rows if row["has_gtin_fallback"]
                ),
                "affiliate_offer_product_count": sum(
                    1 for row in product_rows if row["eligible_affiliate_offers"] > 0
                ),
                "purchase_offer_product_count": sum(
                    1 for row in product_rows if row["eligible_purchase_offers"] > 0
                ),
                "ready_product_count": ready_products,
                "all_products_ready": all_products_ready,
                "write_ready": all_products_ready and write_enabled,
                "blocker_counts": dict(blocker_counts),
                "release_blockers": release_blockers,
                "products": product_rows,
            }
        )

    mapped_staged_product_ids = {
        product_id for product_id in mappings_by_id if product_id in staged_by_id
    }

    return {
        "generated_at": now.astimezone(UTC).isoformat(),
        "release_count": len(release_rows),
        "staged_product_count": len(staged_by_id),
        "release_product_count": len(all_release_product_ids),
        "mapped_staged_product_count": len(mapped_staged_product_ids),
        "unmapped_staged_product_count": (len(staged_by_id) - len(mapped_staged_product_ids)),
        "write_ready_release_count": sum(1 for release in release_rows if release["write_ready"]),
        "releases": release_rows,
    }


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Report guarded SCENTAI release-pipeline readiness across all "
            "prepared release manifests."
        )
    )
    parser.add_argument(
        "--staging",
        type=Path,
        default=DEFAULT_STAGING,
    )
    parser.add_argument(
        "--offers",
        type=Path,
        default=DEFAULT_OFFERS,
    )
    parser.add_argument(
        "--mappings",
        type=Path,
        default=DEFAULT_MAPPINGS,
    )
    parser.add_argument(
        "--release-dir",
        type=Path,
        default=DATA_DIR,
    )
    parser.add_argument(
        "--release-pattern",
        default=DEFAULT_RELEASE_GLOB,
    )
    parser.add_argument(
        "--max-offer-age-hours",
        type=float,
        default=72.0,
    )
    parser.add_argument(
        "--machine-readable",
        action="store_true",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=None,
    )
    args = parser.parse_args()

    releases = load_release_manifests(
        args.release_dir,
        args.release_pattern,
    )
    report = build_release_pipeline_report(
        releases,
        load_json(args.staging),
        load_json(args.offers),
        load_json(args.mappings),
        now=datetime.now(UTC),
        max_offer_age_hours=args.max_offer_age_hours,
    )

    if args.output is not None:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(
            json.dumps(report, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )

    if args.machine_readable:
        print(json.dumps(report, ensure_ascii=False))
        return 0

    print(
        "SCENTAI release pipeline | "
        f"releases={report['release_count']} | "
        f"staged={report['staged_product_count']} | "
        f"mapped={report['mapped_staged_product_count']} | "
        f"write_ready_releases={report['write_ready_release_count']}"
    )

    for release in report["releases"]:
        blockers = ", ".join(release["release_blockers"]) or "-"
        print(
            f"{release['release_id']} | "
            f"mapped={release['mapped_product_count']}/"
            f"{release['product_count']} | "
            f"purchase={release['purchase_offer_product_count']}/"
            f"{release['product_count']} | "
            f"affiliate={release['affiliate_offer_product_count']}/"
            f"{release['product_count']} | "
            f"ready={release['ready_product_count']}/"
            f"{release['product_count']} | "
            f"write_enabled={release['write_enabled']} | "
            f"blockers={blockers}"
        )

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
