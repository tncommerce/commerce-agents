from retail.api.merchant_provider_contract import (
    validate_provider_contract_rows,
)


def _valid_row():
    return {
        "offer_id": "offer-123",
        "merchant": "fixture-shop",
        "merchant_id": "fixture-de",
        "merchant_name": "Fixture Shop",
        "merchant_product_id": "sku-456",
        "price": 89.95,
        "currency": "EUR",
        "in_stock": True,
        "product_url": "https://example.com/product",
        "last_updated_at": "2026-09-17T18:00:00Z",
        "data_source": "fixture-feed",
    }


def test_provider_contract_accepts_complete_row() -> None:
    row = _valid_row()

    result = validate_provider_contract_rows([row])

    assert result.rows == [row]
    assert result.invalid == []


def test_provider_contract_rejects_missing_stock_state() -> None:
    row = _valid_row()
    row.pop("in_stock")

    result = validate_provider_contract_rows([row])

    assert result.rows == []
    assert len(result.invalid) == 1
    assert result.invalid[0].row_index == 0
    assert result.invalid[0].offer_id == "offer-123"
    assert result.invalid[0].reason == "provider_contract_invalid"


def test_provider_contract_requires_product_identifier() -> None:
    row = _valid_row()
    row.pop("merchant_product_id")

    result = validate_provider_contract_rows([row])

    assert result.rows == []
    assert len(result.invalid) == 1
    assert "product_identifier_required" in (result.invalid[0].error)
