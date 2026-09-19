from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

DATA_DIR = Path("examples/retail/data")
DEFAULT_PROGRAMS = DATA_DIR / "scentai_affiliate_programs.json"
DEFAULT_MACHINE = DATA_DIR / "scentai_affiliate_activation_state_machine.json"


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
            }
        )

    for item in programs.get("other_networks", []):
        rows.append(
            {
                "network": item.get("network"),
                "program": item.get("program"),
                "merchant_id": item.get("merchant_id"),
                "application_status": item.get("status"),
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


def build_state_report(programs: dict) -> dict[str, Any]:
    rows = []
    for row in base_program_rows(programs):
        state, blockers = infer_state(row.get("application_status"))
        rows.append(
            {
                **row,
                "activation_state": state,
                "blockers": blockers,
                "live_routing_allowed": False,
                "next_action": (
                    "await_program_decision"
                    if state in {"applied", "pending_review"}
                    else "verify_credentials"
                    if state == "approved_credentials_pending"
                    else "none"
                ),
                "live_activation_action_class": "approval_required",
            }
        )

    return {
        "version": 1,
        "machine_id": "scentai_affiliate_activation_v1",
        "program_count": len(rows),
        "live_program_count": sum(
            1 for row in rows if row["live_routing_allowed"]
        ),
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

    report = build_state_report(load_json(args.programs))

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
