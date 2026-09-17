import pytest

from retail.api.merchant_providers import (
    MappedMerchantFeedAdapter,
    adapt_provider_rows,
    available_providers,
    get_provider_adapter,
    register_provider_adapter,
)


def test_canonical_provider_preserves_feed_rows() -> None:
    rows = [
        {
            "offer_id": "test-offer",
            "merchant": "notino",
            "price": 89.95,
        }
    ]

    adapted = adapt_provider_rows("canonical", rows)

    assert adapted == rows
    assert adapted is not rows
    assert adapted[0] is not rows[0]
    assert "canonical" in available_providers()


def test_unknown_provider_is_rejected() -> None:
    with pytest.raises(
        ValueError,
        match="Unsupported merchant feed provider",
    ):
        get_provider_adapter("unknown-provider")


def test_mapped_provider_converts_external_fields() -> None:
    adapter = MappedMerchantFeedAdapter(
        provider_name="fixture-network",
        field_map={
            "offer_id": "external_offer",
            "merchant_product_id": "external_sku",
            "price": "external_price",
            "product_url": "external_url",
        },
        constants={
            "merchant": "fixture-shop",
            "merchant_id": "fixture-de",
            "merchant_name": "Fixture Shop",
            "currency": "EUR",
            "network": "fixture-network",
            "data_source": "fixture-feed",
        },
    )

    register_provider_adapter(adapter)

    rows = adapt_provider_rows(
        "fixture-network",
        [
            {
                "external_offer": "offer-123",
                "external_sku": "sku-456",
                "external_price": 89.95,
                "external_url":
                    "https://example.com/product",
            }
        ],
    )

    assert rows == [
        {
            "offer_id": "offer-123",
            "merchant_product_id": "sku-456",
            "price": 89.95,
            "product_url":
                "https://example.com/product",
            "merchant": "fixture-shop",
            "merchant_id": "fixture-de",
            "merchant_name": "Fixture Shop",
            "currency": "EUR",
            "network": "fixture-network",
            "data_source": "fixture-feed",
        }
    ]


def test_registered_provider_becomes_available() -> None:
    adapter = MappedMerchantFeedAdapter(
        provider_name="fixture-available",
        field_map={},
    )

    register_provider_adapter(adapter)

    assert "fixture-available" in available_providers()
    assert (
        get_provider_adapter("FIXTURE-AVAILABLE")
        is adapter
    )


def test_duplicate_provider_registration_is_blocked() -> None:
    adapter = MappedMerchantFeedAdapter(
        provider_name="fixture-duplicate",
        field_map={},
    )

    register_provider_adapter(adapter)

    with pytest.raises(
        ValueError,
        match="already registered",
    ):
        register_provider_adapter(adapter)
