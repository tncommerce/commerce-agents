from __future__ import annotations

import argparse
import json
from pathlib import Path

from .merchant_feed_preflight import build_feed_preflight
from .merchant_feed_reader import (
    DEFAULT_MAX_FEED_BYTES,
    DEFAULT_MAX_FEED_ROWS,
    read_merchant_feed_rows,
)
from .merchant_providers import (
    adapt_provider_rows,
    load_mapped_provider_adapter,
    register_provider_adapter,
)

STATUS_EXIT_CODES = {
    "ready": 0,
    "review": 10,
    "blocked": 20,
}


def preflight_status(report: dict) -> str:
    if not report["ready_for_offer_import"]:
        return "blocked"

    if not report["ready_for_promotion_assets"]:
        return "review"

    return "ready"


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Preflight an affiliate merchant feed before "
            "SCENTAI imports any offers or image candidates."
        )
    )
    parser.add_argument("--feed", type=Path, required=True)
    parser.add_argument(
        "--provider",
        type=str,
        default="canonical",
    )
    parser.add_argument(
        "--provider-config",
        type=Path,
        default=None,
    )
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
    parser.add_argument(
        "--machine-readable",
        action="store_true",
    )
    args = parser.parse_args()

    try:
        raw_rows = read_merchant_feed_rows(
            args.feed,
            feed_format=args.feed_format,
            max_bytes=args.max_feed_bytes,
            max_rows=args.max_feed_rows,
        )
    except ValueError as exc:
        parser.error(str(exc))

    provider_name = args.provider

    if args.provider_config is not None:
        try:
            adapter = load_mapped_provider_adapter(args.provider_config)
            register_provider_adapter(
                adapter,
                replace=True,
            )
            provider_name = adapter.provider_name
        except (
            OSError,
            ValueError,
            json.JSONDecodeError,
        ) as exc:
            parser.error(f"Invalid provider config: {exc}")

    rows = adapt_provider_rows(
        provider_name,
        raw_rows,
    )
    report = build_feed_preflight(rows)
    status = preflight_status(report)

    payload = {
        "status": status,
        "exit_code": STATUS_EXIT_CODES[status],
        "provider": provider_name,
        **report,
    }

    if args.machine_readable:
        print(json.dumps(payload, ensure_ascii=False))
    else:
        print(
            "SCENTAI affiliate feed preflight | "
            f"status={status.upper()} | "
            f"provider={provider_name} | "
            f"rows={report['row_count']} | "
            f"import_ready={report['import_ready_rows']} | "
            f"promotion_ready={report['promotion_ready_rows']}"
        )

        print("Coverage:")
        for field, stats in report["coverage"].items():
            print(
                f"  {field:<20} "
                f"{stats['valid']}/{report['row_count']} "
                f"({stats['coverage_pct']:.1f}%)"
            )

        if report["issues"]:
            print("Issue preview:")
            for issue in report["issues"][:10]:
                import_failures = ", ".join(issue["import_failures"]) or "-"
                promotion_failures = ", ".join(issue["promotion_failures"]) or "-"
                print(
                    f"  row={issue['row_index']} | "
                    f"offer={issue['offer_id'] or '-'} | "
                    f"import={import_failures} | "
                    f"promotion={promotion_failures}"
                )

    return STATUS_EXIT_CODES[status]


if __name__ == "__main__":
    raise SystemExit(main())
