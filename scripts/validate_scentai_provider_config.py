from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

REQUIRED_CANONICAL_FIELDS = {
    "offer_id",
    "price",
    "in_stock",
    "product_url",
    "last_updated_at",
}
IDENTIFIER_FIELDS = {
    "merchant_product_id",
    "ean",
    "gtin",
}
PROMOTION_FIELDS = {
    "affiliate_url",
    "image_url",
}
ALLOWED_FIELD_MAP_KEYS = {
    "offer_id",
    "merchant_product_id",
    "ean",
    "gtin",
    "price",
    "currency",
    "shipping_cost",
    "shipping_label",
    "in_stock",
    "variant_label",
    "product_url",
    "affiliate_url",
    "last_updated_at",
    "image_url",
}
REQUIRED_CONSTANTS = {
    "merchant",
    "merchant_id",
    "merchant_name",
    "currency",
    "network",
    "data_source",
}


def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def validate_provider_config(config: dict) -> dict[str, Any]:
    issues: list[str] = []
    provider_name = str(config.get("provider_name") or "").strip()
    field_map = config.get("field_map")
    constants = config.get("constants")

    if not provider_name:
        issues.append("provider_name_missing")

    if not isinstance(field_map, dict) or not field_map:
        issues.append("field_map_missing_or_empty")
        field_map = {}

    if not isinstance(constants, dict):
        issues.append("constants_missing_or_invalid")
        constants = {}

    unknown = sorted(set(field_map) - ALLOWED_FIELD_MAP_KEYS)
    if unknown:
        issues.append(
            "unknown_canonical_field_map_keys:" + ",".join(unknown)
        )

    blank_sources = sorted(
        key
        for key, value in field_map.items()
        if not isinstance(value, str) or not value.strip()
    )
    if blank_sources:
        issues.append(
            "blank_external_source_columns:" + ",".join(blank_sources)
        )

    missing_required = sorted(
        field
        for field in REQUIRED_CANONICAL_FIELDS
        if field not in field_map
    )
    if missing_required:
        issues.append(
            "missing_required_field_mappings:"
            + ",".join(missing_required)
        )

    if not any(field in field_map for field in IDENTIFIER_FIELDS):
        issues.append("missing_product_identifier_mapping")

    missing_constants = sorted(
        key
        for key in REQUIRED_CONSTANTS
        if not str(constants.get(key) or "").strip()
    )
    if missing_constants:
        issues.append(
            "missing_required_constants:"
            + ",".join(missing_constants)
        )

    currency = str(constants.get("currency") or "").strip()
    if currency and len(currency) != 3:
        issues.append("currency_constant_must_be_three_characters")

    promotion_missing = sorted(
        field
        for field in PROMOTION_FIELDS
        if field not in field_map
    )

    import_ready = not any(
        issue.startswith(
            (
                "provider_name_missing",
                "field_map_missing_or_empty",
                "constants_missing_or_invalid",
                "unknown_canonical_field_map_keys",
                "blank_external_source_columns",
                "missing_required_field_mappings",
                "missing_product_identifier_mapping",
                "missing_required_constants",
                "currency_constant_must_be_three_characters",
            )
        )
        for issue in issues
    )

    promotion_ready = (
        import_ready
        and not promotion_missing
    )

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
            "Validate a SCENTAI mapped merchant provider config before "
            "running a real feed dry-run."
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
            print(
                "  - promotion_field_gaps: "
                + ", ".join(report["promotion_field_gaps"])
            )

    return 0 if report["valid"] else 20


if __name__ == "__main__":
    raise SystemExit(main())
