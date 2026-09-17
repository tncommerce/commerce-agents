import pytest

from retail.api.merchant_providers import (
    adapt_provider_rows,
    available_providers,
    get_provider_adapter,
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
