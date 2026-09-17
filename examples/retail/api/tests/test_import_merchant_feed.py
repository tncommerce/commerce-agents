import json
import sys

import pytest

from retail.api.import_merchant_feed import main


PRODUCT_ID = "SC-ESSENTIAL-PARFUMS-BOIS-IMPERIAL-100"


def test_import_merchant_feed_command_end_to_end(tmp_path, monkeypatch, capsys) -> None:
    mappings_path = tmp_path / "mappings.json"
    feed_path = tmp_path / "feed.json"
    offers_path = tmp_path / "offers.json"
    unmatched_path = tmp_path / "unmatched.json"
    invalid_path = tmp_path / "invalid.json"

    mappings_path.write_text(
        json.dumps(
            {
                "mappings": [
                    {
                        "product_id": PRODUCT_ID,
                        "merchant": "notino",
                        "merchant_product_id": "NOTINO-123",
                        "ean": None,
                        "gtin": None,
                    }
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
                        "offer_id": "notino-bois-imperial-100",
                        "merchant": "notino",
                        "merchant_id": "notino-de",
                        "merchant_name": "Notino",
                        "merchant_product_id": "NOTINO-123",
                        "price": 89.95,
                        "currency": "EUR",
                        "shipping_cost": 0.0,
                        "in_stock": True,
                        "variant_label": "100 ml",
                        "product_url": "https://example.com/bois-imperial",
                        "affiliate_url": "https://example.com/affiliate/bois-imperial",
                        "network": "CJ",
                        "data_source": "test-feed",
                        "last_updated_at": "2026-09-17T12:00:00Z",
                    },
                    {
                        "offer_id": "notino-unknown",
                        "merchant": "notino",
                        "merchant_id": "notino-de",
                        "merchant_name": "Notino",
                        "merchant_product_id": "UNKNOWN-999",
                        "price": 49.95,
                        "currency": "EUR",
                        "shipping_cost": 0.0,
                        "in_stock": True,
                        "product_url": "https://example.com/unknown",
                        "network": "CJ",
                        "data_source": "test-feed",
                        "last_updated_at": "2026-09-17T12:00:00Z",
                    },
                    {
                        "offer_id": "broken-row",
                        "merchant": "notino",
                        "merchant_id": "notino-de",
                        "merchant_name": "Notino",
                        "merchant_product_id": "BROKEN-1",
                        "currency": "EUR",
                        "product_url": "https://example.com/broken",
                        "last_updated_at": "2026-09-17T12:00:00Z",
                    },
                ]
            }
        ),
        encoding="utf-8",
    )

    monkeypatch.setattr(
        sys,
        "argv",
        [
            "import_merchant_feed",
            "--feed",
            str(feed_path),
            "--mappings",
            str(mappings_path),
            "--offers",
            str(offers_path),
            "--unmatched",
            str(unmatched_path),
            "--invalid",
            str(invalid_path),
        ],
    )

    main()

    output = capsys.readouterr().out
    assert "Read: 3 | New: 1 | Updated: 0 | Unchanged: 0 | Unmatched: 1 | Invalid: 1" in output

    saved_offers = json.loads(offers_path.read_text(encoding="utf-8"))
    assert len(saved_offers["offers"]) == 1
    assert saved_offers["offers"][0]["product_id"] == PRODUCT_ID
    assert saved_offers["offers"][0]["affiliate_url"] is not None

    saved_unmatched = json.loads(unmatched_path.read_text(encoding="utf-8"))
    assert len(saved_unmatched["unmatched"]) == 1
    assert saved_unmatched["unmatched"][0]["offer_id"] == "notino-unknown"

    saved_invalid = json.loads(invalid_path.read_text(encoding="utf-8"))
    assert len(saved_invalid["invalid"]) == 1
    assert saved_invalid["invalid"][0]["row_index"] == 2
    assert saved_invalid["invalid"][0]["offer_id"] == "broken-row"
    assert saved_invalid["invalid"][0]["reason"] == "invalid_feed_row"


