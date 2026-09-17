from __future__ import annotations

import argparse
import json
from pathlib import Path

from .merchant_feed_reader import (
    read_merchant_feed_rows,
)
from .merchant_provider_contract import (
    validate_provider_contract_rows,
)
from .merchant_providers import adapt_provider_rows

from .merchant_run_reports import (
    append_import_run_report,
    build_import_run_report,
)

from .merchant_run_status import (
    evaluate_import_run,
    machine_readable_result,
)

from .merchant_import import (
    analyze_offer_changes,
    import_feed_rows,
    load_product_mappings,
    upsert_offers_file,
)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Import merchant feed rows into SCENTAI."
    )
    parser.add_argument("--feed", type=Path, required=True)
    parser.add_argument(
        "--mappings",
        type=Path,
        default=Path("examples/retail/data/merchant_product_mappings.json"),
    )
    parser.add_argument(
        "--offers",
        type=Path,
        default=Path("examples/retail/data/merchant_offers.json"),
    )
    parser.add_argument(
        "--unmatched",
        type=Path,
        default=Path("examples/retail/data/merchant_unmatched.json"),
    )
    parser.add_argument(
        "--invalid",
        type=Path,
        default=Path("examples/retail/data/merchant_invalid.json"),
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Validate and analyze the feed without writing output files.",
    )
    parser.add_argument(
        "--provider",
        type=str,
        default="canonical",
        help="Merchant feed provider adapter.",
    )
    parser.add_argument(
        "--feed-format",
        choices=("auto", "json", "csv"),
        default="auto",
        help=(
            "Input feed format. Defaults to automatic "
            "detection from the file extension."
        ),
    )
    parser.add_argument(
        "--authoritative-merchant-id",
        type=str,
        default=None,
        help="Merchant ID for a complete feed snapshot.",
    )
    parser.add_argument(
        "--authoritative-data-source",
        type=str,
        default=None,
        help="Data source for a complete feed snapshot.",
    )
    parser.add_argument(
        "--allow-empty-authoritative",
        action="store_true",
        help=(
            "Allow an authoritative write with zero matched offers. "
            "Use only for an intentional full delisting."
        ),
    )
    parser.add_argument(
        "--run-report",
        type=Path,
        default=None,
        help=(
            "Optional JSONL audit log path. "
            "Defaults next to the merchant offers file."
        ),
    )
    parser.add_argument(
        "--machine-readable",
        action="store_true",
        help="Print one JSON result for schedulers and automation.",
    )

    args = parser.parse_args()

    if (
        (args.authoritative_merchant_id is None)
        != (args.authoritative_data_source is None)
    ):
        parser.error(
            "--authoritative-merchant-id and "
            "--authoritative-data-source must be provided together"
        )

    raw_rows = read_merchant_feed_rows(
        args.feed,
        feed_format=args.feed_format,
    )

    adapted_rows = adapt_provider_rows(
        args.provider,
        raw_rows,
    )

    contract = validate_provider_contract_rows(
        adapted_rows
    )

    rows = contract.rows

    mappings = load_product_mappings(args.mappings)
    result = import_feed_rows(rows, mappings)

    combined_invalid = [
        {
            "row_index": issue.row_index,
            "offer_id": issue.offer_id,
            "merchant": (
                adapted_rows[issue.row_index].get("merchant")
                if issue.row_index < len(adapted_rows)
                else None
            ),
            "reason": issue.reason,
            "error": issue.error,
        }
        for issue in contract.invalid
    ]

    combined_invalid.extend(
        row.model_dump(mode="json")
        for row in result.invalid
    )

    authoritative = (
        args.authoritative_merchant_id is not None
        and args.authoritative_data_source is not None
    )

    if (
        authoritative
        and not args.dry_run
        and not result.offers
        and not args.allow_empty_authoritative
    ):
        parser.error(
            "Refusing authoritative write with zero matched offers. "
            "Run --dry-run first or pass --allow-empty-authoritative "
            "only for an intentional full delisting."
        )

    lifecycle_kwargs = {
        "authoritative_merchant_id": args.authoritative_merchant_id,
        "authoritative_data_source": args.authoritative_data_source,
    }

    if args.dry_run:
        report = analyze_offer_changes(
            args.offers,
            result.offers,
            **lifecycle_kwargs,
        )
    else:
        report = upsert_offers_file(
            args.offers,
            result.offers,
            **lifecycle_kwargs,
        )

        unmatched_payload = {
            "unmatched": [
                row.model_dump(mode="json")
                for row in result.unmatched
            ]
        }

        args.unmatched.parent.mkdir(parents=True, exist_ok=True)
        args.unmatched.write_text(
            json.dumps(unmatched_payload, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )

        invalid_payload = {
            "invalid": combined_invalid
        }

        args.invalid.parent.mkdir(parents=True, exist_ok=True)
        args.invalid.write_text(
            json.dumps(invalid_payload, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )

    mode = "DRY-RUN" if args.dry_run else "WRITE"

    run_report = build_import_run_report(
        provider=args.provider,
        mode=mode,
        feed_file=args.feed.name,
        authoritative_merchant_id=args.authoritative_merchant_id,
        authoritative_data_source=args.authoritative_data_source,
        allow_empty_authoritative=args.allow_empty_authoritative,
        read=len(adapted_rows),
        new=report.new,
        updated=report.updated,
        unchanged=report.unchanged,
        unmatched=len(result.unmatched),
        invalid=len(combined_invalid),
        deactivated=report.deactivated,
    )

    if not args.dry_run:
        run_report_path = (
            args.run_report
            if args.run_report is not None
            else args.offers.with_name(".merchant_import_runs.jsonl")
        )
        append_import_run_report(
            run_report_path,
            run_report,
        )

    operational = evaluate_import_run(run_report)

    if args.machine_readable:
        print(
            json.dumps(
                machine_readable_result(run_report),
                ensure_ascii=False,
            )
        )
    else:
        print(
            f"Mode: {mode} | "
            f"Read: {len(adapted_rows)} | "
            f"New: {report.new} | "
            f"Updated: {report.updated} | "
            f"Unchanged: {report.unchanged} | "
            f"Unmatched: {len(result.unmatched)} | "
            f"Invalid: {len(combined_invalid)} | "
            f"Deactivated: {report.deactivated} | "
            f"Status: {operational.status.upper()} | "
            f"Run ID: {run_report.run_id}"
        )

    return operational.exit_code


if __name__ == "__main__":
    raise SystemExit(main())
