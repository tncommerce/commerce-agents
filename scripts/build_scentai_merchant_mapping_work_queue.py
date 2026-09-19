from __future__ import annotations

import argparse
import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

DATA_DIR = Path("examples/retail/data")
DEFAULT_STAGING = DATA_DIR / "scentai_catalog_staging.json"
DEFAULT_MAPPINGS = DATA_DIR / "merchant_product_mappings.json"
DEFAULT_AFFILIATES = DATA_DIR / "scentai_affiliate_programs.json"
DEFAULT_OUTPUT = DATA_DIR / "scentai_merchant_mapping_work_queue.json"


def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def canonical_bytes(payload: dict) -> bytes:
    return json.dumps(
        payload,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")


def source_fingerprint(*payloads: dict) -> str:
    digest = hashlib.sha256()
    for payload in payloads:
        digest.update(canonical_bytes(payload))
    return digest.hexdigest()


def affiliate_program_index(payload: dict) -> tuple[dict[str, dict], list[dict]]:
    programs: dict[str, dict] = {}
    rows: list[dict] = []

    default_network = str(payload.get("network") or "").strip()
    for item in payload.get("applications", []):
        row = {
            "network": default_network,
            "merchant_id": item.get("merchant_id"),
            "program": item.get("program"),
            "status": item.get("status"),
        }
        rows.append(row)
        merchant_id = str(item.get("merchant_id") or "").strip()
        if merchant_id:
            programs[merchant_id] = {
                "network": default_network,
                "program": item.get("program"),
                "status": item.get("status"),
            }

    for item in payload.get("other_networks", []):
        row = {
            "network": item.get("network"),
            "merchant_id": item.get("merchant_id"),
            "program": item.get("program"),
            "status": item.get("status"),
        }
        rows.append(row)
        merchant_id = str(item.get("merchant_id") or "").strip()
        if merchant_id:
            programs[merchant_id] = {
                "network": item.get("network"),
                "program": item.get("program"),
                "status": item.get("status"),
            }

    return programs, rows


def build_queue(
    staging: dict,
    mappings_payload: dict,
    affiliate_payload: dict,
    *,
    generated_at: str,
) -> dict[str, Any]:
    mappings = mappings_payload.get("mappings", [])
    programs, affiliate_rows = affiliate_program_index(affiliate_payload)

    items: list[dict[str, Any]] = []
    for product in staging.get("products", []):
        product_id = str(product.get("product_id") or "").strip()
        product_mappings = [
            mapping for mapping in mappings if mapping.get("product_id") == product_id
        ]
        resolved = [
            mapping
            for mapping in product_mappings
            if any(
                str(mapping.get(key) or "").strip()
                for key in ("merchant_product_id", "ean", "gtin")
            )
        ]
        full = [
            mapping
            for mapping in product_mappings
            if str(mapping.get("merchant_product_id") or "").strip()
            and any(str(mapping.get(key) or "").strip() for key in ("ean", "gtin"))
        ]

        merchant_rows: list[dict[str, Any]] = []
        for mapping in product_mappings:
            merchant_id = str(mapping.get("merchant") or "").strip()
            program = programs.get(merchant_id)
            if not program:
                activation_state = "no_registered_program"
            elif program.get("status") == "approved":
                activation_state = "approved"
            else:
                activation_state = "pending_program_approval"

            merchant_rows.append(
                {
                    "merchant_id": merchant_id,
                    "mapping_state": (
                        "full"
                        if str(mapping.get("merchant_product_id") or "").strip()
                        and any(str(mapping.get(key) or "").strip() for key in ("ean", "gtin"))
                        else "partial"
                    ),
                    "merchant_product_id": mapping.get("merchant_product_id"),
                    "ean": mapping.get("ean"),
                    "gtin": mapping.get("gtin"),
                    "affiliate_program": program,
                    "affiliate_activation_state": activation_state,
                }
            )

        state = "mapping_data_ready_affiliate_blocked"
        next_action = "await_affiliate_program_approval"
        blockers: list[str] = []

        if not resolved:
            state = "mapping_required"
            next_action = "verify_exact_merchant_product_identity"
            blockers.append("no_resolved_merchant_mapping")

        if product_id == "SC-JPG-FLEUR-DU-MALE-2026-EDT-125":
            state = "research_blocked"
            next_action = "verify_current_retail_channel_before_mapping"
            blockers.extend(
                [
                    "verified_current_merchant_pending",
                    "community_performance_still_provisional",
                ]
            )

        community = product.get("community", {})
        if (
            community.get("provisional")
            and "community_performance_still_provisional" not in blockers
        ):
            blockers.append("community_performance_still_provisional")

        if resolved and not any(
            row["affiliate_activation_state"] == "approved" for row in merchant_rows
        ):
            blockers.append("affiliate_program_not_approved")

        items.append(
            {
                "product_id": product_id,
                "candidate_id": product.get("candidate_id"),
                "brand": product.get("brand"),
                "name": product.get("name"),
                "batch": product.get("batch"),
                "researched_merchant_count": int(
                    product.get("commerce", {}).get(
                        "merchant_coverage_count",
                        0,
                    )
                    or 0
                ),
                "mapping_count": len(product_mappings),
                "resolved_mapping_count": len(resolved),
                "full_mapping_count": len(full),
                "state": state,
                "blockers": blockers,
                "next_action": next_action,
                "action_class": "auto_allowed",
                "live_activation_action_class": "approval_required",
                "merchants": merchant_rows,
            }
        )

    state_weight = {
        "research_blocked": 0,
        "mapping_required": 1,
        "mapping_data_ready_affiliate_blocked": 2,
    }
    items.sort(
        key=lambda item: (
            state_weight.get(str(item["state"]), 99),
            str(item.get("brand") or "").casefold(),
            str(item.get("name") or "").casefold(),
        )
    )

    approved_programs = [row for row in affiliate_rows if row.get("status") == "approved"]

    return {
        "version": 1,
        "generated_at": generated_at,
        "source_fingerprint_sha256": source_fingerprint(
            staging,
            mappings_payload,
            affiliate_payload,
        ),
        "policy_ref": "scentai_jarvis_operating_policy.json",
        "source_files": [
            DEFAULT_STAGING.name,
            DEFAULT_MAPPINGS.name,
            DEFAULT_AFFILIATES.name,
        ],
        "summary": {
            "staged_products": len(items),
            "products_with_resolved_mapping": sum(
                1 for item in items if item["resolved_mapping_count"] > 0
            ),
            "products_with_two_or_more_resolved_mappings": sum(
                1 for item in items if item["resolved_mapping_count"] >= 2
            ),
            "products_without_resolved_mapping": sum(
                1 for item in items if item["resolved_mapping_count"] == 0
            ),
            "affiliate_programs_registered": len(affiliate_rows),
            "affiliate_programs_approved": len(approved_programs),
            "affiliate_programs_pending": (len(affiliate_rows) - len(approved_programs)),
            "live_activation_ready_products": sum(
                1
                for item in items
                if any(
                    merchant["affiliate_activation_state"] == "approved"
                    for merchant in item["merchants"]
                )
            ),
        },
        "affiliate_programs": affiliate_rows,
        "items": items,
    }


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Build the Jarvis-ready SCENTAI merchant mapping work queue "
            "from source-of-truth staging, mapping and affiliate files."
        )
    )
    parser.add_argument("--staging", type=Path, default=DEFAULT_STAGING)
    parser.add_argument("--mappings", type=Path, default=DEFAULT_MAPPINGS)
    parser.add_argument(
        "--affiliates",
        type=Path,
        default=DEFAULT_AFFILIATES,
    )
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument(
        "--generated-at",
        default=None,
        help=(
            "Optional ISO-8601 timestamp for reproducible committed output. "
            "Defaults to current UTC time."
        ),
    )
    parser.add_argument("--machine-readable", action="store_true")
    args = parser.parse_args()

    generated_at = args.generated_at or datetime.now(UTC).replace(microsecond=0).isoformat()

    queue = build_queue(
        load_json(args.staging),
        load_json(args.mappings),
        load_json(args.affiliates),
        generated_at=generated_at,
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
            "SCENTAI mapping work queue | "
            f"staged={summary['staged_products']} | "
            f"mapped={summary['products_with_resolved_mapping']} | "
            f"unmapped={summary['products_without_resolved_mapping']} | "
            f"affiliate_approved={summary['affiliate_programs_approved']} | "
            f"activation_ready={summary['live_activation_ready_products']}"
        )
        print(f"source_fingerprint_sha256={queue['source_fingerprint_sha256']}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
