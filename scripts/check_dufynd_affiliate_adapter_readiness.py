from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from scripts.validate_scentai_provider_config import (
    load_json,
    validate_provider_config,
)

DEFAULT_PROGRAMS = Path("examples/retail/data/scentai_affiliate_programs.json")
DEFAULT_PARTNERS = Path("examples/retail/data/merchant_partners.json")

APPROVED_STATUSES = {
    "approved",
    "active",
    "tracking_ready",
}
PENDING_STATUSES = {
    "applied",
    "applied_pending",
    "pending",
}


def _network_by_merchant(programs: dict) -> dict[str, dict[str, Any]]:
    rows: list[dict[str, Any]] = []

    primary_network = str(programs.get("network") or "").strip()
    for row in programs.get("applications", []):
        rows.append(
            {
                **row,
                "network": primary_network,
            }
        )

    for row in programs.get("other_networks", []):
        rows.append(dict(row))

    return {
        str(row.get("merchant_id") or "").strip(): row
        for row in rows
        if str(row.get("merchant_id") or "").strip()
    }


def evaluate_adapter_readiness(
    config: dict,
    programs: dict,
    partners: dict,
) -> dict[str, Any]:
    contract = validate_provider_config(config)
    issues = list(contract["issues"])

    constants = config.get("constants") or {}
    merchant_id = str(constants.get("merchant_id") or "").strip()
    network = str(constants.get("network") or "").strip()

    partner_by_id = {
        str(row.get("merchant_id") or "").strip(): row
        for row in partners.get("partners", [])
        if str(row.get("merchant_id") or "").strip()
    }
    application_by_id = _network_by_merchant(programs)

    partner = partner_by_id.get(merchant_id)
    application = application_by_id.get(merchant_id)

    if merchant_id and partner is None:
        issues.append("merchant_missing_from_partner_registry")

    if merchant_id and application is None:
        issues.append("merchant_missing_from_affiliate_program_registry")

    expected_network = (
        str(application.get("network") or "").strip()
        if application
        else ""
    )
    if (
        expected_network
        and network
        and expected_network.casefold() != network.casefold()
    ):
        issues.append(
            "affiliate_network_mismatch:"
            f"expected={expected_network},configured={network}"
        )

    application_status = (
        str(application.get("status") or "").strip()
        if application
        else None
    )

    if not contract["valid"] or any(
        issue.startswith(
            (
                "merchant_missing_",
                "affiliate_network_mismatch:",
            )
        )
        for issue in issues
    ):
        state = "BLOCKED"
        next_action = "fix_provider_or_registry_contract"
    elif application_status in PENDING_STATUSES:
        state = "WAITING_APPROVAL"
        next_action = "await_affiliate_program_approval"
    elif application_status in APPROVED_STATUSES:
        state = "READY_FOR_FEED_PREFLIGHT"
        next_action = "run_real_feed_preflight"
    else:
        state = "REVIEW"
        next_action = "verify_affiliate_program_status"

    return {
        "state": state,
        "provider_name": contract["provider_name"],
        "merchant_id": merchant_id or None,
        "network": network or None,
        "expected_network": expected_network or None,
        "application_status": application_status,
        "partner_status": partner.get("status") if partner else None,
        "provider_contract_valid": contract["valid"],
        "promotion_asset_contract_ready": contract[
            "promotion_asset_contract_ready"
        ],
        "issues": sorted(set(issues)),
        "next_action": next_action,
    }


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Check a DUFYND affiliate feed adapter against the known "
            "merchant and affiliate-program registries."
        )
    )
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument(
        "--programs",
        type=Path,
        default=DEFAULT_PROGRAMS,
    )
    parser.add_argument(
        "--partners",
        type=Path,
        default=DEFAULT_PARTNERS,
    )
    parser.add_argument(
        "--machine-readable",
        action="store_true",
    )
    args = parser.parse_args()

    try:
        report = evaluate_adapter_readiness(
            load_json(args.config),
            load_json(args.programs),
            load_json(args.partners),
        )
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        parser.error(str(exc))

    if args.machine_readable:
        print(json.dumps(report, ensure_ascii=False))
    else:
        print(
            "DUFYND affiliate adapter | "
            f"state={report['state']} | "
            f"merchant={report['merchant_id']} | "
            f"network={report['network']} | "
            f"next={report['next_action']}"
        )
        for issue in report["issues"]:
            print(f"  - {issue}")

    return 20 if report["state"] == "BLOCKED" else 0


if __name__ == "__main__":
    raise SystemExit(main())