def test_import_merchant_feed_dry_run_does_not_write_files(
    tmp_path,
    monkeypatch,
    capsys,
) -> None:
    mappings_path = tmp_path / "mappings.json"
    feed_path = tmp_path / "feed.json"
    offers_path = tmp_path / "offers.json"
    unmatched_path = tmp_path / "unmatched.json"
    invalid_path = tmp_path / "invalid.json"

    mappings_path.write_text(
        json.dumps(
            {
                "mappings": [
                    {
                        "product_id": PRODUCT_ID,
                        "merchant": "notino",
                        "merchant_product_id": "NOTINO-123",
                        "ean": None,
                        "gtin": None,
                    }
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
                        "offer_id": "notino-bois-imperial-100",
                        "merchant": "notino",
                        "merchant_id": "notino-de",
                        "merchant_name": "Notino",
                        "merchant_product_id": "NOTINO-123",
                        "price": 89.95,
                        "currency": "EUR",
                        "shipping_cost": 0.0,
                        "in_stock": True,
                        "product_url": "https://example.com/bois-imperial",
                        "network": "CJ",
                        "data_source": "test-feed",
                        "last_updated_at": "2026-09-17T12:00:00Z",
                    }
                ]
            }
        ),
        encoding="utf-8",
    )

    offers_path.write_text(json.dumps({"offers": []}), encoding="utf-8")
    original_offers = offers_path.read_text(encoding="utf-8")
    unmatched_path.write_text("KEEP-UNMATCHED", encoding="utf-8")
    invalid_path.write_text("KEEP-INVALID", encoding="utf-8")

    monkeypatch.setattr(
        sys,
        "argv",
        [
            "import_merchant_feed",
            "--feed",
            str(feed_path),
            "--mappings",
            str(mappings_path),
            "--offers",
            str(offers_path),
            "--unmatched",
            str(unmatched_path),
            "--invalid",
            str(invalid_path),
            "--dry-run",
        ],
    )

    main()

    output = capsys.readouterr().out
    assert "Mode: DRY-RUN" in output
    assert "Read: 1 | New: 1 | Updated: 0 | Unchanged: 0 | Unmatched: 0 | Invalid: 0" in output

    assert offers_path.read_text(encoding="utf-8") == original_offers
    assert unmatched_path.read_text(encoding="utf-8") == "KEEP-UNMATCHED"
    assert invalid_path.read_text(encoding="utf-8") == "KEEP-INVALID"


def test_authoritative_dry_run_reports_deactivation_without_writing(
    tmp_path,
    monkeypatch,
    capsys,
) -> None:
    mappings_path = tmp_path / "mappings.json"
    feed_path = tmp_path / "feed.json"
    offers_path = tmp_path / "offers.json"
    unmatched_path = tmp_path / "unmatched.json"
    invalid_path = tmp_path / "invalid.json"

    mappings_path.write_text(
        json.dumps(
            {
                "mappings": [
                    {
                        "product_id": PRODUCT_ID,
                        "merchant": "notino",
                        "merchant_product_id": "NOTINO-123",
                        "ean": None,
                        "gtin": None,
                    }
                ]
            }
        ),
        encoding="utf-8",
    )

    offers_path.write_text(
        json.dumps(
            {
                "offers": [
                    {
                        "offer_id": "notino-active",
                        "product_id": PRODUCT_ID,
                        "merchant_id": "notino-de",
                        "merchant_name": "Notino",
                        "merchant_product_id": "NOTINO-123",
                        "price": 89.95,
                        "currency": "EUR",
                        "shipping_cost": 0.0,
                        "in_stock": True,
                        "product_url": "https://example.com/active",
                        "affiliate_url": None,
                        "network": "CJ",
                        "data_source": "cj-feed",
                        "last_updated_at": "2026-09-16T12:00:00Z",
                    },
                    {
                        "offer_id": "notino-missing",
                        "product_id": PRODUCT_ID,
                        "merchant_id": "notino-de",
                        "merchant_name": "Notino",
                        "merchant_product_id": "NOTINO-456",
                        "price": 95.0,
                        "currency": "EUR",
                        "shipping_cost": 0.0,
                        "in_stock": True,
                        "product_url": "https://example.com/missing",
                        "affiliate_url": None,
                        "network": "CJ",
                        "data_source": "cj-feed",
                        "last_updated_at": "2026-09-16T12:00:00Z",
                    },
                ]
            }
        ),
        encoding="utf-8",
    )

    original_offers = offers_path.read_text(encoding="utf-8")

    feed_path.write_text(
        json.dumps(
            {
                "offers": [
                    {
                        "offer_id": "notino-active",
                        "merchant": "notino",
                        "merchant_id": "notino-de",
                        "merchant_name": "Notino",
                        "merchant_product_id": "NOTINO-123",
                        "price": 89.95,
                        "currency": "EUR",
                        "shipping_cost": 0.0,
                        "in_stock": True,
                        "product_url": "https://example.com/active",
                        "network": "CJ",
                        "data_source": "cj-feed",
                        "last_updated_at": "2026-09-17T12:00:00Z",
                    }
                ]
            }
        ),
        encoding="utf-8",
    )

    monkeypatch.setattr(
        sys,
        "argv",
        [
            "import_merchant_feed",
            "--feed",
            str(feed_path),
            "--mappings",
            str(mappings_path),
            "--offers",
            str(offers_path),
            "--unmatched",
            str(unmatched_path),
            "--invalid",
            str(invalid_path),
            "--dry-run",
            "--authoritative-merchant-id",
            "notino-de",
            "--authoritative-data-source",
            "cj-feed",
        ],
    )

    main()

    output = capsys.readouterr().out

    assert "Mode: DRY-RUN" in output
    assert "Deactivated: 1" in output

    assert offers_path.read_text(encoding="utf-8") == original_offers
    assert not unmatched_path.exists()
    assert not invalid_path.exists()


