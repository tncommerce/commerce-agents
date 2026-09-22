from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

DATA_DIR = Path("examples/retail/data")
DEFAULT_PROGRAMS = DATA_DIR / "scentai_affiliate_programs.json"
DEFAULT_MACHINE = DATA_DIR / "scentai_affiliate_activation_state_machine.json"
DEFAULT_PARTNERS = DATA_DIR / "merchant_partners.json"


def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def normalize_application_status(value: object) -> str:
    return str(value or "").strip().casefold()


def base_program_rows(programs: dict) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    default_network = str(programs.get("network") or "").strip()

    for item in programs.get("applications", []):
        rows.append(
            {
                "network": default_network,
                "program": item.get("program"),
                "merchant_id": item.get("merchant_id"),
                "application_status": item.get("status"),
                "tracking_strategy": item.get("tracking_strategy"),
            }
        )

    for item in programs.get("other_networks", []):
        rows.append(
            {
                "network": item.get("network"),
                "program": item.get("program"),
                "merchant_id": item.get("merchant_id"),
                "application_status": item.get("status"),
                "tracking_strategy": item.get("tracking_strategy"),
            }
        )

    return rows


def infer_state(application_status: object) -> tuple[str, list[str]]:
    status = normalize_application_status(application_status)

    if status in {"rejected", "declined"}:
        return "rejected", ["affiliate_program_rejected"]
    if status in {"revoked", "terminated"}:
        return "revoked", ["affiliate_program_revoked"]
    if status == "approved":
        return (
            "approved_credentials_pending",
            [
                "credentials_not_verified_in_repo_state",
                "integration_strategy_not_verified",
                "dry_run_not_recorded",
                "user_approval_not_recorded",
            ],
        )
    if status in {"applied_pending", "pending", "pending_review"}:
        return "pending_review", ["affiliate_program_approval_pending"]
    if status in {"applied", "application_submitted"}:
        return "applied", ["affiliate_program_approval_pending"]

    return "not_registered", ["affiliate_program_not_registered"]


def active_partner_index(partners: dict | None) -> dict[str, dict[str, Any]]:
    index: dict[str, dict[str, Any]] = {}
    for item in (partners or {}).get("partners", []):
        merchant_id = str(item.get("merchant_id") or "").strip()
        affiliate_url = str(item.get("affiliate_url") or "").strip()
        verified_at = str(item.get("last_verified_at") or "").strip()
        status = str(item.get("status") or "").strip().casefold()
        if (
            merchant_id
            and status == "active"
            and affiliate_url.startswith(("https://", "http://"))
            and verified_at
        ):
            index[merchant_id] = item
    return index


def build_state_report(
    programs: dict,
    *,
    generated_at: str | None = None,
    merchant_partners: dict | None = None,
) -> dict[str, Any]:
    rows = []
    active_partners = active_partner_index(merchant_partners)

    for row in base_program_rows(programs):
        state, blockers = infer_state(row.get("application_status"))
        merchant_id = str(row.get("merchant_id") or "").strip()
        partner = active_partners.get(merchant_id)
        tracking_strategy = str(row.get("tracking_strategy") or "").strip()
        merchant_homepage_tracking_active = (
            normalize_application_status(row.get("application_status")) == "approved"
            and tracking_strategy.startswith("verified_")
            and partner is not None
        )

        if merchant_homepage_tracking_active:
            state = "active"
            blockers = []
            live_routing_allowed = True
            next_action = "maintain_partner_health"
            routing_scope = "merchant_homepage_only"
        else:
            live_routing_allowed = False
            next_action = (
                "await_program_decision"
                if state in {"applied", "pending_review"}
                else "verify_credentials"
                if state == "approved_credentials_pending"
                else "none"
            )
            routing_scope = "none"

        rows.append(
            {
                **row,
                "activation_state": state,
                "blockers": blockers,
                "live_routing_allowed": live_routing_allowed,
                "routing_scope": routing_scope,
                "merchant_homepage_tracking_active": merchant_homepage_tracking_active,
                "product_offer_activation_independent": True,
                "next_action": next_action,
                "live_activation_action_class": "approval_required",
            }
        )

    live_program_count = sum(1 for row in rows if row["live_routing_allowed"])
    approved_program_count = sum(
        1
        for row in rows
        if normalize_application_status(row.get("application_status")) == "approved"
    )
    ready_for_user_approval = sum(
        1 for row in rows if row["activation_state"] == "ready_for_user_approval"
    )
    rejected_program_count = sum(1 for row in rows if row["activation_state"] == "rejected")
    pending_program_count = sum(
        1
        for row in rows
        if row["activation_state"]
        in {
            "applied",
            "pending_review",
            "approved_credentials_pending",
            "ready_for_user_approval",
        }
    )

    return {
        "version": 2,
        "generated_at": generated_at,
        "machine_id": "scentai_affiliate_activation_v1",
        "scope_note": (
            "Program activation can describe a verified merchant-level homepage tracking route. "
            "Product-specific tracked offers remain independently gated by exact SKU mapping, "
            "stock, feed validation, image rights and release quality gates."
        ),
        "summary": {
            "programs": len(rows),
            "approved": approved_program_count,
            "active": live_program_count,
            "pending": pending_program_count,
            "rejected": rejected_program_count,
            "ready_for_user_approval": ready_for_user_approval,
            "merchant_homepage_tracking_active": sum(
                1 for row in rows if row["merchant_homepage_tracking_active"]
            ),
        },
        "program_count": len(rows),
        "live_program_count": live_program_count,
        "programs": rows,
    }


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Evaluate SCENTAI affiliate application records against the "
            "Jarvis-safe activation lifecycle."
        )
    )
    parser.add_argument(
        "--programs",
        type=Path,
        default=DEFAULT_PROGRAMS,
    )
    parser.add_argument(
        "--machine",
        type=Path,
        default=DEFAULT_MACHINE,
    )
    parser.add_argument(
        "--partners",
        type=Path,
        default=DEFAULT_PARTNERS,
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=None,
    )
    parser.add_argument(
        "--machine-readable",
        action="store_true",
    )
    args = parser.parse_args()

    machine = load_json(args.machine)
    if machine.get("machine_id") != "scentai_affiliate_activation_v1":
        parser.error("Unsupported affiliate activation state machine")

    report = build_state_report(
        load_json(args.programs),
        merchant_partners=(load_json(args.partners) if args.partners.exists() else None),
    )

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
            "SCENTAI affiliate activation | "
            f"programs={report['program_count']} | "
            f"live={report['live_program_count']}"
        )
        for row in report["programs"]:
            print(
                f"  {row['merchant_id']} | "
                f"{row['application_status']} -> "
                f"{row['activation_state']} | "
                f"next={row['next_action']}"
            )

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
