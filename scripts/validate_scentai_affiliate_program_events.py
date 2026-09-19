from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

DATA_DIR = Path("examples/retail/data")
DEFAULT_EVENTS = DATA_DIR / "scentai_affiliate_program_events.json"
DEFAULT_REGISTRY = DATA_DIR / "scentai_affiliate_programs.json"

ALLOWED_STATUSES = {
    "applied",
    "applied_pending",
    "pending_review",
    "approved",
    "rejected",
    "revoked",
}


def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def derive_current_statuses(events_payload: dict) -> dict[tuple[str, str], dict[str, Any]]:
    events = events_payload.get("events", [])
    if not isinstance(events, list):
        raise ValueError("events must be a list")

    seen_event_ids: set[str] = set()
    seen_sequences: set[int] = set()
    latest: dict[tuple[str, str], dict[str, Any]] = {}

    for event in events:
        event_id = str(event.get("event_id") or "").strip()
        network = str(event.get("network") or "").strip()
        merchant_id = str(event.get("merchant_id") or "").strip()
        status_after = str(event.get("status_after") or "").strip()
        sequence = event.get("sequence")

        if not event_id:
            raise ValueError("affiliate event requires event_id")
        if event_id in seen_event_ids:
            raise ValueError(f"duplicate affiliate event_id: {event_id}")
        seen_event_ids.add(event_id)

        if not isinstance(sequence, int) or sequence < 1:
            raise ValueError(f"{event_id}: sequence must be a positive integer")
        if sequence in seen_sequences:
            raise ValueError(f"duplicate affiliate event sequence: {sequence}")
        seen_sequences.add(sequence)

        if not network or not merchant_id:
            raise ValueError(f"{event_id}: network and merchant_id are required")
        if status_after not in ALLOWED_STATUSES:
            raise ValueError(
                f"{event_id}: unsupported status_after {status_after!r}"
            )

        key = (network.casefold(), merchant_id.casefold())
        current = latest.get(key)
        if current is None or sequence > int(current["sequence"]):
            latest[key] = event

    return latest


def registry_statuses(registry: dict) -> dict[tuple[str, str], str]:
    rows: dict[tuple[str, str], str] = {}
    default_network = str(registry.get("network") or "").strip()

    for item in registry.get("applications", []):
        key = (
            default_network.casefold(),
            str(item.get("merchant_id") or "").strip().casefold(),
        )
        rows[key] = str(item.get("status") or "").strip()

    for item in registry.get("other_networks", []):
        key = (
            str(item.get("network") or "").strip().casefold(),
            str(item.get("merchant_id") or "").strip().casefold(),
        )
        rows[key] = str(item.get("status") or "").strip()

    return rows


def build_parity_report(events_payload: dict, registry: dict) -> dict[str, Any]:
    latest = derive_current_statuses(events_payload)
    current = registry_statuses(registry)

    keys = sorted(set(latest) | set(current))
    rows = []
    for key in keys:
        event = latest.get(key)
        event_status = (
            str(event.get("status_after") or "").strip()
            if event
            else None
        )
        registry_status = current.get(key)
        rows.append(
            {
                "network": key[0],
                "merchant_id": key[1],
                "event_status": event_status,
                "registry_status": registry_status,
                "in_sync": event_status == registry_status,
                "latest_event_id": (
                    event.get("event_id") if event else None
                ),
                "latest_sequence": (
                    event.get("sequence") if event else None
                ),
            }
        )

    return {
        "program_count": len(rows),
        "in_sync_count": sum(1 for row in rows if row["in_sync"]),
        "out_of_sync_count": sum(
            1 for row in rows if not row["in_sync"]
        ),
        "in_sync": all(row["in_sync"] for row in rows),
        "rows": rows,
    }


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Validate the append-only SCENTAI affiliate program event "
            "ledger and compare its latest states with the current registry."
        )
    )
    parser.add_argument("--events", type=Path, default=DEFAULT_EVENTS)
    parser.add_argument("--registry", type=Path, default=DEFAULT_REGISTRY)
    parser.add_argument("--machine-readable", action="store_true")
    args = parser.parse_args()

    try:
        report = build_parity_report(
            load_json(args.events),
            load_json(args.registry),
        )
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        parser.error(str(exc))

    if args.machine_readable:
        print(json.dumps(report, ensure_ascii=False))
    else:
        print(
            "SCENTAI affiliate event parity | "
            f"programs={report['program_count']} | "
            f"in_sync={report['in_sync_count']} | "
            f"out_of_sync={report['out_of_sync_count']}"
        )

    return 0 if report["in_sync"] else 20


if __name__ == "__main__":
    raise SystemExit(main())
