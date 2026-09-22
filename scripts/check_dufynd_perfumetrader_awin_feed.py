from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
EXAMPLES_DIR = REPO_ROOT / "examples"

for import_root in (REPO_ROOT, EXAMPLES_DIR):
    import_path = str(import_root)
    if import_path not in sys.path:
        sys.path.insert(0, import_path)

from scripts.profile_scentai_merchant_feed_schema import profile_feed_rows  # noqa: E402
from scripts.promote_scentai_catalog import load_release_manifest  # noqa: E402
from scripts.validate_scentai_provider_config import (  # noqa: E402
    IDENTIFIER_FIELDS,
    PROMOTION_FIELDS,
    REQUIRED_CANONICAL_FIELDS,
    load_json,
    validate_provider_config,
)

from retail.api.merchant_feed_reader import (  # noqa: E402
    DEFAULT_MAX_FEED_BYTES,
    DEFAULT_MAX_FEED_ROWS,
    read_merchant_feed_rows,
)
from retail.api.merchant_import import (  # noqa: E402
    MerchantProductMapping,
    load_product_mappings,
)
from retail.api.merchant_providers import (  # noqa: E402
    MappedMerchantFeedAdapter,
    load_mapped_provider_adapter,
)
from retail.api.scentai_release_feed_readiness import (  # noqa: E402
    build_release_feed_readiness,
)

DEFAULT_CONFIG = Path(
    "examples/retail/data/dufynd_awin_perfumetrader_provider_config.json"
)
DEFAULT_MANIFEST = Path("examples/retail/data/scentai_release_batch_01.json")
DEFAULT_MAPPINGS = Path("examples/retail/data/merchant_product_mappings.json")

STATUS_EXIT_CODES = {
    "ready_for_manual_asset_review": 0,
    "review": 10,
    "blocked": 20,
    "blocked_schema": 20,
}


def _mapped_source(
    config: dict,
    canonical_field: str,
) -> str | None:
    field_map = config.get("field_map")
    if not isinstance(field_map, dict):
        return None
    value = field_map.get(canonical_field)
    if not isinstance(value, str) or not value.strip():
        return None
    return value.strip()


def _schema_gate(
    rows: list[dict],
    config: dict,
) -> dict[str, Any]:
    observed = {str(key) for row in rows for key in row}

    required_sources = {
        source
        for field in REQUIRED_CANONICAL_FIELDS
        if (source := _mapped_source(config, field))
    }
    missing_required = sorted(required_sources - observed)

    identifier_sources = {
        source
        for field in IDENTIFIER_FIELDS
        if (source := _mapped_source(config, field))
    }
    present_identifier_sources = sorted(identifier_sources & observed)

    promotion_sources = {
        field: source
        for field in PROMOTION_FIELDS
        if (source := _mapped_source(config, field))
    }
    missing_promotion = sorted(
        field
        for field, source in promotion_sources.items()
        if source not in observed
    )

    all_configured_sources = {
        str(source).strip()
        for source in config.get("field_map", {}).values()
        if isinstance(source, str) and source.strip()
    }

    blockers = []
    if missing_required:
        blockers.append("required_feed_columns_missing")
    if not present_identifier_sources:
        blockers.append("product_identifier_column_missing")

    return {
        "observed_column_count": len(observed),
        "missing_configured_columns": sorted(all_configured_sources - observed),
        "missing_required_columns": missing_required,
        "present_identifier_columns": present_identifier_sources,
        "missing_promotion_fields": missing_promotion,
        "import_schema_ready": not blockers,
        "blockers": blockers,
    }


def build_perfumetrader_intake_report(
    *,
    raw_rows: list[dict],
    config: dict,
    adapter: MappedMerchantFeedAdapter,
    release_product_ids: list[str],
    mappings: list[MerchantProductMapping],
) -> dict[str, Any]:
    config_report = validate_provider_config(config)
    profile = profile_feed_rows(raw_rows)
    schema = _schema_gate(raw_rows, config)

    if not config_report["valid"]:
        return {
            "status": "blocked_schema",
            "provider": adapter.provider_name,
            "config": config_report,
            "schema": schema,
            "profile": profile,
            "release": None,
            "writes_performed": False,
            "next_action": "fix_provider_config",
        }

    if not schema["import_schema_ready"]:
        return {
            "status": "blocked_schema",
            "provider": adapter.provider_name,
            "config": config_report,
            "schema": schema,
            "profile": profile,
            "release": None,
            "writes_performed": False,
            "next_action": "redownload_feed_with_required_columns",
        }

    adapted_rows = [adapter.adapt_row(row) for row in raw_rows]
    release = build_release_feed_readiness(
        release_product_ids,
        adapted_rows,
        mappings,
    )

    return {
        "status": release["status"],
        "provider": adapter.provider_name,
        "config": config_report,
        "schema": schema,
        "profile": profile,
        "release": release,
        "writes_performed": False,
        "next_action": (
            "manual_asset_review"
            if release["status"] == "ready_for_manual_asset_review"
            else "resolve_release_feed_gaps"
        ),
    }


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Run the full read-only DUFYND intake for a real Perfumetrader "
            "Awin product feed: schema profile, provider mapping and Release 01 readiness."
        )
    )
    parser.add_argument("--feed", type=Path, required=True)
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument("--mappings", type=Path, default=DEFAULT_MAPPINGS)
    parser.add_argument(
        "--feed-format",
        choices=("auto", "json", "csv"),
        default="auto",
    )
    parser.add_argument(
        "--max-feed-bytes",
        type=int,
        default=DEFAULT_MAX_FEED_BYTES,
    )
    parser.add_argument(
        "--max-feed-rows",
        type=int,
        default=DEFAULT_MAX_FEED_ROWS,
    )
    parser.add_argument("--machine-readable", action="store_true")
    args = parser.parse_args()

    try:
        raw_rows = read_merchant_feed_rows(
            args.feed,
            feed_format=args.feed_format,
            max_bytes=args.max_feed_bytes,
            max_rows=args.max_feed_rows,
        )
        config = load_json(args.config)
        adapter = load_mapped_provider_adapter(args.config)
        release_product_ids = load_release_manifest(args.manifest)
        mappings = load_product_mappings(args.mappings)
        report = build_perfumetrader_intake_report(
            raw_rows=raw_rows,
            config=config,
            adapter=adapter,
            release_product_ids=release_product_ids,
            mappings=mappings,
        )
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        parser.error(str(exc))

    if args.machine_readable:
        print(json.dumps(report, ensure_ascii=False))
    else:
        release = report["release"]
        release_summary = (
            "not-run"
            if release is None
            else (
                f"{release['release_trackable_offer_product_count']}/"
                f"{release['release_size']} offers; "
                f"{release['release_feed_image_product_count']}/"
                f"{release['release_size']} feed images"
            )
        )
        print(
            "DUFYND Perfumetrader Awin intake | "
            f"status={report['status'].upper()} | "
            f"rows={report['profile']['row_count']} | "
            f"columns={report['profile']['column_count']} | "
            f"release={release_summary} | "
            "writes=0"
        )

        for blocker in report["schema"]["blockers"]:
            print(f"  schema_blocker: {blocker}")
        for field in report["schema"]["missing_promotion_fields"]:
            print(f"  promotion_field_missing: {field}")

        if release is not None:
            for blocker in release["blockers"]:
                print(f"  release_blocker: {blocker}")

    return STATUS_EXIT_CODES[report["status"]]


if __name__ == "__main__":
    raise SystemExit(main())
