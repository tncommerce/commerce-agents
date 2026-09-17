from __future__ import annotations

import json
from pathlib import Path

from pydantic import BaseModel

from .merchant_offers import MerchantOffer

class MerchantProductMapping(BaseModel):
    product_id: str
    merchant: str
    merchant_product_id: str | None = None
    ean: str | None = None
    gtin: str | None = None


def load_product_mappings(path: Path) -> list[MerchantProductMapping]:
    raw = json.loads(path.read_text(encoding="utf-8-sig"))
    rows = raw.get("mappings", [])
    return [MerchantProductMapping.model_validate(row) for row in rows]


def _same_identifier(left: str | None, right: str | None) -> bool:
    if not left or not right:
        return False
    return left.strip().casefold() == right.strip().casefold()


def resolve_product_id(
    mappings: list[MerchantProductMapping],
    *,
    merchant: str,
    merchant_product_id: str | None = None,
    ean: str | None = None,
    gtin: str | None = None,
) -> str | None:
    merchant_key = merchant.strip().casefold()

    for mapping in mappings:
        if mapping.merchant.strip().casefold() != merchant_key:
            continue

        if _same_identifier(mapping.merchant_product_id, merchant_product_id):
            return mapping.product_id

        if _same_identifier(mapping.ean, ean):
            return mapping.product_id

        if _same_identifier(mapping.gtin, gtin):
            return mapping.product_id

    return None

def validate_offer_payload(payload: dict) -> MerchantOffer:
    return MerchantOffer.model_validate(payload)
class MerchantFeedRow(BaseModel):
    offer_id: str
    merchant: str
    merchant_id: str
    merchant_name: str
    merchant_product_id: str | None = None
    ean: str | None = None
    gtin: str | None = None
    price: float
    currency: str = "EUR"
    shipping_cost: float | None = None
    shipping_label: str | None = None
    in_stock: bool = False
    variant_label: str | None = None
    product_url: str
    affiliate_url: str | None = None
    network: str | None = None
    data_source: str | None = None
    last_updated_at: str
    commission_rate: float | None = None


def normalize_feed_row(
    payload: dict,
    mappings: list[MerchantProductMapping],
) -> MerchantOffer | None:
    row = MerchantFeedRow.model_validate(payload)

    product_id = resolve_product_id(
        mappings,
        merchant=row.merchant,
        merchant_product_id=row.merchant_product_id,
        ean=row.ean,
        gtin=row.gtin,
    )

    if product_id is None:
        return None

    return MerchantOffer.model_validate(
        {
            "offer_id": row.offer_id,
            "product_id": product_id,
            "merchant_id": row.merchant_id,
            "merchant_name": row.merchant_name,
            "merchant_product_id": row.merchant_product_id,
            "price": row.price,
            "currency": row.currency,
            "shipping_cost": row.shipping_cost,
            "shipping_label": row.shipping_label,
            "in_stock": row.in_stock,
            "variant_label": row.variant_label,
            "product_url": row.product_url,
            "affiliate_url": row.affiliate_url,
            "network": row.network,
            "data_source": row.data_source,
            "last_updated_at": row.last_updated_at,
            "commission_rate": row.commission_rate,
        }
    )
class UnmatchedFeedRow(BaseModel):
    offer_id: str
    merchant: str
    merchant_product_id: str | None = None
    ean: str | None = None
    gtin: str | None = None
    reason: str = "product_mapping_not_found"


class FeedImportResult(BaseModel):
    offers: list[MerchantOffer]
    unmatched: list[UnmatchedFeedRow]


def import_feed_rows(
    payloads: list[dict],
    mappings: list[MerchantProductMapping],
) -> FeedImportResult:
    offers: list[MerchantOffer] = []
    unmatched: list[UnmatchedFeedRow] = []

    for payload in payloads:
        row = MerchantFeedRow.model_validate(payload)
        offer = normalize_feed_row(payload, mappings)

        if offer is None:
            unmatched.append(
                UnmatchedFeedRow(
                    offer_id=row.offer_id,
                    merchant=row.merchant,
                    merchant_product_id=row.merchant_product_id,
                    ean=row.ean,
                    gtin=row.gtin,
                )
            )
            continue

        offers.append(offer)

    return FeedImportResult(
        offers=offers,
        unmatched=unmatched,
    )