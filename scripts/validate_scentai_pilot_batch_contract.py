py>>>
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
  
…[16383 chars truncated — re-run with head/grep/tail for full output]…
nonical_field_map_keys",
                "blank_external_source_columns",
                "missing_required_field_mappings",
                "missing_product_identifier_mapping",
                "missing_required_constants",
                "currency_constant_must_be_three_characters",
            )
        )
        for issue in issues
    )

    promotion_ready = import_ready and not promotion_missing

    return {
        "valid": import_ready,
        "provider_name": provider_name or None,
        "import_contract_ready": import_ready,
        "promotion_asset_contract_ready": promotion_ready,
        "promotion_field_gaps": promotion_missing,
        "issues": issues,
        "next_action": (
            "run_real_feed_preflight"
            if promotion_ready
            else "complete_provider_mapping_from_real_feed_sample"
        ),
        "note": (
            "This validates configuration structure only. It does not prove "
            "the external columns contain correct values; the real feed "
            "preflight and release checker remain mandatory."
        ),
    }


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Validate a SCENTAI mapped merchant provider config before running a real feed dry-run."
        )
    )
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--machine-readable", action="store_true")
    args = parser.parse_args()

    try:
        report = validate_provider_config(load_json(args.config))
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        parser.error(str(exc))

    if args.machine_readable:
        print(json.dumps(report, ensure_ascii=False))
    else:
        print(
            "SCENTAI provider config | "
            f"valid={report['valid']} | "
            f"import_ready={report['import_contract_ready']} | "
            f"promotion_ready={report['promotion_asset_contract_ready']} | "
            f"next={report['next_action']}"
        )
        for issue in report["issues"]:
            print(f"  - {issue}")
        if report["promotion_field_gaps"]:
            print("  - promotion_field_gaps: " + ", ".join(report["promotion_field_gaps"]))

    return 0 if report["valid"] else 20


if __name__ == "__main__":
    raise SystemExit(main())
