import json

from retail.api.merchant_import import (
    MerchantProductMapping,
    import_feed_rows,
    load_product_mappings,
    normalize_feed_row,
    resolve_product_id,
    upsert_offers_file,
    validate_offer_payload,
)

PRODUCT_ID = "SC-ESSENTIAL-PARFUMS-BOIS-IMPERIAL-100"


def test_load_product_mappings_accepts_utf8_bom(tmp_path) -> None:
    path = tmp_path / "merchant_product_mappings.json"
    path.write_text(
        json.dumps(
            {
                "mappings": [
                    {
                        "product_id": PRODUCT_ID,
                        "merchant": "notino",
                        "merchant_product_id": "NOTINO-123",
                        "ean": "1234567890123",
                        "gtin": None,
                    }
                ]
            }
        ),
        encoding="utf-8-sig",
    )

    mappings = load_product_mappings(path)

    assert len(mappings) == 1
    assert mappings[0].product_id == PRODUCT_ID
    assert mappings[0].merchant == "notino"


def test_resolve_product_id_uses_known_identifiers() -> None:
    mappings = [
        MerchantProductMapping(
            product_id=PRODUCT_ID,
            merchant="notino",
            merchant_product_id="NOTINO-123",
            ean="1234567890123",
            gtin="00012345678905",
        )
    ]

    assert (
        resolve_product_id(
            mappings,
            merchant="NOTINO",
            merchant_product_id=" NOTINO-123 ",
        )
        == PRODUCT_ID
    )

    assert (
        resolve_product_id(
            mappings,
            merchant="notino",
            ean="1234567890123",
        )
        == PRODUCT_ID
    )

    assert (
        resolve_product_id(
            mappings,
            merchant="notino",
            gtin="00012345678905",
        )
        == PRODUCT_ID
    )


def test_resolve_product_id_does_not_cross_merchants() -> None:
    mappings = [
        MerchantProductMapping(
            product_id=PRODUCT_ID,
            merchant="notino",
            ean="1234567890123",
        )
    ]

    assert (
        resolve_product_id(
            mappings,
            merchant="douglas",
            ean="1234567890123",
        )
        is None
    )


def test_validate_offer_payload_returns_merchant_offer() -> None:
    offer = validate_offer_payload(
        {
            "offer_id": "notino-bois-imperial-100",
            "product_id": PRODUCT_ID,
            "merchant_id": "notino-de",
            "merchant_name": "Notino",
            "merchant_product_id": "NOTINO-123",
            "price": 94.0,
            "currency": "EUR",
            "shipping_cost": 0.0,
            "shipping_label": "Kostenloser Versand",
            "in_stock": True,
            "variant_label": "100 ml",
            "product_url": "https://example.com/bois-imperial",
            "affiliate_url": None,
            "network": "CJ",
            "data_source": "test-feed",
            "last_updated_at": "2026-09-17T12:00:00Z",
            "commission_rate": None,
        }
    )

    assert offer.product_id == PRODUCT_ID
    assert offer.merchant_name == "Notino"
    assert offer.price == 94.0

def test_normalize_feed_row_creates_offer_for_known_product() -> None:
    mappings = [
        MerchantProductMapping(
            product_id=PRODUCT_ID,
            merchant="notino",
            merchant_product_id="NOTINO-123",
            ean="1234567890123",
        )
    ]

    offer = normalize_feed_row(
        {
            "offer_id": "notino-bois-imperial-100",
            "merchant": "notino",
            "merchant_id": "notino-de",
            "merchant_name": "Notino",
            "merchant_product_id": "NOTINO-123",
            "ean": "1234567890123",
            "price": 89.95,
            "currency": "EUR",
            "shipping_cost": 0.0,
            "shipping_label": "Kostenloser Versand",
            "in_stock": True,
            "variant_label": "100 ml",
            "product_url": "https://example.com/bois-imperial",
            "affiliate_url": "https://example.com/affiliate/bois-imperial",
            "network": "CJ",
            "data_source": "cj-feed",
            "last_updated_at": "2026-09-17T12:00:00Z",
            "commission_rate": 0.05,
        },
        mappings,
    )

    assert offer is not None
    assert offer.product_id == PRODUCT_ID
    assert offer.merchant_name == "Notino"
    assert offer.price == 89.95
    assert offer.affiliate_url == "https://example.com/affiliate/bois-imperial"


def test_normalize_feed_row_skips_unknown_product() -> None:
    mappings = [
        MerchantProductMapping(
            product_id=PRODUCT_ID,
            merchant="notino",
            merchant_product_id="NOTINO-123",
        )
    ]

    offer = normalize_feed_row(
        {
            "offer_id": "notino-unknown-product",
            "merchant": "notino",
            "merchant_id": "notino-de",
            "merchant_name": "Notino",
            "merchant_product_id": "UNKNOWN-999",
            "price": 50.0,
            "currency": "EUR",
            "shipping_cost": 0.0,
            "in_stock": True,
            "product_url": "https://example.com/unknown",
            "network": "CJ",
            "data_source": "cj-feed",
            "last_updated_at": "2026-09-17T12:00:00Z",
        },
        mappings,
    )

    assert offer is None

