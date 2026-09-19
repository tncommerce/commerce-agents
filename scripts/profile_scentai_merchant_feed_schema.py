from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from examples.retail.api.merchant_feed_reader import (
    DEFAULT_MAX_FEED_BYTES,
    DEFAULT_MAX_FEED_ROWS,
    read_merchant_feed_rows,
)


def _non_empty(value: object) -> bool:
    return value is not None and bool(str(value).strip())


def _looks_numeric(value: object) -> bool:
    if isinstance(value, bool) or not _non_empty(value):
        return False
    try:
        float(str(value).strip().replace(",", "."))
    except ValueError:
        return False
    return True


def _looks_bool(value: object) -> bool:
    if isinstance(value, bool):
        return True
    if isinstance(value, int) and value in {0, 1}:
        return True
    if isinstance(value, str):
        return value.strip().casefold() in {
            "true",
            "false",
            "1",
            "0",
            "yes",
            "no",
            "ja",
            "nein",
        }
    return False


def _looks_http_url(value: object) -> bool:
    if not _non_empty(value):
        return False
    parsed = urlparse(str(value).strip())
    return parsed.scheme in {"http", "https"} and bool(parsed.netloc)


def _value_type(value: object) -> str:
    if value is None:
        return "null"
    if isinstance(value, bool):
        return "bool"
    if isinstance(value, int):
        return "int"
    if isinstance(value, float):
        return "float"
    if isinstance(value, str):
        return "str"
    if isinstance(value, list):
        return "list"
    if isinstance(value, dict):
        return "object"
    return type(value).__name__


def profile_feed_rows(rows: list[dict]) -> dict[str, Any]:
    columns = sorted(
        {
            str(key)
            for row in rows
            for key in row.keys()
        }
    )

    profiles = []
    total = len(rows)

    for column in columns:
        values = [row.get(column) for row in rows]
        non_empty = [value for value in values if _non_empty(value)]
        type_counts = Counter(_value_type(value) for value in non_empty)

        numeric = sum(1 for value in non_empty if _looks_numeric(value))
        boolean = sum(1 for value in non_empty if _looks_bool(value))
        urls = sum(1 for value in non_empty if _looks_http_url(value))

        profiles.append(
            {
                "column": column,
                "non_empty_count": len(non_empty),
                "empty_count": total - len(non_empty),
                "coverage_pct": (
                    round((len(non_empty) / total) * 100, 1)
                    if total
                    else 0.0
                ),
                "value_types": dict(sorted(type_counts.items())),
                "numeric_like_count": numeric,
                "boolean_like_count": boolean,
                "http_url_like_count": urls,
            }
        )

    return {
        "row_count": total,
        "column_count": len(columns),
        "columns": columns,
        "profiles": profiles,
        "privacy_note": (
            "This report intentionally excludes raw feed values, "
            "credentials, URLs and row samples. It profiles structure only."
        ),
        "next_action": (
            "Create a provider field map from the real feed schema. "
            "Do not infer or guess external column semantics solely from "
            "this structural report."
        ),
    }


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Profile the structure of a real merchant feed without "
            "printing raw row values or secret-bearing URLs."
        )
    )
    parser.add_argument("--feed", type=Path, required=True)
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
    parser.add_argument("--output", type=Path, default=None)
    parser.add_argument("--machine-readable", action="store_true")
    args = parser.parse_args()

    try:
        rows = read_merchant_feed_rows(
            args.feed,
            feed_format=args.feed_format,
            max_bytes=args.max_feed_bytes,
            max_rows=args.max_feed_rows,
        )
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        parser.error(str(exc))

    report = profile_feed_rows(rows)

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
            "SCENTAI feed schema profile | "
            f"rows={report['row_count']} | "
            f"columns={report['column_count']}"
        )
        for row in report["profiles"]:
            print(
                f"  {row['column']} | "
                f"coverage={row['coverage_pct']}% | "
                f"types={row['value_types']} | "
                f"numeric={row['numeric_like_count']} | "
                f"bool={row['boolean_like_count']} | "
                f"url={row['http_url_like_count']}"
            )

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
