from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
EXAMPLES_DIR = REPO_ROOT / "examples"

for import_root in (REPO_ROOT, EXAMPLES_DIR):
    import_path = str(import_root)
    if import_path not in sys.path:
        sys.path.insert(0, import_path)

from retail.api.merchant_feed_reader import (  # noqa: E402
    DEFAULT_MAX_FEED_BYTES,
    DEFAULT_MAX_FEED_ROWS,
    read_merchant_feed_rows,
)
from retail.api.merchant_import import load_product_mappings  # noqa: E402
from retail.api.merchant_providers import (  # noqa: E402
    adapt_provider_rows,
    load_mapped_provider_adapter,
    register_provider_adapter,
)
from retail.api.scentai_release_feed_readiness import (  # noqa: E402
    build_release_feed_readiness,
)
from scripts.promote_scentai_catalog import load_release_manifest  # noqa: E402

DEFAULT_MANIFEST = Path(
    "examples/retail/data/scentai_release_batch_01.json"
)
DEFAULT_MAPPINGS = Path(
    "examples/retail/data/merchant_product_mappings.json"
)

STATUS_EXIT_CODES = {
    "ready_for_manual_asset_review": 0,
    "review": 10,
    "blocked": 20,
}


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Check whether an approved affiliate feed can cover a guarded "
            "SCENTAI release manifest before any write occurs."
        )
    )
    parser.add_argument("--feed", type=Path, required=True)
    parser.add_argument(
        "--manifest",
        type=Path,
        default=DEFAULT_MANIFEST,
    )
    parser.add_argument(
        "--mappings",
        type=Path,
        default=DEFAULT_MAPPINGS,
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
        "--machine-readable",
        action="store_true",
    )
    args = parser.parse_args()

    try:
        release_product_ids = load_release_manifest(args.manifest)
        raw_rows = read_merchant_feed_rows(
            args.feed,
            feed_format=args.feed_format,
            max_bytes=args.max_feed_bytes,
            max_rows=args.max_feed_rows,
        )
        mappings = load_product_mappings(args.mappings)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        parser.error(str(exc))

    provider_name = args.provider
    if args.provider_config is not None:
        try:
            adapter = load_mapped_provider_adapter(
                args.provider_config
            )
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

    report = build_release_feed_readiness(
        release_product_ids,
        adapted_rows,
        mappings,
    )
    report = {
        "provider": provider_name,
        "release_manifest": str(args.manifest),
        **report,
    }

    if args.machine_readable:
        print(json.dumps(report, ensure_ascii=False))
    else:
        print(
            "SCENTAI release feed readiness | "
            f"status={report['status'].upper()} | "
            f"provider={provider_name} | "
            f"release={report['release_size']} | "
            f"mapped={report['release_mapped_product_count']} | "
            f"affiliate_offers="
            f"{report['release_trackable_offer_product_count']} | "
            f"feed_images={report['release_feed_image_product_count']}"
        )

        if report["blockers"]:
            print("Blockers:")
            for blocker in report["blockers"]:
                print(f"  - {blocker}")

        print("Release products:")
        for row in report["products"]:
            print(
                f"  {row['product_id']} | "
                f"mapped={row['mapped']} | "
                f"trackable={row['trackable_offer_ready']} | "
                f"feed_image={row['feed_image_candidate_ready']}"
            )

    return STATUS_EXIT_CODES[report["status"]]


if __name__ == "__main__":
    raise SystemExit(main())
