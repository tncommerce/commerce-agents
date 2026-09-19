from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from scripts.build_scentai_jarvis_operations_status import (
    build_operations_status,
)

DATA_DIR = Path("examples/retail/data")
DEFAULT_MAPPING = DATA_DIR / "scentai_merchant_mapping_work_queue.json"
DEFAULT_AFFILIATE = DATA_DIR / "scentai_affiliate_activation_status.json"
DEFAULT_IMAGES = DATA_DIR / "scentai_image_approval_work_queue.json"
DEFAULT_RELEASE = DATA_DIR / "scentai_release_01_gate_status.json"
DEFAULT_FEED = DATA_DIR / "scentai_release_01_feed_activation_queue.json"
DEFAULT_STATUS = DATA_DIR / "scentai_jarvis_operations_status.json"


def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def validate_operations_status(
    current: dict,
    mapping: dict,
    affiliate: dict,
    images: dict,
    release: dict,
    feed: dict,
) -> dict[str, Any]:
    generated_at = str(current.get("generated_at") or "").strip()
    if not generated_at:
        return {
            "valid": False,
            "issues": ["operations_status_generated_at_missing"],
        }

    expected = build_operations_status(
        mapping,
        affiliate,
        images,
        release,
        feed,
        generated_at=generated_at,
    )

    issues: list[str] = []

    current_fingerprint = str(current.get("source_fingerprint_sha256") or "").strip()
    expected_fingerprint = expected["source_fingerprint_sha256"]

    if current_fingerprint != expected_fingerprint:
        issues.append("operations_status_source_fingerprint_stale")

    fields = [
        "system",
        "control_plane",
        "policy_ref",
        "overall_state",
        "user_approval_required_now",
        "next_action",
        "next_action_class",
        "blockers",
        "safety",
        "catalog",
        "affiliate",
        "images",
        "release_01",
        "pending_manual_approvals",
        "operating_note",
    ]

    drift_fields = [field for field in fields if current.get(field) != expected.get(field)]
    if drift_fields:
        issues.append("operations_status_field_drift:" + ",".join(drift_fields))

    return {
        "valid": not issues,
        "issues": issues,
        "expected_source_fingerprint_sha256": expected_fingerprint,
        "current_source_fingerprint_sha256": (current_fingerprint or None),
        "drift_fields": drift_fields,
    }


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Validate that the committed SCENTAI Jarvis operations status "
            "matches its current source-of-truth states."
        )
    )
    parser.add_argument("--status", type=Path, default=DEFAULT_STATUS)
    parser.add_argument("--mapping", type=Path, default=DEFAULT_MAPPING)
    parser.add_argument("--affiliate", type=Path, default=DEFAULT_AFFILIATE)
    parser.add_argument("--images", type=Path, default=DEFAULT_IMAGES)
    parser.add_argument("--release", type=Path, default=DEFAULT_RELEASE)
    parser.add_argument("--feed", type=Path, default=DEFAULT_FEED)
    parser.add_argument("--machine-readable", action="store_true")
    args = parser.parse_args()

    try:
        report = validate_operations_status(
            load_json(args.status),
            load_json(args.mapping),
            load_json(args.affiliate),
            load_json(args.images),
            load_json(args.release),
            load_json(args.feed),
        )
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        parser.error(str(exc))

    if args.machine_readable:
        print(json.dumps(report, ensure_ascii=False))
    else:
        print(
            "SCENTAI Jarvis operations parity | "
            f"valid={report['valid']} | "
            f"drift_fields={report.get('drift_fields', [])}"
        )
        for issue in report["issues"]:
            print(f"  - {issue}")

    return 0 if report["valid"] else 20


if __name__ == "__main__":
    raise SystemExit(main())
