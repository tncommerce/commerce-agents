from __future__ import annotations

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
        content_id = row["content_id"]
        assert content_id in plan_by_id
        assert plan_by_id[content_id]["status"] == "scripted"
        assert row["landing_path"] == plan_by_id[content_id]["landing_path"]
        assert row["product_ids"] == plan_by_id[content_id]["product_ids"]
        assert 20 <= int(row["duration_target_seconds"]) <= 35
        assert row["scenes"]
        assert row["caption_skeleton"]
        assert set(row["product_ids"]) <= live_ids

        customer_text = " ".join(
            [
                row["hook"],
                row["caption_skeleton"],
                *[scene["voiceover"] + " " + scene["on_screen"] for scene in row["scenes"]],
            ]
        )

        assert "€" not in customer_text
        assert "ist ein 1:1-klon" not in customer_text.casefold()
        assert "ist der 1:1-klon" not in customer_text.casefold()


def test_clone_wording_only_appears_when_claim_basis_documents_clone() -> None:
    for row in scripted_rows():
        customer_text = " ".join(
            [
                row["hook"],
                *[scene["voiceover"] + " " + scene["on_screen"] for scene in row["scenes"]],
            ]
        ).casefold()

        if "clone-beziehung" not in customer_text:
            continue

        basis = " ".join(row["claim_basis"]).casefold()
        assert "clone/high" in basis
