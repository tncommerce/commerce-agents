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
    assert (
        saved_invalid["invalid"][0]["reason"]
        == "provider_contract_invalid"
    )


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


def test_write_import_creates_audit_report_but_dry_run_does_not(
    tmp_path,
    monkeypatch,
    capsys,
) -> None:
    mappings_path = tmp_path / "mappings.json"
    feed_path = tmp_path / "feed.json"
    offers_path = tmp_path / "offers.json"
    unmatched_path = tmp_path / "unmatched.json"
    invalid_path = tmp_path / "invalid.json"
    run_report_path = tmp_path / "runs.jsonl"

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
                        "offer_id": "notino-audit-test",
                        "merchant": "notino",
                        "merchant_id": "notino-de",
                        "merchant_name": "Notino",
                        "merchant_product_id": "NOTINO-123",
                        "price": 89.95,
                        "currency": "EUR",
                        "shipping_cost": 0.0,
                        "in_stock": True,
                        "product_url": "https://example.com/notino",
                        "affiliate_url": "https://example.com/affiliate/notino",
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
            "--run-report",
            str(run_report_path),
            "--provider",
            "canonical",
        ],
    )

    main()

    write_output = capsys.readouterr().out
    assert "Mode: WRITE" in write_output
    assert "Run ID:" in write_output

    lines = run_report_path.read_text(
        encoding="utf-8"
    ).splitlines()

    assert len(lines) == 1

    saved = json.loads(lines[0])

    assert saved["run_id"]
    assert saved["provider"] == "canonical"
    assert saved["mode"] == "WRITE"
    assert saved["read"] == 1
    assert saved["new"] == 1
    assert saved["updated"] == 0
    assert saved["unchanged"] == 0
    assert saved["unmatched"] == 0
    assert saved["invalid"] == 0
    assert saved["deactivated"] == 0

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
            "--run-report",
            str(run_report_path),
            "--provider",
            "canonical",
            "--dry-run",
        ],
    )

    main()

    dry_run_output = capsys.readouterr().out
    assert "Mode: DRY-RUN" in dry_run_output

    lines_after_dry_run = run_report_path.read_text(
        encoding="utf-8"
    ).splitlines()

    assert len(lines_after_dry_run) == 1