def test_cli_uses_selected_provider_adapter(
    tmp_path,
    monkeypatch,
    capsys,
) -> None:
    from retail.api import import_merchant_feed as import_command

    mappings_path = tmp_path / "mappings.json"
    feed_path = tmp_path / "feed.json"
    offers_path = tmp_path / "offers.json"

    mappings_path.write_text(
        json.dumps(
            {
                "mappings": [
                    {
                        "product_id": PRODUCT_ID,
                        "merchant": "notino",
                        "merchant_product_id": "NOTINO-123",
                        "ean": None,
                        "gtin": None,
                    }
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
                        "offer_id": "notino-test",
                        "merchant": "notino",
                        "merchant_id": "notino-de",
                        "merchant_name": "Notino",
                        "merchant_product_id": "NOTINO-123",
                        "price": 89.95,
                        "currency": "EUR",
                        "shipping_cost": 0.0,
                        "in_stock": True,
                        "product_url": "https://example.com/notino",
                        "network": "CJ",
                        "data_source": "test-feed",
                        "last_updated_at": "2026-09-17T12:00:00Z",
                    }
                ]
            }
        ),
        encoding="utf-8",
    )

    selected_providers = []
    original_adapter = import_command.adapt_provider_rows

    def tracked_adapter(provider, payloads):
        selected_providers.append(provider)
        return original_adapter(provider, payloads)

    monkeypatch.setattr(
        import_command,
        "adapt_provider_rows",
        tracked_adapter,
    )

    monkeypatch.setattr(
        sys,
        "argv",
        [
            "import_merchant_feed",
            "--feed",
            str(feed_path),
            "--mappings",
            str(mappings_path),
            "--offers",
            str(offers_path),
            "--provider",
            "canonical",
            "--dry-run",
        ],
    )

    import_command.main()

    output = capsys.readouterr().out

    assert selected_providers == ["canonical"]
    assert "Mode: DRY-RUN" in output
    assert "New: 1" in output


