from __future__ import annotations

import json
import re
from pathlib import Path

DATA_DIR = Path("examples/retail/data")
IDENTIFIER_PATTERN = re.compile(r"^[A-Za-z0-9._:-]{1,80}$")
ALLOWED_CHANNELS = {
    "tiktok",
    "instagram",
    "youtube",
    "organic",
    "newsletter",
    "partner",
}
ALLOWED_LANDINGS = {
    "/duftfinder",
    "/parfum-alternativen",
    "/parfum-geschenkberater",
}


def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def test_prelaunch_content_plan_is_trackable_and_live_safe() -> None:
    plan = load_json(DATA_DIR / "scentai_launch_content_plan.json")
    catalog = load_json(DATA_DIR / "catalog.json")

    live_ids = {
        product["product_id"]
        for product in catalog.get("products", [])
        if str(product.get("product_id") or "").startswith("SC-")
        and product.get("category") == "fragrance"
        and product.get("in_stock") is not False
    }

    rows = plan["content"]
    content_ids = [row["content_id"] for row in rows]

    assert plan["campaign_id"] == "launch01"
    assert len(rows) == 15
    assert len(content_ids) == len(set(content_ids))
    assert set(plan["channels"]) <= ALLOWED_CHANNELS

    for row in rows:
        assert IDENTIFIER_PATTERN.fullmatch(row["content_id"])
        assert row["landing_path"] in ALLOWED_LANDINGS
        assert row["status"] == "planned"
        assert row["product_ids"]
        assert set(row["product_ids"]) <= live_ids
