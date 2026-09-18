from __future__ import annotations

from datetime import datetime

from pydantic import (
    BaseModel,
    Field,
    ValidationError,
    model_validator,
)


class MerchantProviderCanonicalRow(BaseModel):
    offer_id: str = Field(min_length=1)
    merchant: str = Field(min_length=1)
    merchant_id: str = Field(min_length=1)
    merchant_name: str = Field(min_length=1)

    merchant_product_id: str | None = None
    ean: str | None = None
    gtin: str | None = None

    price: float = Field(ge=0)
    currency: str = Field(min_length=3, max_length=3)
    in_stock: bool

    product_url: str = Field(min_length=1)
    last_updated_at: datetime
    data_source: str = Field(min_length=1)

    @model_validator(mode="after")
    def require_product_identifier(
        self,
    ) -> "MerchantProviderCanonicalRow":
        identifiers = (
            self.merchant_product_id,
            self.ean,
            self.gtin,
        )

        if not any(
            value is not None and value.strip()
            for value in identifiers
        ):
            raise ValueError(
                "product_identifier_required"
            )

        return self


class ProviderContractIssue(BaseModel):
    row_index: int
    offer_id: str | None = None
    reason: str = "provider_contract_invalid"
    error: str


class ProviderContractResult(BaseModel):
    rows: list[dict]
    invalid: list[ProviderContractIssue]


def validate_provider_contract_rows(
    payloads: list[dict],
) -> ProviderContractResult:
    valid_rows: list[dict] = []
    invalid: list[ProviderContractIssue] = []

    for row_index, payload in enumerate(payloads):
        try:
            MerchantProviderCanonicalRow.model_validate(
                payload
            )
        except ValidationError as exc:
            invalid.append(
                ProviderContractIssue(
                    row_index=row_index,
                    offer_id=payload.get("offer_id"),
                    error=str(exc),
                )
            )
            continue

        valid_rows.append(
            dict(payload)
        )

    return ProviderContractResult(
        rows=valid_rows,
        invalid=invalid,
    )
