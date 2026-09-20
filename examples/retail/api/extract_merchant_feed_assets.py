from __future__ import annotations

import argparse
import json
from pathlib import Path

from .merchant_feed_assets import (
    extract_feed_image_candidates,
)
from .merchant_feed_reader import (
    DEFAULT_MAX_FEED_BYTES,
    DEFAULT_MAX_FEED_ROWS,
    read_merchant_feed_rows,
)
from .merchant_import import load_product_mappings
from .merchant_providers import (
    adapt_provider_rows,
    load_mapped_provider_adapter,
    register_provider_adapter,
)

DEFAULT_OUTPUT = Path("examples/retail/data/merchant_feed_image_candidates.json")


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Extract reviewable product-image candidates from an approved affiliate merchant feed."
        )
    )
    parser.add_argument("--feed", type=Path, required=True)
    parser.add_argument(
        "--mappings",
        type=Path,
        default=Path("examples/retail/data/merchant_product_mappings.json"),
    )
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
        "--output",
        type=Path,
        default=DEFAULT_OUTPUT,
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

    adapted_rows = adapt_provider_rows(
        provider_name,
        raw_rows,
    )
    mappings = load_product_mappings(args.mappings)

    result = extract_feed_image_candidates(
        adapted_rows,
        mappings,
    )

    payload = {
        "status": "review_only_not_live",
        "provider": provider_name,
        **result,
    }

    args.output.parent.mkdir(
        parents=True,
        exist_ok=True,
    )
    args.output.write_text(
        json.dumps(
            payload,
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )

    if args.machine_readable:
        print(json.dumps(payload, ensure_ascii=False))
    else:
        print(
            "DUFYND feed image candidates | "
            f"provider={provider_name} | "
            f"candidates={result['candidate_count']} | "
            f"unmatched={result['unmatched_count']} | "
            f"invalid={result['invalid_count']} | "
            f"output={args.output}"
        )

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
