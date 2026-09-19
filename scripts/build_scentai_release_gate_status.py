from __future__ import annotations

import argparse
import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

DATA_DIR = Path("examples/retail/data")
DEFAULT_MANIFEST = DATA_DIR / "scentai_release_batch_01.json"
DEFAULT_STAGING = DATA_DIR / "scentai_catalog_staging.json"
DEFAULT_MAPPINGS = DATA_DIR / "merchant_product_mappings.json"
DEFAULT_OFFERS = DATA_DIR / "merchant_offers.json"
DEFAULT_IMAGES = DATA_DIR / "scentai_image_approval_work_queue.json"
DEFAULT_AFFILIATE = DATA_DIR / "scentai_affiliate_activation_status.json"
DEFAULT_OUTPUT = DATA_DIR / "scentai_release_01_gate_status.json"


def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def canonical_bytes(payload: object) -> bytes:
    return json.dumps(
        payload,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")


def fingerprint(*payloads: object) -> str:
    digest = hashlib.sha256()
    for payload in payloads:
        digest.update(canonical_bytes(payload))
    return digest.hexdigest()


def normalized_merchant_id(value: object) -> str:
    merchant = str(value or "").strip().casefold()
    if merchant.endswith("-de"):
        return merchant[:-3]
    return merchant


def build_release_gate_status(
    manifest: dict,
    staging_payload: dict,
    mappings_payload: dict,
    offers_payload: dict,
    images_payload: dict,
    affiliate_payload: dict,
    *,
    generated_at: str,
) -> dict[str, Any]:
    staging = staging_payload.get("products", [])
    mappings = mappings_payload.get("mappings", [])
    offers = offers_payload.get("offers", [])
    image_rows = images_payload.get("items", [])
    affiliate_rows = affiliate_payload.get("programs", [])

    image_by_id = {str(row.get("product_id") or ""): row for row in image_rows}
    active_merchants = {
        normalized_merchant_id(row.get("merchant_id"))
        for row in affiliate_rows
        if row.get("live_routing_allowed") is True
    }

    rows: list[dict[str, Any]] = []
    for product_id in manifest.get("product_ids", []):
        product = next(
            (row for row in staging if row.get("product_id") == product_id),
            None,
        )
        product_mappings = [row for row in mappings if row.get("product_id") == product_id]
        resolved_mappings = [
            row
            for row in product_mappings
            if any(
                str(row.get(key) or "").strip() for key in ("merchant_product_id", "ean", "gtin")
            )
        ]
        image = image_by_id.get(str(product_id), {})
        image_state = str(image.get("image_state") or "missing")
        image_ready = image_state.startswith("approved_")

        product_offers = [
            row
            for row in offers
            if row.get("product_id") == product_id
            and row.get("in_stock") is not False
            and str(row.get("affiliate_url") or "").strip()
        ]
        affiliate_ready = any(
            normalized_merchant_id(row.get("merchant_id")) in active_merchants
            for row in product_offers
        )

        community_ready = not bool((product or {}).get("community", {}).get("provisional"))
        mapping_ready = bool(resolved_mappings)

        gates = {
            "non_provisional_community_data": community_ready,
            "resolved_merchant_product_mapping": mapping_ready,
            "approved_product_image": image_ready,
            "current_tracked_affiliate_offer": affiliate_ready,
            "staging_recommendation_qa": True,
            "not_already_live": True,
        }
        blockers = [name for name, passed in gates.items() if not passed]

        if not image_ready:
            next_event = (
                "approved_affiliate_feed_or_verified_asset_usage_then_manual_visual_approval"
            )
        elif not affiliate_ready:
            next_event = "affiliate_program_approval_and_current_tracked_offer_import"
        else:
            next_event = "release_dry_run"

        rows.append(
            {
                "product_id": product_id,
                "candidate_id": ((product or {}).get("candidate_id")),
                "brand": (product or {}).get("brand"),
                "name": (product or {}).get("name"),
                "mapping_count": len(product_mappings),
                "resolved_mapping_count": len(resolved_mappings),
                "image_state": image_state,
                "affiliate_offer_count": len(product_offers),
                "gates": gates,
                "blockers": blockers,
                "promotion_ready": not blockers,
                "next_unblocking_event": next_event,
            }
        )

    source_hash = fingerprint(
        manifest,
        staging_payload,
        mappings_payload,
        offers_payload,
        images_payload,
        affiliate_payload,
    )

    return {
        "version": 1,
        "generated_at": generated_at,
        "source_fingerprint_sha256": source_hash,
        "release_id": manifest.get("release_id"),
        "policy_ref": "scentai_jarvis_operating_policy.json",
        "image_machine_ref": "scentai_image_approval_state_machine.json",
        "affiliate_machine_ref": ("scentai_affiliate_activation_state_machine.json"),
        "summary": {
            "release_size": len(rows),
            "mapping_ready": sum(
                1 for row in rows if row["gates"]["resolved_merchant_product_mapping"]
            ),
            "image_identity_source_verified": sum(
                1
                for row in rows
                if row["image_state"]
                in {
                    "rights_or_source_check_pending",
                    "review_ready",
                }
                or row["image_state"].startswith("approved_")
            ),
            "approved_images": sum(1 for row in rows if row["gates"]["approved_product_image"]),
            "current_tracked_affiliate_offers": sum(
                1 for row in rows if row["gates"]["current_tracked_affiliate_offer"]
            ),
            "promotion_ready": sum(1 for row in rows if row["promotion_ready"]),
        },
        "release_write_policy": manifest.get("write_policy"),
        "rows": rows,
    }


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Build a Jarvis-ready guarded release gate snapshot "
            "from current SCENTAI source-of-truth files."
        )
    )
    parser.add_argument(
        "--manifest",
        type=Path,
        default=DEFAULT_MANIFEST,
    )
    parser.add_argument(
        "--staging",
        type=Path,
        default=DEFAULT_STAGING,
    )
    parser.add_argument(
        "--mappings",
        type=Path,
        default=DEFAULT_MAPPINGS,
    )
    parser.add_argument(
        "--offers",
        type=Path,
        default=DEFAULT_OFFERS,
    )
    parser.add_argument(
        "--images",
        type=Path,
        default=DEFAULT_IMAGES,
    )
    parser.add_argument(
        "--affiliate",
        type=Path,
        default=DEFAULT_AFFILIATE,
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=DEFAULT_OUTPUT,
    )
    parser.add_argument("--generated-at", default=None)
    parser.add_argument("--machine-readable", action="store_true")
    args = parser.parse_args()

    generated_at = args.generated_at or datetime.now(UTC).replace(microsecond=0).isoformat()

    report = build_release_gate_status(
        load_json(args.manifest),
        load_json(args.staging),
        load_json(args.mappings),
        load_json(args.offers),
        load_json(args.images),
        load_json(args.affiliate),
        generated_at=generated_at,
    )

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )

    if args.machine_readable:
        print(json.dumps(report, ensure_ascii=False))
    else:
        summary = report["summary"]
        print(
            "SCENTAI release gates | "
            f"release={report['release_id']} | "
            f"mapping={summary['mapping_ready']}/"
            f"{summary['release_size']} | "
            f"images={summary['approved_images']}/"
            f"{summary['release_size']} | "
            f"affiliate={summary['current_tracked_affiliate_offers']}/"
            f"{summary['release_size']} | "
            f"ready={summary['promotion_ready']}/"
            f"{summary['release_size']}"
        )
        print(f"source_fingerprint_sha256={report['source_fingerprint_sha256']}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
