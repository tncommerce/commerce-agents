from __future__ import annotations

import json
from pathlib import Path

DATA_DIR = Path("examples/retail/data")
AVAILABLE_STATUSES = {"available"}


def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def test_promotion_queue_covers_explicit_available_merchant_snapshots() -> None:
    queue = load_json(DATA_DIR / "scentai_catalog_promotion_queue.json")
    queue_by_id = {row["candidate_id"]: row for row in queue["candidates"]}

    for batch in (1, 2, 3):
        verification = load_json(DATA_DIR / f"scentai_catalog_batch{batch}_verification.json")

        for product in verification["products"]:
            candidate_id = product["candidate_id"]
            merchant_snapshot = product.get("merchant_snapshot", {})
            explicitly_available = sum(
                1 for status in merchant_snapshot.values() if status in AVAILABLE_STATUSES
            )

            declared = int(queue_by_id[candidate_id].get("merchant_coverage_count", 0) or 0)

            assert declared >= explicitly_available, (
                f"{candidate_id}: promotion queue declares {declared} researched "
                f"merchant(s), but verification explicitly marks "
                f"{explicitly_available} as available"
            )
