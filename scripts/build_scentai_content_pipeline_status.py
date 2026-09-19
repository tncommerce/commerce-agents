.py>>>
from __future__ import annotations

from collections import defaultdict
from typing import Any
from urllib.parse import urlparse

from .merchant_feed_assets import extract_feed_image_candidates
from .merchant_feed_preflight import build_feed_preflight
from .merchant_import import (
    MerchantProductMapping,
    import_feed_rows,
)
from .merchant_provider_contract import validate_provider_contract_rows


def _valid_http_url(value: object) -> bool:
    if not isinstance(value, str) or not value.strip():
        return False

    parsed = urlparse(value.strip())
    return parsed.scheme in {"http", "https"} and bool(parsed.netloc)


def build_release_feed_readiness(
    release_product_ids: list[str],
    rows: list[dict],
    mappings: list[MerchantProductMapping],
) -> dict[str, Any]:
    release_ids = list(dict.fromkeys(release_product_ids))
    release_set = set(release_ids)

    preflight = build_feed_preflight(rows)
    contract = validate_provider_contract_rows(rows)
    imported = import_feed_rows(contract.rows, mappings)
    images = extract_feed_image_candidates(rows, mappings)

    offers_by_product: dict[str, list] = defaultdict(list)
    for offer in imported.offers:
        if offer.product_id in release_set:
            offers_by_product[offer.product_id].append(offer)

    images_by_product: dict[str, list[dict]] = defaultdict(list)
    for candidate in images["cand
…[43132 chars truncated — re-run with head/grep/tail for full output]…
EFAULT_ASSET_CANDIDATES = DATA_DIR / "scentai_image_asset_candidates.json"
DEFAULT_RELEASES = [
    DATA_DIR / "scentai_release_batch_01.json",
    DATA_DIR / "scentai_release_batch_02.json",
    DATA_DIR / "scentai_release_batch_03.json",
]
APPROVED_IMAGE_STATES = {
    "approved_feed_image",
    "approved_manufacturer_image",
    "approved_licensed_image",
}


def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def canonical_bytes(payload: object) -> bytes:
    return json.dumps(
        payload,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")


def source_fingerprint(
    staging: dict,
    releases: list[dict],
    asset_candidates: dict | None = None,
) -> str:
    digest = hashlib.sha256()
    digest.update(canonical_bytes(staging))
    for release in releases:
        digest.update(canonical_bytes(release))
    if asset_candidates is not None:
        digest.update(canonical_bytes(asset_candidates))
    return digest.hexdigest()


def build_release_index(
    releases: list[dict],
) -> dict[str, dict[str, Any]]:
    index: dict[str, dict[str, Any]] = {}

    for release_order, release in enumerate(releases, start=1):
        release_id = str(release.get("release_id") or "").strip()
        for position, product_id in enumerate(
            release.get("product_ids", []),
            start=1,
        ):
            index[str(product_id)] = {
                "release_id": release_id,
                "release_order": release_order,
                "position": position,
                "write_enabled": bool(release.get("write_enabled")),
            }

    return index


def build_queue(
    staging: dict,
    releases: list[dict],
    *,
    generated_at: str,
    asset_candidates: dict | None = None,
) -> dict[str, Any]:
    release_index = build_release_index(releases)
    candidate_by_product = {
        str(row.get("product_id") or ""): row
        for row in (asset_candidates or {}).get("products", [])
        if str(row.get("product_id") or "").strip()
    }
    items: list[dict[str, Any]] = []

    for product in staging.get("products", []):
        product_id = str(product.get("product_id") or "").strip()
        media = product.get("media", {})
        image_status = str(media.get("image_status") or "").strip()
        image_url = str(media.get("image_url") or "").strip() or None
        approved = image_status in APPROVED_IMAGE_STATES and image_url is not None

        candidate = candidate_by_product.get(product_id)

        if approved:
            image_state = image_status
            blockers: list[str] = []
            next_action = "none"
        elif candidate is not None:
            image_state = str(candidate.get("image_state") or "rights_or_source_check_pending")
            if image_state == "identity_check_pending":
                blockers = [
                    "approved_product_image_missing",
                    "exact_variant_identity_not_verified",
                ]
            elif image_state == "review_ready":
                blockers = [
                    "approved_product_image_missing",
                    "manual_visual_approval_pending",
                ]
            else:
                blockers = [
                    "approved_product_image_missing",
                    "asset_usage_or_feed_rights_not_verified",
                ]
            next_action = str(
                candidate.get("next_action")
                or ("prefer_approved_affiliate_feed_image_else_verify_manufacturer_asset_usage")
            )
        else:
            image_state = "missing"
            blockers = ["approved_product_image_missing"]
            next_action = "await_real_feed_or_official_asset_candidate"

        row: dict[str, Any] = {
            "product_id": product_id,
            "candidate_id": product.get("candidate_id"),
            "brand": product.get("brand"),
            "name": product.get("name"),
            "batch": product.get("batch"),
            "release": release_index.get(product_id),
            "current_image_url": image_url,
            "current_image_status": image_status or "missing",
            "image_state": image_state,
            "blockers": blockers,
            "next_action": next_action,
            "action_class": "auto_allowed",
            "approval_action_class": "approval_required",
        }

        if candidate is not None and not approved:
            row["candidate_source"] = candidate.get("candidate_source")
            verified_at = candidate.get(
                "candidate_source",
                {},
            ).get("verified_at")
            audit_trail = [
                {
                    "at": verified_at,
                    "from": "missing",
                    "to": "candidate_discovered",
                    "trigger": "manufacturer_source_found",
                },
                {
                    "at": verified_at,
                    "from": "candidate_discovered",
                    "to": "identity_check_pending",
                    "trigger": "candidate_normalized",
                },
            ]
            if image_state in {
                "rights_or_source_check_pending",
                "review_ready",
            }:
                audit_trail.extend(
                    [
                        {
                            "at": verified_at,
                            "from": "identity_check_pending",
                            "to": "identity_verified",
                            "trigger": "exact_variant_verified",
                        },
                        {
                            "at": verified_at,
                            "from": "identity_verified",
                            "to": "rights_or_source_check_pending",
                            "trigger": "identity_gate_passed",
                        },
                    ]
                )
            if image_state == "review_ready":
                audit_trail.append(
                    {
                        "at": verified_at,
                        "from": "rights_or_source_check_pending",
                        "to": "review_ready",
                        "trigger": "approved_source_class_verified",
                    }
                )
            row["audit_trail"] = audit_trail

        items.append(row)

    items.sort(
        key=lambda item: (
            (item["release"]["release_order"] if item["release"] else 99),
            (item["release"]["position"] if item["release"] else 999),
            str(item.get("brand") or "").casefold(),
            str(item.get("name") or "").casefold(),
        )
    )

    return {
        "version": 1,
        "generated_at": generated_at,
        "source_fingerprint_sha256": source_fingerprint(
            staging,
            releases,
            asset_candidates,
        ),
        "machine_id": "scentai_image_approval_v1",
        "policy_ref": "scentai_jarvis_operating_policy.json",
        "source_files": [
            DEFAULT_STAGING.name,
            *[path.name for path in DEFAULT_RELEASES],
            *([DEFAULT_ASSET_CANDIDATES.name] if asset_candidates is not None else []),
        ],
        "summary": {
            "staged_products": len(items),
            "release_01_products": sum(
                1
                for item in items
                if item.get("release", {}).get("release_id") == "SCENTAI-RELEASE-01"
                if item.get("release")
            ),
            "release_02_products": sum(
                1
                for item in items
                if item.get("release", {}).get("release_id") == "SCENTAI-RELEASE-02"
                if item.get("release")
            ),
            "release_03_products": sum(
                1
                for item in items
                if item.get("release", {}).get("release_id") == "SCENTAI-RELEASE-03"
                if item.get("release")
            ),
            "approved_images": sum(
                1 for item in items if str(item["image_state"]).startswith("approved_")
            ),
            "pending_images": sum(
                1 for item in items if not str(item["image_state"]).startswith("approved_")
            ),
            "review_ready": sum(1 for item in items if item["image_state"] == "review_ready"),
            "rights_or_source_check_pending": sum(
                1 for item in items if item["image_state"] == "rights_or_source_check_pending"
            ),
            "identity_check_pending": sum(
                1 for item in items if item["image_state"] == "identity_check_pending"
            ),
        },
        "items": items,
    }


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Build the Jarvis-ready SCENTAI image approval work queue "
            "from staging and guarded release manifests."
        )
    )
    parser.add_argument(
        "--staging",
        type=Path,
        default=DEFAULT_STAGING,
    )
    parser.add_argument(
        "--release",
        action="append",
        type=Path,
        default=None,
        help="Optional release manifest. Repeatable.",
    )
    parser.add_argument(
        "--asset-candidates",
        type=Path,
        default=DEFAULT_ASSET_CANDIDATES,
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=DEFAULT_OUTPUT,
    )
    parser.add_argument(
        "--generated-at",
        default=None,
    )
    parser.add_argument(
        "--machine-readable",
        action="store_true",
    )
    args = parser.parse_args()

    release_paths = args.release or DEFAULT_RELEASES
    staging = load_json(args.staging)
    releases = [load_json(path) for path in release_paths]
    asset_candidates = load_json(args.asset_candidates) if args.asset_candidates.exists() else None
    generated_at = args.generated_at or datetime.now(UTC).replace(microsecond=0).isoformat()

    queue = build_queue(
        staging,
        releases,
        generated_at=generated_at,
        asset_candidates=asset_candidates,
    )

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(queue, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )

    if args.machine_readable:
        print(json.dumps(queue, ensure_ascii=False))
    else:
        summary = queue["summary"]
        print(
            "SCENTAI image queue | "
            f"staged={summary['staged_products']} | "
            f"approved={summary['approved_images']} | "
            f"pending={summary['pending_images']} | "
            f"review_ready={summary['review_ready']}"
        )
        print(f"source_fingerprint_sha256={queue['source_fingerprint_sha256']}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
