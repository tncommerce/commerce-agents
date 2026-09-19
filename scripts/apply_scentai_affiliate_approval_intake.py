from __future__ import annotations

import argparse
import copy
import json
import re
from pathlib import Path
from typing import Any

from scripts.validate_scentai_affiliate_approval_intake import (
    load_json,
    validate_intake,
)

DATA_DIR = Path("examples/retail/data")
DEFAULT_REGISTRY = DATA_DIR / "scentai_affiliate_programs.json"
DEFAULT_EVENTS = DATA_DIR / "scentai_affiliate_program_events.json"


def _slug(value: str) -> str:
    normalized = re.sub(
        r"[^a-z0-9]+",
        "-",
        value.strip().casefold(),
    ).strip("-")
    return normalized or "unknown"


def _event_id(
    *,
    network: str,
    merchant_id: str,
    status: str,
    observed_at: str,
) -> str:
    return "-".join(
        [
            _slug(network),
            _slug(merchant_id),
            _slug(status),
            _slug(observed_at),
        ]
    )


def _update_registry_status(
    registry: dict,
    *,
    network: str,
    merchant_id: str,
    status: str,
) -> bool:
    default_network = str(registry.get("network") or "").strip()

    if default_network.casefold() == network.casefold():
        for item in registry.get("applications", []):
            if str(item.get("merchant_id") or "").strip().casefold() == merchant_id.casefold():
                changed = item.get("status") != status
                item["status"] = status
                return changed

    for item in registry.get("other_networks", []):
        if (
            str(item.get("network") or "").strip().casefold() == network.casefold()
            and str(item.get("merchant_id") or "").strip().casefold() == merchant_id.casefold()
        ):
            changed = item.get("status") != status
            item["status"] = status
            return changed

    raise ValueError("Validated merchant/network pair disappeared from registry")


def _latest_sequence(events_payload: dict) -> int:
    sequences = [int(event.get("sequence") or 0) for event in events_payload.get("events", [])]
    return max(sequences, default=0)


def _existing_event(
    events_payload: dict,
    event_id: str,
) -> dict | None:
    return next(
        (event for event in events_payload.get("events", []) if event.get("event_id") == event_id),
        None,
    )


def apply_intake(
    intake: dict,
    registry: dict,
    events_payload: dict,
) -> dict[str, Any]:
    validation = validate_intake(intake, registry)
    if not validation["valid"]:
        return {
            "valid": False,
            "applied": False,
            "changed": False,
            "validation": validation,
            "registry": registry,
            "events": events_payload,
            "live_routing_allowed": False,
        }

    network = str(intake["network"]).strip()
    merchant_id = str(intake["merchant_id"]).strip()
    program = str(intake["program"]).strip()
    status = str(intake["observed_status"]).strip().casefold()
    observed_at = str(intake["observed_at"]).strip()
    event_id = _event_id(
        network=network,
        merchant_id=merchant_id,
        status=status,
        observed_at=observed_at,
    )

    next_registry = copy.deepcopy(registry)
    next_events = copy.deepcopy(events_payload)
    next_events.setdefault("events", [])

    existing = _existing_event(next_events, event_id)
    current_status = validation["current_registry_status"]

    if existing is not None and current_status == status:
        return {
            "valid": True,
            "applied": True,
            "changed": False,
            "idempotent_noop": True,
            "event_id": event_id,
            "validation": validation,
            "registry": next_registry,
            "events": next_events,
            "live_routing_allowed": False,
            "next_action": validation["next_action"],
        }

    registry_changed = _update_registry_status(
        next_registry,
        network=network,
        merchant_id=merchant_id,
        status=status,
    )

    if existing is None:
        evidence = intake.get("evidence", {})
        next_events["events"].append(
            {
                "sequence": _latest_sequence(next_events) + 1,
                "event_id": event_id,
                "network": network,
                "merchant_id": merchant_id,
                "program": program,
                "event_type": (
                    "program_approved"
                    if status == "approved"
                    else "program_rejected"
                    if status == "rejected"
                    else "program_revoked"
                ),
                "event_at": observed_at,
                "recorded_at": observed_at,
                "status_after": status,
                "source": str(evidence.get("source_type") or "affiliate_approval_intake"),
                "external_program_id": evidence.get("external_program_id"),
                "reference_note": evidence.get("reference_note"),
            }
        )
        event_changed = True
    else:
        event_changed = False

    return {
        "valid": True,
        "applied": True,
        "changed": registry_changed or event_changed,
        "idempotent_noop": False,
        "event_id": event_id,
        "validation": validation,
        "registry": next_registry,
        "events": next_events,
        "live_routing_allowed": False,
        "next_action": validation["next_action"],
    }


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp_path = path.with_suffix(path.suffix + ".tmp")
    temp_path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    temp_path.replace(path)


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Safely apply a validated SCENTAI affiliate program decision "
            "to the current registry and append-only audit ledger. "
            "Dry-run is the default."
        )
    )
    parser.add_argument("--intake", type=Path, required=True)
    parser.add_argument(
        "--registry",
        type=Path,
        default=DEFAULT_REGISTRY,
    )
    parser.add_argument(
        "--events",
        type=Path,
        default=DEFAULT_EVENTS,
    )
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--machine-readable", action="store_true")
    args = parser.parse_args()

    try:
        result = apply_intake(
            load_json(args.intake),
            load_json(args.registry),
            load_json(args.events),
        )
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        parser.error(str(exc))

    if not result["valid"]:
        if args.machine_readable:
            print(json.dumps(result, ensure_ascii=False))
        else:
            print("SCENTAI affiliate intake apply | INVALID")
            for issue in result["validation"]["issues"]:
                print(f"  - {issue}")
        return 20

    wrote = False
    if args.write and result["changed"]:
        _write_json(args.events, result["events"])
        _write_json(args.registry, result["registry"])
        wrote = True

    output = {
        "valid": True,
        "dry_run": not args.write,
        "changed": result["changed"],
        "wrote": wrote,
        "idempotent_noop": result.get("idempotent_noop", False),
        "event_id": result["event_id"],
        "observed_status": result["validation"]["observed_status"],
        "activation_state_after_event": result["validation"]["activation_state_after_event"],
        "live_routing_allowed": False,
        "next_action": result["next_action"],
    }

    if args.machine_readable:
        print(json.dumps(output, ensure_ascii=False))
    else:
        print(
            "SCENTAI affiliate intake apply | "
            f"dry_run={output['dry_run']} | "
            f"changed={output['changed']} | "
            f"wrote={output['wrote']} | "
            f"status={output['observed_status']} | "
            f"activation={output['activation_state_after_event']} | "
            f"live={output['live_routing_allowed']} | "
            f"next={output['next_action']}"
        )

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
