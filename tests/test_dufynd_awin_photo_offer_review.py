from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from pathlib import Path

import pytest
from scripts.export_dufynd_awin_photo_offer_review import TARGETS, build_review

SOURCE = b"bounded offline source fixture"
SECRET = "NEVER_PRINT_TEST_CREDENTIAL"


def metadata() -> dict:
    return {
        "advertiser_id": "31081",
        "feed_id": "91379",
        "joined": True,
        "membership_status": "active",
        "downloaded": True,
        "checked_at": "2026-10-26T12:00:00+00:00",
        "last_imported": "2026-10-26 00:03:45",
        "download_sha256": hashlib.sha256(SOURCE).hexdigest(),
        "downloaded_bytes": len(SOURCE),
    }


def row() -> dict:
    return {
        "merchant_product_id": "924719",
        "aw_product_id": "38332629354",
        "product_name": "Bois Imperial Eau de Parfum 100 ml",
        "search_price": "91.95",
        "delivery_cost": "0.00",
        "currency": "EUR",
        "merchant_deep_link": "https://www.topparfuemerie.de/bois-imperial?sku=924719",
        "merchant_image_url": "https://www.topparfuemerie.de/media/catalog/product/9/2/924719_3770010614630_051.png",
        "aw_deep_link": "https://www.awin1.com/pclick.php?p=38332629354&a=3099222&m=31081",
        "unrequested_private_field": "MUST_NOT_ESCAPE",
    }


def test_original_values_exact_six_scope_and_missing_facts_are_preserved() -> None:
    original = row()
    result = build_review(
        [original, {"merchant_product_id": "unrequested"}], metadata(), SOURCE, SECRET
    )
    assert len(result["rows"]) == len(TARGETS) == 6
    assert not result["activation_allowed"] and not result["image_publication_allowed"]
    assert result["tracking_clicks_executed"] == 0
    first = result["rows"][0]
    assert first["fields"] == {
        k: v for k, v in original.items() if k != "unrequested_private_field"
    }
    assert "gtin" in first["missing_fields"] and "in_stock" in first["missing_fields"]
    assert "gtin" not in first["fields"] and "in_stock" not in first["fields"]
    assert all(item["status"] == "HOLD" for item in result["rows"][1:])
    assert "MUST_NOT_ESCAPE" not in json.dumps(result)


def test_duplicate_target_remains_held_without_choosing_a_variant() -> None:
    result = build_review([row(), row()], metadata(), SOURCE, SECRET)
    assert result["rows"][0]["matches"] == 2
    assert result["rows"][0]["status"] == "HOLD"
    assert "fields" not in result["rows"][0]


@pytest.mark.parametrize(
    "change", [{"joined": False}, {"feed_id": "0"}, {"download_sha256": "bad"}]
)
def test_source_membership_identity_and_download_binding_fail_closed(change: dict) -> None:
    with pytest.raises(ValueError, match="not_verified"):
        build_review([row()], {**metadata(), **change}, SOURCE, SECRET)


def test_secret_and_wrong_publisher_urls_are_withheld_without_rewriting() -> None:
    source = {
        **row(),
        "description": "%4eEVER_PRINT_TEST_CREDENTIAL",
        "aw_deep_link": row()["aw_deep_link"].replace("3099222", "1"),
        "alternate_image": "https://www.topparfuemerie.de/secret?api_key=x",
    }
    result = build_review([source], metadata(), SOURCE, SECRET)
    first = result["rows"][0]
    assert set(first["withheld_fields"]) == {"description", "aw_deep_link", "alternate_image"}
    assert SECRET not in json.dumps(result)
    assert first["fields"]["merchant_image_url"] == source["merchant_image_url"]


def test_stdlib_only_cli_outputs_json_and_no_source_files(tmp_path: Path) -> None:
    source = tmp_path / "feed.json"
    source.write_text(json.dumps([row()]))
    meta = tmp_path / "metadata.json"
    meta.write_text(
        json.dumps(
            {
                **metadata(),
                "downloaded_bytes": source.stat().st_size,
                "download_sha256": hashlib.sha256(source.read_bytes()).hexdigest(),
            }
        )
    )
    run = subprocess.run(
        [
            sys.executable,
            "-S",
            "scripts/export_dufynd_awin_photo_offer_review.py",
            "--feed",
            str(source),
            "--metadata",
            str(meta),
        ],
        env={"AWIN_DATA_FEED_API_KEY": SECRET},
        text=True,
        capture_output=True,
    )
    assert run.returncode == 0, run.stderr
    assert run.stdout.startswith("DUFYND_BOUNDED_PHOTO_OFFER_REVIEW=")
    assert SECRET not in run.stdout + run.stderr
    assert len(run.stdout.splitlines()) == 1
    assert set(tmp_path.iterdir()) == {source, meta}
