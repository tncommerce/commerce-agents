from __future__ import annotations

import json
from pathlib import Path

PATH = Path("examples/retail/data/dufynd_top_parfuemerie_release01_dry_run.json")


def load() -> dict:
    return json.loads(PATH.read_text(encoding="utf-8-sig"))


def test_release01_dry_run_is_all_or_nothing_blocked() -> None:
    report = load()
    assert report["status"] == "blocked_all_or_nothing"
    assert report["summary"]["release_size"] == 5
    assert report["summary"]["feed_rows_mapped"] == 4
    assert report["summary"]["ready_for_live_activation"] == 0


def test_all_awin_feed_links_use_expected_tracking_contract() -> None:
    tracking = load()["tracking_validation"]
    assert tracking["feed_row_count"] == 8053
    assert tracking["valid_awin_tracking_rows"] == 8053
    assert tracking["invalid_tracking_rows"] == 0
    assert tracking["publisher_id"] == "3099222"
    assert tracking["advertiser_id"] == "31081"


def test_hypnotic_poison_remains_blocked_when_absent_from_feed() -> None:
    rows = load()["products"]
    row = next(item for item in rows if item["product_id"] == "SC-DIOR-HYPNOTIC-POISON-EDT-100")
    assert row["merchant_product_id"] is None
    assert row["activation"] == "blocked"


def test_no_product_is_live_activated_by_dry_run() -> None:
    assert all(row["activation"].startswith("blocked") for row in load()["products"])