def test_cli_returns_zero_for_clean_import(
    tmp_path,
    monkeypatch,
    capsys,
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

    feed_path.write_text(
        json.dumps(
            {
                "offers": [
                    {
                        "offer_id": "notino-clean",
                        "merchant": "notino",
                        "merchant_id": "notino-de",
                        "merchant_name": "Notino",
                        "merchant_product_id": "NOTINO-123",
                        "price": 89.95,
                        "currency": "EUR",
                        "shipping_cost": 0.0,
                        "in_stock": True,
                        "product_url": "https://example.com/clean",
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
        ],
    )

    exit_code = main()
    output = capsys.readouterr().out

    assert exit_code == 0
    assert "Status: OK" in output


def test_cli_returns_review_exit_code_and_machine_json(
    tmp_path,
    monkeypatch,
    capsys,
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

    feed_path.write_text(
        json.dumps(
            {
                "offers": [
                    {
                        "offer_id": "notino-clean",
                        "merchant": "notino",
                        "merchant_id": "notino-de",
                        "merchant_name": "Notino",
                        "merchant_product_id": "NOTINO-123",
                        "price": 89.95,
                        "currency": "EUR",
                        "shipping_cost": 0.0,
                        "in_stock": True,
                        "product_url": "https://example.com/clean",
                        "network": "CJ",
                        "data_source": "cj-feed",
                        "last_updated_at": "2026-09-17T12:00:00Z",
                    },
                    {
                        "offer_id": "notino-unmatched",
                        "merchant": "notino",
                        "merchant_id": "notino-de",
                        "merchant_name": "Notino",
                        "merchant_product_id": "UNKNOWN-999",
                        "price": 49.95,
                        "currency": "EUR",
                        "shipping_cost": 0.0,
                        "in_stock": True,
                        "product_url": "https://example.com/unmatched",
                        "network": "CJ",
                        "data_source": "cj-feed",
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
            "--machine-readable",
        ],
    )

    exit_code = main()
    output = capsys.readouterr().out.strip()
    payload = json.loads(output)

    assert exit_code == 10
    assert payload["status"] == "review"
    assert payload["exit_code"] == 10
    assert "unmatched_rows" in payload["reasons"]
    assert payload["run"]["unmatched"] == 1
    assert payload["run"]["run_id"]


def test_provider_contract_blocks_row_before_product_mapping(
    tmp_path,
    monkeypatch,
    capsys,
) -> None:
    from retail.api import import_merchant_feed as import_command
    from retail.api.merchant_providers import (
        MappedMerchantFeedAdapter,
        register_provider_adapter,
    )

    mappings_path = tmp_path / "mappings.json"
    feed_path = tmp_path / "feed.json"
    offers_path = tmp_path / "offers.json"

    mappings_path.write_text(
        json.dumps(
            {
                "mappings": [
                    {
                        "product_id": PRODUCT_ID,
                        "merchant": "fixture-shop",
                        "merchant_product_id": "SKU-123",
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
                        "external_offer": "offer-123",
                        "external_sku": "SKU-123",
                        "external_price": 89.95,
                        "external_url":
                            "https://example.com/product",
                        "external_updated":
                            "2026-09-17T18:00:00Z",
                    }
                ]
            }
        ),
        encoding="utf-8",
    )

    offers_path.write_text(
        json.dumps({"offers": []}),
        encoding="utf-8",
    )

    adapter = MappedMerchantFeedAdapter(
        provider_name="fixture-contract-gate",
        field_map={
            "offer_id": "external_offer",
            "merchant_product_id": "external_sku",
            "price": "external_price",
            "product_url": "external_url",
            "last_updated_at": "external_updated",
        },
        constants={
            "merchant": "fixture-shop",
            "merchant_id": "fixture-de",
            "merchant_name": "Fixture Shop",
            "currency": "EUR",
            "data_source": "fixture-feed",
        },
    )

    register_provider_adapter(
        adapter,
        replace=True,
    )

    received_rows = []
    original_import = import_command.import_feed_rows

    def tracked_import(payloads, mappings):
        received_rows.append(list(payloads))
        return original_import(
            payloads,
            mappings,
        )

    monkeypatch.setattr(
        import_command,
        "import_feed_rows",
        tracked_import,
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
            "fixture-contract-gate",
            "--dry-run",
        ],
    )

    import_command.main()

    output = capsys.readouterr().out

    assert received_rows == [[]]
    assert "Read: 1" in output
    assert "Unmatched: 0" in output
    assert "Invalid: 1" in output


def test_import_command_reads_csv_feed(
    tmp_path,
    monkeypatch,
    capsys,
) -> None:
    mappings_path = tmp_path / "mappings.json"
    feed_path = tmp_path / "feed.csv"
    offers_path = tmp_path / "offers.json"

    mappings_path.write_text(
        json.dumps(
            {
                "mappings": [
                    {
                        "product_id": PRODUCT_ID,
                        "merchant": "notino",
                        "merchant_product_id": "NOTINO-CSV-123",
                        "ean": None,
                        "gtin": None,
                    }
                ]
            }
        ),
        encoding="utf-8",
    )

    feed_path.write_text(
        (
            "offer_id,merchant,merchant_id,merchant_name,"
            "merchant_product_id,price,currency,in_stock,"
            "product_url,last_updated_at,data_source,network\n"
            "notino-csv-offer,notino,notino-de,Notino,"
            "NOTINO-CSV-123,89.95,EUR,true,"
            "https://example.com/csv-product,"
            "2026-09-17T18:00:00Z,csv-test-feed,CJ\n"
        ),
        encoding="utf-8",
    )

    offers_path.write_text(
        json.dumps({"offers": []}),
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
            "--dry-run",
        ],
    )

    main()

    output = capsys.readouterr().out

    assert "Mode: DRY-RUN" in output
    assert "Read: 1" in output
    assert "New: 1" in output
    assert "Unmatched: 0" in output
    assert "Invalid: 0" in output


@pytest.mark.parametrize(
    "delimiter",
    [";", "\t"],
)
def test_import_command_accepts_realistic_csv_delimiters(
    tmp_path,
    monkeypatch,
    capsys,
    delimiter,
) -> None:
    mappings_path = tmp_path / "mappings.json"
    feed_path = tmp_path / "feed.csv"
    offers_path = tmp_path / "offers.json"

    mappings_path.write_text(
        json.dumps(
            {
                "mappings": [
                    {
                        "product_id": PRODUCT_ID,
                        "merchant": "notino",
                        "merchant_product_id": "NOTINO-DELIM-123",
                        "ean": None,
                        "gtin": None,
                    }
                ]
            }
        ),
        encoding="utf-8",
    )

    header = delimiter.join(
        [
            "offer_id",
            "merchant",
            "merchant_id",
            "merchant_name",
            "merchant_product_id",
            "price",
            "currency",
            "in_stock",
            "product_url",
            "last_updated_at",
            "data_source",
            "network",
        ]
    )

    row = delimiter.join(
        [
            "notino-delimiter-offer",
            "notino",
            "notino-de",
            "Notino",
            "NOTINO-DELIM-123",
            "89.95",
            "EUR",
            "true",
            "https://example.com/delimiter-product",
            "2026-09-17T18:00:00Z",
            "delimiter-test-feed",
            "CJ",
        ]
    )

    feed_path.write_text(
        header + "\n" + row + "\n",
        encoding="utf-8",
    )

    offers_path.write_text(
        json.dumps({"offers": []}),
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
            "--dry-run",
        ],
    )

    main()

    output = capsys.readouterr().out

    assert "Mode: DRY-RUN" in output
    assert "Read: 1" in output
    assert "New: 1" in output
    assert "Unmatched: 0" in output
    assert "Invalid: 0" in output


def test_duplicate_offer_ids_block_import_before_write(
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
                        "merchant_product_id": "NOTINO-DUP-123",
                        "ean": None,
                        "gtin": None,
                    }
                ]
            }
        ),
        encoding="utf-8",
    )

    base_offer = {
        "offer_id": "duplicate-offer",
        "merchant": "notino",
        "merchant_id": "notino-de",
        "merchant_name": "Notino",
        "merchant_product_id": "NOTINO-DUP-123",
        "price": 89.95,
        "currency": "EUR",
        "in_stock": True,
        "product_url": "https://example.com/product",
        "last_updated_at": "2026-09-17T18:00:00Z",
        "data_source": "duplicate-test-feed",
    }

    second_offer = dict(base_offer)
    second_offer["price"] = 79.95

    feed_path.write_text(
        json.dumps(
            {
                "offers": [
                    base_offer,
                    second_offer,
                ]
            }
        ),
        encoding="utf-8",
    )

    offers_path.write_text(
        json.dumps({"offers": []}),
        encoding="utf-8",
    )

    original = offers_path.read_text(
        encoding="utf-8"
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
        ],
    )

    with pytest.raises(SystemExit) as exc:
        main()

    assert exc.value.code == 2
    assert (
        offers_path.read_text(encoding="utf-8")
        == original
    )


