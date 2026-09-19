from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

DATA_DIR = Path("examples/retail/data")
DEFAULT_REGISTRY = DATA_DIR / "scentai_affiliate_programs.json"

ALLOWED_OBSERVED_STATUSES = {
    "approved",
    "rejected",
    "revoked",
}
ALLOWED_SOURCE_TYPES = {
    "network_dashboard",
    "network_email",
    "network_api",
}
FORBIDDEN_SECRET_KEYS = {
    "password",
    "passwd",
    "token",
    "access_token",
    "refresh_token",
    "api_key",
    "apikey",
    "secret",
    "client_secret",
    "private_feed_url",
    "credential",
    "credentials",
    "credential_value",
}
ALLOWED_CURRENT_STATUSES = {
    "applied",
    "applied_pending",
    "pending_review",
    "approved",
    "rejected",
    "revoked",
}


def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def _walk_forbidden_keys(
    value: object,
    *,
    path: str = "$",
) -> list[str]:
    issues: list[str] = []

    if isinstance(value, dict):
        for key, child in value.items():
            normalized = str(key).strip().casefold()
            child_path = f"{path}.{key}"
            if normalized in FORBIDDEN_SECRET_KEYS:
                issues.append(f"{child_path}: secret-bearing field is forbidden")
            issues.extend(
                _walk_forbidden_keys(
                    child,
                    path=child_path,
                )
            )
    elif isinstance(value, list):
        for index, child in enumerate(value):
            issues.extend(
                _walk_forbidden_keys(
                    child,
                    path=f"{path}[{index}]",
                )
            )

    return issues


def registry_programs(
    registry: dict,
) -> dict[tuple[str, str], dict[str, Any]]:
    rows: dict[tuple[str, str], dict[str, Any]] = {}
    default_network = str(registry.get("network") or "").strip()

    for item in registry.get("applications", []):
        merchant_id = str(item.get("merchant_id") or "").strip()
        rows[
            (
                default_network.casefold(),
                merchant_id.casefold(),
            )
        ] = {
            "network": default_network,
            "merchant_id": merchant_id,
            "program": item.get("program"),
            "status": item.get("status"),
        }

    for item in registry.get("other_networks", []):
        network = str(item.get("network") or "").strip()
        merchant_id = str(item.get("merchant_id") or "").strip()
        rows[
            (
                network.casefold(),
                merchant_id.casefold(),
            )
        ] = {
            "network": network,
            "merchant_id": merchant_id,
            "program": item.get("program"),
            "status": item.get("status"),
        }

    return rows


def activation_state_for_status(status: str) -> str:
    if status == "approved":
        return "approved_credentials_pending"
    if status == "rejected":
        return "rejected"
    if status == "revoked":
        return "revoked"
    raise ValueError(f"Unsupported observed status: {status}")


def validate_intake(
    intake: dict,
    registry: dict,
) -> dict[str, Any]:
    issues = _walk_forbidden_keys(intake)

    merchant_id = str(intake.get("merchant_id") or "").strip()
    network = str(intake.get("network") or "").strip()
    program = str(intake.get("program") or "").strip()
    observed_status = str(intake.get("observed_status") or "").strip().casefold()
    observed_at = str(intake.get("observed_at") or "").strip()

    if int(intake.get("version") or 0) != 1:
        issues.append("$.version: only version 1 is supported")
    if intake.get("intake_type") != "affiliate_program_decision":
        issues.append("$.intake_type: expected affiliate_program_decision")
    if not merchant_id:
        issues.append("$.merchant_id: required")
    if not network:
        issues.append("$.network: required")
    if not program:
        issues.append("$.program: required")
    if observed_status not in ALLOWED_OBSERVED_STATUSES:
        issues.append("$.observed_status: must be approved, rejected or revoked")
    if not observed_at:
        issues.append("$.observed_at: required")

    evidence = intake.get("evidence")
    if not isinstance(evidence, dict):
        issues.append("$.evidence: object required")
        evidence = {}

    source_type = str(evidence.get("source_type") or "").strip()
    if source_type not in ALLOWED_SOURCE_TYPES:
        issues.append("$.evidence.source_type: unsupported evidence source")

    integration = intake.get("integration_metadata")
    if not isinstance(integration, dict):
        issues.append("$.integration_metadata: object required")
        integration = {}

    if integration.get("credential_storage") != "external_secret_store_only":
        issues.append(
            "$.integration_metadata.credential_storage: must be external_secret_store_only"
        )

    programs = registry_programs(registry)
    registry_row = programs.get(
        (
            network.casefold(),
            merchant_id.casefold(),
        )
    )

    if registry_row is None:
        issues.append("registry: merchant/network pair is not registered")
        current_status = None
    else:
        current_status = str(registry_row.get("status") or "").strip().casefold()
        if current_status not in ALLOWED_CURRENT_STATUSES:
            issues.append(f"registry: unsupported current status {current_status!r}")
        if str(registry_row.get("program") or "").strip() != program:
            issues.append("registry: program name does not exactly match the registered program")

    transition_allowed = False
    if registry_row is not None and not issues:
        transition_allowed = (
            (
                current_status
                in {
                    "applied",
                    "applied_pending",
                    "pending_review",
                }
                and observed_status
                in {
                    "approved",
                    "rejected",
                }
            )
            or (
                current_status == "approved"
                and observed_status
                in {
                    "approved",
                    "revoked",
                }
            )
            or (current_status == observed_status)
        )

        if not transition_allowed:
            issues.append(
                f"transition: observed status is not valid from current status {current_status!r}"
            )

    valid = not issues

    next_action = None
    activation_state = None
    if valid:
        activation_state = activation_state_for_status(observed_status)
        if observed_status == "approved":
            next_action = "verify_credentials_in_external_secret_store"
        elif observed_status == "rejected":
            next_action = "record_rejection_and_stop_integration"
        else:
            next_action = "disable_routing_and_record_program_revocation"

    return {
        "valid": valid,
        "issues": issues,
        "merchant_id": merchant_id or None,
        "network": network or None,
        "program": program or None,
        "current_registry_status": current_status,
        "observed_status": observed_status or None,
        "transition_allowed": transition_allowed if valid else False,
        "activation_state_after_event": activation_state,
        "live_routing_allowed_after_event": False,
        "next_action": next_action,
        "write_action_class": "auto_allowed",
        "live_activation_action_class": "approval_required",
        "note": (
            "A valid approval intake may update program state only. "
            "It never enables live routing by itself."
        ),
    }


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Validate a non-secret SCENTAI affiliate program decision "
            "intake against the current affiliate registry."
        )
    )
    parser.add_argument("--intake", type=Path, required=True)
    parser.add_argument(
        "--registry",
        type=Path,
        default=DEFAULT_REGISTRY,
    )
    parser.add_argument("--output", type=Path, default=None)
    parser.add_argument("--machine-readable", action="store_true")
    args = parser.parse_args()

    try:
        report = validate_intake(
            load_json(args.intake),
            load_json(args.registry),
        )
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        parser.error(str(exc))

    if args.output is not None:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(
            json.dumps(report, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )

    if args.machine_readable:
        print(json.dumps(report, ensure_ascii=False))
    else:
        print(
            "SCENTAI affiliate approval intake | "
            f"valid={report['valid']} | "
            f"merchant={report['merchant_id']} | "
            f"current={report['current_registry_status']} | "
            f"observed={report['observed_status']} | "
            f"next={report['next_action']}"
        )
        for issue in report["issues"]:
            print(f"  - {issue}")

    return 0 if report["valid"] else 20


if __name__ == "__main__":
    raise SystemExit(main())
