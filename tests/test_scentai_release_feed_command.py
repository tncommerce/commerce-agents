from __future__ import annotations

import json
import sys

from scripts.check_scentai_release_feed import main


def test_release_feed_command_reports_complete_fixture_ready(
    tmp_path,
    monkeypatch,
    capsys,
) -> None:
    product_ids = [
        f"SC-COMMAND-{index}"
        for index in range(1, 6)
    ]

    manifest_path = tmp_path / "release.json"
    mappings_path = tmp_path / "mappings.json"
    feed_path = tmp_path / "feed.json"

    manifest_path.write_text(
        json.dumps({"product_ids": product_ids}),
        encoding="utf-8",
    )

    mappings_path.write_text(
        json.dumps(
            {
                "mappings": [
                    {
                        "product_id": product_id,
                        "merchant": "fixture-shop",
                        "merchant_product_id": f"SKU-{index}",
                        "ean": None,
                        "gtin": None,
                    }
                    for index, product_id in enumerate(
                        product_ids,
                        start=1,
                    )
                ]
            }
        ),
        encoding="utf-8",
    )

    feed_path.write_text(
        json.dumps(
            {
                "offers": [
                    {
                        "offer_id": f"offer-{index}",
                        "merchant": "fixture-shop",
                        "merchant_id": "fixture-shop-de",
                        "merchant_name": "Fixture Shop",
                        "merchant_product_id": f"SKU-{index}",
                        "price": 70.0 + index,
                        "currency": "EUR",
                        "in_stock": True,
                        "product_url": (
                            f"https://shop.example/product/{index}"
                        ),
                        "affiliate_url": (
                            f"https://network.example/click/{index}"
                        ),
                        "last_updated_at": (
                            "2026-09-19T08:00:00Z"
                        ),
                        "data_source": "fixture-feed",
                        "network": "Awin",
                        "image_url": (
                            f"https://cdn.example/product-{index}.jpg"
                        ),
                    }
                    for index in range(1, 6)
                ]
            }
        ),
        encoding="utf-8",
    )

    monkeypatch.setattr(
        sys,
        "argv",
        [
            "check_scentai_release_feed",
            "--feed",
            str(feed_path),
            "--manifest",
            str(manifest_path),
            "--mappings",
            str(mappings_path),
            "--machine-readable",
        ],
    )

    exit_code = main()
    payload = json.loads(capsys.readouterr().out)

    assert exit_code == 0
    assert payload["status"] == "ready_for_manual_asset_review"
    assert payload["release_mapped_product_count"] == 5
    assert payload["release_trackable_offer_product_count"] == 5
    assert payload["release_feed_image_product_count"] == 5
