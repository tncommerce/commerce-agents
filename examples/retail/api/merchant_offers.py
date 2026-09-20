from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from uuid import uuid4

from pydantic import BaseModel, Field


class MerchantOffer(BaseModel):
    """One purchasable offer for a catalog product.

    Product/fragrance knowledge stays in catalog.json. Merchant-specific commerce
    data lives here so price, stock and tracking can change independently.
    """

    offer_id: str
    product_id: str
    merchant_id: str
    merchant_name: str
    merchant_product_id: str | None = None
    price: float = Field(gt=0)
    currency: str = "EUR"
    shipping_cost: float | None = Field(default=None, ge=0)
    shipping_label: str | None = None
    in_stock: bool = False
    variant_label: str | None = None
    product_url: str
    affiliate_url: str | None = None
    network: str | None = None
    data_source: str | None = None
    last_updated_at: datetime

    # Internal economics only. Never use this as a customer ranking signal.
    # It may be retained for reporting and analytics but does not affect
    # product recommendations or merchant-offer ordering.
    commission_rate: float | None = Field(default=None, ge=0)


def _as_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)


def offer_age_hours(offer: MerchantOffer, *, now: datetime | None = None) -> float:
    reference = _as_utc(now or datetime.now(UTC))
    checked = _as_utc(offer.last_updated_at)
    return max((reference - checked).total_seconds() / 3600.0, 0.0)


def offer_total_price(offer: MerchantOffer) -> float | None:
    """Known customer total.

    Unknown shipping is intentionally not treated as zero because that could make a
    seemingly cheaper merchant win on incomplete data.
    """

    if offer.shipping_cost is None:
        return None
    return round(offer.price + offer.shipping_cost, 2)


def rank_offers(
    offers: list[MerchantOffer],
    *,
    now: datetime | None = None,
    max_age_hours: float = 72.0,
) -> list[MerchantOffer]:
    """Return customer-eligible offers in trust-first order.

    V1 ranking rules:
    1. exact catalog product match is guaranteed by product_id
    2. out-of-stock offers are excluded
    3. stale offers are excluded
    4. offers with a known customer total outrank unknown shipping
    5. lower customer total wins
    6. materially fresher data wins before monetization
    7. within the same freshness band, the more recently updated offer wins
    8. merchant name provides a deterministic final tie-breaker

    Commission is never used as a ranking signal.
    """

    reference = _as_utc(now or datetime.now(UTC))
    eligible = [
        offer
        for offer in offers
        if offer.in_stock
        and offer_age_hours(offer, now=reference) <= max_age_hours
        and bool(offer.affiliate_url or offer.product_url)
    ]

    def sort_key(offer: MerchantOffer) -> tuple[Any, ...]:
        total = offer_total_price(offer)
        total_known = total is not None
        age = offer_age_hours(offer, now=reference)

        # Offers inside the same 24-hour freshness band are considered comparable.
        # Within that band, the more recently updated offer wins.
        # Commission is not considered for ranking.
        freshness_band = int(age // 24)

        return (
            0 if total_known else 1,
            total if total_known else offer.price,
            freshness_band,
            age,
            offer.merchant_name.casefold(),
        )

    return sorted(eligible, key=sort_key)


def customer_offer_payload(offer: MerchantOffer) -> dict[str, Any]:
    total = offer_total_price(offer)
    return {
        "offer_id": offer.offer_id,
        "product_id": offer.product_id,
        "merchant_id": offer.merchant_id,
        "merchant_name": offer.merchant_name,
        "merchant_product_id": offer.merchant_product_id,
        "price": offer.price,
        "currency": offer.currency,
        "shipping_cost": offer.shipping_cost,
        "shipping_label": offer.shipping_label,
        "total_price": total,
        "in_stock": offer.in_stock,
        "variant_label": offer.variant_label,
        "clickout_path": f"/api/clickout/{offer.offer_id}",
        "affiliate_link": bool(offer.affiliate_url),
        "last_updated_at": offer.last_updated_at.isoformat(),
    }


class MerchantOfferStore:
    def __init__(self, path: Path) -> None:
        self.path = path

    def _load(self) -> list[MerchantOffer]:
        if not self.path.exists():
            return []

        raw = json.loads(self.path.read_text(encoding="utf-8"))
        rows = raw.get("offers", raw if isinstance(raw, list) else [])
        return [MerchantOffer.model_validate(row) for row in rows]

    def offers_for(
        self,
        product_id: str,
        *,
        now: datetime | None = None,
        max_age_hours: float = 72.0,
    ) -> list[MerchantOffer]:
        matches = [offer for offer in self._load() if offer.product_id == product_id]
        return rank_offers(
            matches,
            now=now,
            max_age_hours=max_age_hours,
        )

    def eligible_offer(
        self,
        offer_id: str,
        *,
        now: datetime | None = None,
        max_age_hours: float = 72.0,
    ) -> MerchantOffer | None:
        candidate = next(
            (offer for offer in self._load() if offer.offer_id == offer_id),
            None,
        )
        if candidate is None:
            return None

        eligible = rank_offers(
            [candidate],
            now=now,
            max_age_hours=max_age_hours,
        )
        return eligible[0] if eligible else None


class MerchantClickoutTracker:
    """Append-only local clickout event log for the MVP.

    No customer identity is stored here. A later analytics phase can attach an
    anonymous session or recommendation context once the public product is ready.
    """

    def __init__(self, path: Path) -> None:
        self.path = path

    def record(
        self,
        offer: MerchantOffer,
        *,
        now: datetime | None = None,
        acquisition_source: str | None = None,
        campaign_id: str | None = None,
        content_id: str | None = None,
    ) -> str:
        click_id = str(uuid4())
        occurred_at = _as_utc(now or datetime.now(UTC))
        event = {
            "click_id": click_id,
            "occurred_at": occurred_at.isoformat(),
            "offer_id": offer.offer_id,
            "product_id": offer.product_id,
            "merchant_id": offer.merchant_id,
            "merchant_name": offer.merchant_name,
            "network": offer.network,
            "affiliate_link": bool(offer.affiliate_url),
            "acquisition_source": acquisition_source,
            "campaign_id": campaign_id,
            "content_id": content_id,
        }

        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(event, ensure_ascii=False) + "\n")

        return click_id
