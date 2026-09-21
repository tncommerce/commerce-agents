from __future__ import annotations

import argparse
import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

DATA_DIR = Path("examples/retail/data")
DEFAULT_RELEASE = DATA_DIR / "scentai_release_batch_01.json"
DEFAULT_MAPPINGS = DATA_DIR / "merchant_product_mappings.json"
DEFAULT_AFFILIATES = DATA_DIR / "scentai_affiliate_programs.json"
DEFAULT_VARIANT_AUDIT = DATA_DIR / "dufynd_perfumetrader_release01_variant_audit.json"
DEFAULT_OUTPUT = DATA_DIR / "scentai_release_01_feed_activation_queue.json"


def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def canonical_bytes(payload: object) -> bytes:
    return json.dumps(
        payload,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")


def source_fingerprint(*payloads: object) -> str:
    digest = hashlib.sha256()
    for payload in payloads:
        digest.update(canonical_bytes(payload))
    return digest.hexdigest()


def affiliate_program_rows(payload: dict) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    default_network = str(payload.get("network") or "").strip()

    for item in payload.get("applications", []):
        rows.append(
            {
                "network": default_network,
                "merchant_id": item.get("merchant_id"),
                "program": item.get("program"),
                "application_status": item.get("status"),
            }
        )

    for item in payload.get("other_networks", []):
        rows.append(
            {
                "network": item.get("network"),
                "merchant_id": item.get("merchant_id"),
                "program": item.get("program"),
                "application_status": item.get("status"),
            }
        )

    return rows


def build_feed_activation_queue(
    release: dict,
    mappings_payload: dict,
    affiliates: dict,
    *,
    generated_at: str,
    variant_audit: dict | None = None,
) -> dict[str, Any]:
    release_ids = list(dict.fromkeys(release.get("product_ids", [])))
    release_set = set(release_ids)
    mappings = mappings_payload.get("mappings", [])
    audit_payload = variant_audit or {}
    audit_merchant = str(audit_payload.get("merchant_id") or "").strip().casefold()
    audit_release = str(audit_payload.get("release_id") or "").strip()
    audit_rows = {
        str(row.get("product_id") or "").strip(): row
        for row in audit_payload.get("rows", [])
        if str(row.get("product_id") or "").strip() in release_set
    }

    programs: list[dict[str, Any]] = []
    for program in affiliate_program_rows(affiliates):
        merchant_id = str(program.get("merchant_id") or "").strip()
        merchant_key = merchant_id.casefold()

        mapped_product_ids = [
            product_id
            for product_id in release_ids
            if any(
                mapping.get("product_id") == product_id
                and str(mapping.get("merchant") or "").strip().casefold() == merchant_key
                and any(
                    str(mapping.get(key) or "").strip()
                    for key in (
                        "merchant_product_id",
                        "ean",
                        "gtin",
                    )
                )
                for mapping in mappings
            )
        ]

        mapped_count = len(mapped_product_ids)
        full_coverage = bool(release_set) and mapped_count == len(release_set)
        approved = str(program.get("application_status") or "").strip().casefold() == "approved"
        missing_product_ids = [
            product_id for product_id in release_ids if product_id not in mapped_product_ids
        ]
        audit_applies = (
            merchant_key == audit_merchant
            and str(release.get("release_id") or "").strip() == audit_release
        )
        audited_missing_product_ids = [
            product_id
            for product_id in missing_product_ids
            if product_id in audit_rows and audit_rows[product_id].get("mapping_eligible") is False
        ]
        verified_unmapped_product_ids = [
            product_id
            for product_id in missing_product_ids
            if product_id in audit_rows and audit_rows[product_id].get("mapping_eligible") is True
        ]
        missing_mapping_audit_complete = bool(audit_applies) and set(
            audited_missing_product_ids
        ) == set(missing_product_ids)

        if approved and full_coverage:
            state = "approved_mapping_ready_feed_sample_pending"
            next_action = "obtain_real_feed_sample_and_create_provider_config"
        elif approved:
            state = "approved_mapping_partial"
            next_action = (
                "await_exact_variant_feed_or_product_evidence"
                if missing_mapping_audit_complete
                else "resolve_remaining_release_mappings_before_feed_validation"
            )
        elif full_coverage:
            state = "program_pending_full_mapping_ready"
            next_action = "await_program_decision"
        else:
            state = "program_pending_mapping_partial"
            next_action = "await_program_decision"

        program_row: dict[str, Any] = {
            **program,
            "mapped_release_product_count": mapped_count,
            "release_size": len(release_ids),
            "mapped_product_ids": mapped_product_ids,
            "full_release_mapping_coverage": full_coverage,
            "program_approved": approved,
            "state": state,
            "feed_state": (
                "await_real_feed_or_tracked_link_sample"
                if approved and full_coverage
                else (
                    "await_exact_variant_feed_or_product_evidence"
                    if approved and missing_mapping_audit_complete
                    else (
                        "await_remaining_mapping_resolution"
                        if approved
                        else "await_program_approval"
                    )
                )
            ),
            "provider_config_state": ("not_configured_until_real_feed_sample"),
            "dry_run_state": "not_run",
            "image_candidate_state": "not_extracted",
            "live_routing_allowed": False,
            "next_action": next_action,
            "action_class": "auto_allowed",
            "live_activation_action_class": "approval_required",
        }
        if audit_applies:
            program_row["variant_audit"] = {
                "checked_at": audit_payload.get("checked_at"),
                "scope": audit_payload.get("scope"),
                "audited_release_product_count": len(audit_rows),
                "exact_variant_verified_product_count": sum(
                    row.get("audit_state") == "exact_variant_verified"
                    for row in audit_rows.values()
                ),
                "missing_mapping_product_ids": missing_product_ids,
                "audited_missing_mapping_product_ids": audited_missing_product_ids,
                "verified_unmapped_product_ids": verified_unmapped_product_ids,
                "missing_mapping_audit_complete": missing_mapping_audit_complete,
                "missing_mapping_states": {
                    product_id: audit_rows[product_id].get("audit_state")
                    for product_id in audited_missing_product_ids
                },
            }
        programs.append(program_row)

    programs.sort(
        key=lambda row: (
            -int(bool(row["full_release_mapping_coverage"])),
            -int(row["mapped_release_product_count"]),
            str(row.get("merchant_id") or "").casefold(),
        )
    )

    approved_full = [
        row for row in programs if row["program_approved"] and row["full_release_mapping_coverage"]
    ]

    return {
        "version": 1,
        "generated_at": generated_at,
        "source_fingerprint_sha256": source_fingerprint(
            release,
            mappings_payload,
            affiliates,
            audit_payload,
        ),
        "release_id": release.get("release_id"),
        "purpose": (
            "Jarvis-ready affiliate/feed activation queue. "
            "Operational integration coverage only; never use commission "
            "to rank fragrances or customer-facing merchant offers."
        ),
        "policy_ref": "scentai_jarvis_operating_policy.json",
        "activation_machine_ref": ("scentai_affiliate_activation_state_machine.json"),
        "feed_checker_ref": "scripts/check_scentai_release_feed.py",
        "summary": {
            "registered_programs": len(programs),
            "programs_with_any_release_mapping": sum(
                1 for row in programs if row["mapped_release_product_count"] > 0
            ),
            "programs_with_full_release_mapping": sum(
                1 for row in programs if row["full_release_mapping_coverage"]
            ),
            "approved_programs": sum(1 for row in programs if row["program_approved"]),
            "approved_programs_with_full_release_mapping": len(approved_full),
            "feed_validation_path_available": bool(approved_full),
            "live_activation_ready": False,
        },
        "operational_note": (
            "Full mapping coverage can make a merchant a complete "
            "feed-validation path after program approval. It never makes "
            "the merchant live by itself; real feed validation, tracked "
            "offers, image review, quality gates and explicit user approval "
            "remain required."
        ),
        "programs": programs,
    }


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Build the Jarvis-ready SCENTAI Release 01 affiliate/feed "
            "activation queue from current source-of-truth files."
        )
    )
    parser.add_argument(
        "--release",
        type=Path,
        default=DEFAULT_RELEASE,
    )
    parser.add_argument(
        "--mappings",
        type=Path,
        default=DEFAULT_MAPPINGS,
    )
    parser.add_argument(
        "--affiliates",
        type=Path,
        default=DEFAULT_AFFILIATES,
    )
    parser.add_argument(
        "--variant-audit",
        type=Path,
        default=DEFAULT_VARIANT_AUDIT,
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

    variant_audit = load_json(args.variant_audit) if args.variant_audit.exists() else {}
    queue = build_feed_activation_queue(
        load_json(args.release),
        load_json(args.mappings),
        load_json(args.affiliates),
        generated_at=generated_at,
        variant_audit=variant_audit,
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
            "SCENTAI Release 01 feed activation | "
            f"programs={summary['registered_programs']} | "
            f"full_mapping_paths="
            f"{summary['programs_with_full_release_mapping']} | "
            f"approved_full_paths="
            f"{summary['approved_programs_with_full_release_mapping']} | "
            f"feed_validation_path="
            f"{summary['feed_validation_path_available']} | "
            f"live_ready={summary['live_activation_ready']}"
        )
        print(f"source_fingerprint_sha256={queue['source_fingerprint_sha256']}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