def test_import_feed_rows_separates_matched_and_unmatched() -> None:
    mappings = [
        MerchantProductMapping(
            product_id=PRODUCT_ID,
            merchant="notino",
            merchant_product_id="NOTINO-123",
        )
    ]

    result = import_feed_rows(
        [
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
                "affiliate_url": "https://example.com/affiliate/bois-imperial",
                "network": "CJ",
                "data_source": "cj-feed",
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
                "data_source": "cj-feed",
                "last_updated_at": "2026-09-17T12:00:00Z",
            },
        ],
        mappings,
    )

    assert len(result.offers) == 1
    assert result.offers[0].product_id == PRODUCT_ID
    assert len(result.unmatched) == 1
    assert result.unmatched[0].offer_id == "notino-unknown"
    assert result.unmatched[0].reason == "product_mapping_not_found"


def test_upsert_offers_file_updates_existing_and_adds_new(tmp_path) -> None:
    path = tmp_path / "merchant_offers.json"

    path.write_text(
        json.dumps(
            {
                "offers": [
                    {
                        "offer_id": "douglas-bois-imperial-100",
                        "product_id": PRODUCT_ID,
                        "merchant_id": "douglas-de",
                        "merchant_name": "Douglas",
                        "merchant_product_id": "1068008",
                        "price": 94.0,
                        "currency": "EUR",
                        "shipping_cost": 0.0,
                        "in_stock": True,
                        "product_url": "https://example.com/douglas",
                        "affiliate_url": None,
                        "network": "Awin",
                        "data_source": "old-feed",
                        "last_updated_at": "2026-09-15T12:00:00Z",
                    }
                ]
            }
        ),
        encoding="utf-8",
    )

    updated_douglas = validate_offer_payload(
        {
            "offer_id": "douglas-bois-imperial-100",
            "product_id": PRODUCT_ID,
            "merchant_id": "douglas-de",
            "merchant_name": "Douglas",
            "merchant_product_id": "1068008",
            "price": 89.0,
            "currency": "EUR",
            "shipping_cost": 0.0,
            "in_stock": True,
            "product_url": "https://example.com/douglas",
            "affiliate_url": "https://example.com/douglas-affiliate",
            "network": "Awin",
            "data_source": "awin-feed",
            "last_updated_at": "2026-09-17T12:00:00Z",
        }
    )

    notino = validate_offer_payload(
        {
            "offer_id": "notino-bois-imperial-100",
            "product_id": PRODUCT_ID,
            "merchant_id": "notino-de",
            "merchant_name": "Notino",
            "merchant_product_id": "NOTINO-123",
            "price": 91.0,
            "currency": "EUR",
            "shipping_cost": 0.0,
            "in_stock": True,
            "product_url": "https://example.com/notino",
            "affiliate_url": "https://example.com/notino-affiliate",
            "network": "CJ",
            "data_source": "cj-feed",
            "last_updated_at": "2026-09-17T12:00:00Z",
        }
    )

    upsert_offers_file(path, [updated_douglas, notino])

    saved = json.loads(path.read_text(encoding="utf-8"))
    offers = saved["offers"]

    assert len(offers) == 2

    by_id = {offer["offer_id"]: offer for offer in offers}

    assert by_id["douglas-bois-imperial-100"]["price"] == 89.0
    assert by_id["douglas-bois-imperial-100"]["data_source"] == "awin-feed"
    assert by_id["douglas-bois-imperial-100"]["affiliate_url"] == "https://example.com/douglas-affiliate"

    assert by_id["notino-bois-imperial-100"]["merchant_name"] == "Notino"
    assert by_id["notino-bois-imperial-100"]["network"] == "CJ"


def test_import_feed_rows_continues_after_invalid_row() -> None:
    mappings = [
        MerchantProductMapping(
            product_id=PRODUCT_ID,
            merchant="notino",
            merchant_product_id="NOTINO-123",
        )
    ]

    result = import_feed_rows(
        [
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
                "data_source": "cj-feed",
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
                "data_source": "cj-feed",
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
        ],
        mappings,
    )

    assert len(result.offers) == 1
    assert result.offers[0].offer_id == "notino-bois-imperial-100"

    assert len(result.unmatched) == 1
    assert result.unmatched[0].offer_id == "notino-unknown"

    assert len(result.invalid) == 1
    assert result.invalid[0].row_index == 2
    assert result.invalid[0].offer_id == "broken-row"
    assert result.invalid[0].reason == "invalid_feed_row"
