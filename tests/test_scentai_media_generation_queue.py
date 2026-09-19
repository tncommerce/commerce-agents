_future__ import annotations

import json
from pathlib import Path

DATA_DIR = Path("examples/retail/data")
SCRIPT_FILES = (
    "scentai_launch_scripts_batch_01.json",
    "scentai_launch_scripts_batch_02.json",
    "scentai_launch_scripts_batch_03.json",
)


def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def scripted_rows() -> list[dict]:
    rows: list[dict] = []
    for file_name in SCRIPT_FILES:
        payload = load_json(DATA_DIR / file_name)
        rows.extend(payload["creatives"])
    return rows


def test_launch_script_batches_match_content_plan() -> None:
    plan = load_json(DATA_DIR / "scentai_launch_content_plan.json")
    catalog = load_json(DATA_DIR / "catalog.json")

    plan_by_id = {row["content_id"]: row for row in plan["content"]}
    live_ids = {
        product["product_id"]
        for product in catalog.get("products", [])
        if str(product.get("product_id") or "").startswith("SC-")
        and product.get("category") == "fragrance"
        and product.get("in_stock") is not False
    }

    rows = scripted_rows()
    content_ids = [row["content_id"] for row in rows]

    assert len(rows) == 15
    assert len(content_ids) == len(set(content_ids))

    scripted_plan_ids = {
        row["content_id"] for row in plan["content"] if row["status"] == "scripted"
    }
    assert set(content_ids) == scripted_plan_ids

    for row in rows:
        content_id = row["content_
…[6718 chars truncated — re-run with head/grep/tail for full output]…
             1 for status in merchant_snapshot.values() if status in AVAILABLE_STATUSES
            )

            declared = int(queue_by_id[candidate_id].get("merchant_coverage_count", 0) or 0)

            assert declared >= explicitly_available, (
                f"{candidate_id}: promotion queue declares {declared} researched "
                f"merchant(s), but verification explicitly marks "
                f"{explicitly_available} as available"
            )