def test_import_command_blocks_feed_over_row_limit(
    tmp_path,
    monkeypatch,
) -> None:
    mappings_path = tmp_path / "mappings.json"
    feed_path = tmp_path / "feed.json"
    offers_path = tmp_path / "offers.json"

    mappings_path.write_text(
        json.dumps({"mappings": []}),
        encoding="utf-8",
    )

    feed_path.write_text(
        json.dumps(
            {
                "offers": [
                    {"offer_id": "offer-1"},
                    {"offer_id": "offer-2"},
                ]
            }
        ),
        encoding="utf-8",
    )

    offers_path.write_text(
        json.dumps({"offers": []}),
        encoding="utf-8",
    )

    original = offers_path.read_text(
        encoding="utf-8"
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
            "--max-feed-rows",
            "1",
        ],
    )

    with pytest.raises(SystemExit) as exc:
        main()

    assert exc.value.code == 2
    assert (
        offers_path.read_text(encoding="utf-8")
        == original
    )


def test_machine_readable_run_contains_snapshot_hashes(
    tmp_path,
    monkeypatch,
    capsys,
) -> None:
    from retail.api.merchant_feed_snapshot import (
        file_sha256,
    )

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
                        "merchant_product_id": "NOTINO-SNAPSHOT-123",
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
                        "offer_id": "snapshot-offer",
                        "merchant": "notino",
                        "merchant_id": "notino-de",
                        "merchant_name": "Notino",
                        "merchant_product_id": "NOTINO-SNAPSHOT-123",
                        "price": 89.95,
                        "currency": "EUR",
                        "in_stock": True,
                        "product_url": "https://example.com/snapshot",
                        "last_updated_at": "2026-09-17T18:00:00Z",
                        "data_source": "snapshot-test-feed",
                    }
                ]
            }
        ),
        encoding="utf-8",
    )

    offers_path.write_text(
        json.dumps({"offers": []}),
        encoding="utf-8",
    )

    expected_feed_hash = file_sha256(feed_path)
    expected_mappings_hash = file_sha256(mappings_path)

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
            "--dry-run",
            "--machine-readable",
        ],
    )

    exit_code = main()

    payload = json.loads(
        capsys.readouterr().out
    )

    assert exit_code == 0
    assert payload["run"]["feed_sha256"] == expected_feed_hash
    assert (
        payload["run"]["mappings_sha256"]
        == expected_mappings_hash
    )


def test_import_aborts_if_feed_changes_during_processing(
    tmp_path,
    monkeypatch,
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
                        "merchant_product_id": "NOTINO-STABLE-123",
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
                        "offer_id": "stable-offer",
                        "merchant": "notino",
                        "merchant_id": "notino-de",
                        "merchant_name": "Notino",
                        "merchant_product_id": "NOTINO-STABLE-123",
                        "price": 89.95,
                        "currency": "EUR",
                        "in_stock": True,
                        "product_url": "https://example.com/stable",
                        "last_updated_at": "2026-09-17T18:00:00Z",
                        "data_source": "stability-test-feed",
                    }
                ]
            }
        ),
        encoding="utf-8",
    )

    offers_path.write_text(
        json.dumps({"offers": []}),
        encoding="utf-8",
    )

    original_offers = offers_path.read_text(
        encoding="utf-8"
    )

    original_import = import_command.import_feed_rows

    def changing_import(payloads, mappings):
        result = original_import(
            payloads,
            mappings,
        )

        feed_path.write_text(
            json.dumps(
                {
                    "offers": [
                        {
                            "offer_id": "changed-mid-run"
                        }
                    ]
                }
            ),
            encoding="utf-8",
        )

        return result

    monkeypatch.setattr(
        import_command,
        "import_feed_rows",
        changing_import,
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
        ],
    )

    with pytest.raises(SystemExit) as exc:
        import_command.main()

    assert exc.value.code == 2
    assert (
        offers_path.read_text(encoding="utf-8")
        == original_offers
    )