def test_authoritative_write_with_zero_matches_is_blocked(
    tmp_path,
    monkeypatch,
) -> None:
    mappings_path = tmp_path / "mappings.json"
    feed_path = tmp_path / "feed.json"
    offers_path = tmp_path / "offers.json"

    mappings_path.write_text(
        json.dumps(
            {
                "mappings": [
                    {
                        "product_id": PRODUCT_ID,
                        "merchant": "notino",
                        "merchant_product_id": "NOTINO-123",
                        "ean": None,
                        "gtin": None,
                    }
                ]
            }
        ),
        encoding="utf-8",
    )

    offers_path.write_text(
        json.dumps(
            {
                "offers": [
                    {
                        "offer_id": "notino-existing",
                        "product_id": PRODUCT_ID,
                        "merchant_id": "notino-de",
                        "merchant_name": "Notino",
                        "merchant_product_id": "NOTINO-123",
                        "price": 89.95,
                        "currency": "EUR",
                        "shipping_cost": 0.0,
                        "in_stock": True,
                        "product_url": "https://example.com/existing",
                        "affiliate_url": None,
                        "network": "CJ",
                        "data_source": "cj-feed",
                        "last_updated_at": "2026-09-16T12:00:00Z",
                    }
                ]
            }
        ),
        encoding="utf-8",
    )

    original_offers = offers_path.read_text(encoding="utf-8")

    feed_path.write_text(
        json.dumps(
            {
                "offers": [
                    {
                        "offer_id": "notino-unmapped",
                        "merchant": "notino",
                        "merchant_id": "notino-de",
                        "merchant_name": "Notino",
                        "merchant_product_id": "UNKNOWN-999",
                        "price": 49.95,
                        "currency": "EUR",
                        "shipping_cost": 0.0,
                        "in_stock": True,
                        "product_url": "https://example.com/unmapped",
                        "network": "CJ",
                        "data_source": "cj-feed",
                        "last_updated_at": "2026-09-17T12:00:00Z",
                    }
                ]
            }
        ),
        encoding="utf-8",
    )

    monkeypatch.setattr(
        sys,
        "argv",
        [
            "import_merchant_feed",
            "--feed",
            str(feed_path),
            "--mappings",
            str(mappings_path),
            "--offers",
            str(offers_path),
            "--authoritative-merchant-id",
            "notino-de",
            "--authoritative-data-source",
            "cj-feed",
        ],
    )

    with pytest.raises(SystemExit):
        main()

    assert offers_path.read_text(encoding="utf-8") == original_offers


def test_allow_empty_authoritative_can_intentionally_deactivate_all(
    tmp_path,
    monkeypatch,
    capsys,
) -> None:
    mappings_path = tmp_path / "mappings.json"
    feed_path = tmp_path / "feed.json"
    offers_path = tmp_path / "offers.json"
    unmatched_path = tmp_path / "unmatched.json"
    invalid_path = tmp_path / "invalid.json"

    mappings_path.write_text(
        json.dumps({"mappings": []}),
        encoding="utf-8",
    )

    feed_path.write_text(
        json.dumps({"offers": []}),
        encoding="utf-8",
    )

    offers_path.write_text(
        json.dumps(
            {
                "offers": [
                    {
                        "offer_id": "notino-existing",
                        "product_id": PRODUCT_ID,
                        "merchant_id": "notino-de",
                        "merchant_name": "Notino",
                        "merchant_product_id": "NOTINO-123",
                        "price": 89.95,
                        "currency": "EUR",
                        "shipping_cost": 0.0,
                        "in_stock": True,
                        "product_url": "https://example.com/existing",
                        "affiliate_url": None,
                        "network": "CJ",
                        "data_source": "cj-feed",
                        "last_updated_at": "2026-09-16T12:00:00Z",
                    }
                ]
            }
        ),
        encoding="utf-8",
    )

    monkeypatch.setattr(
        sys,
        "argv",
        [
            "import_merchant_feed",
            "--feed",
            str(feed_path),
            "--mappings",
            str(mappings_path),
            "--offers",
            str(offers_path),
            "--unmatched",
            str(unmatched_path),
            "--invalid",
            str(invalid_path),
            "--authoritative-merchant-id",
            "notino-de",
            "--authoritative-data-source",
            "cj-feed",
            "--allow-empty-authoritative",
        ],
    )

    main()

    output = capsys.readouterr().out
    assert "Deactivated: 1" in output

    saved = json.loads(offers_path.read_text(encoding="utf-8"))
    assert saved["offers"][0]["in_stock"] is False
