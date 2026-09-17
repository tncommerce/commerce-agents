from __future__ import annotations

import argparse
import json
from pathlib import Path

from .merchant_import import (
    import_feed_rows,
    load_product_mappings,
    upsert_offers_file,
)


def main() -> None:
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

    args = parser.parse_args()

    raw = json.loads(args.feed.read_text(encoding="utf-8-sig"))
    rows = raw.get("offers", raw if isinstance(raw, list) else [])

    mappings = load_product_mappings(args.mappings)
    result = import_feed_rows(rows, mappings)

    upsert_offers_file(args.offers, result.offers)

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
        "invalid": [
            row.model_dump(mode="json")
            for row in result.invalid
        ]
    }

    args.invalid.parent.mkdir(parents=True, exist_ok=True)
    args.invalid.write_text(
        json.dumps(invalid_payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )

    print(
        f"Read: {len(rows)} | "
        f"Imported: {len(result.offers)} | "
        f"Unmatched: {len(result.unmatched)} | "
        f"Invalid: {len(result.invalid)}"
    )


if __name__ == "__main__":
    main()
