from __future__ import annotations

from datetime import UTC, datetime

import pytest

from retail.api import main as main_module
from retail.api.merchant_offers import MerchantOffer
from retail.api.merchant_partners import MerchantPartner


class CapturingBackgroundTasks:
    def __init__(self) -> None:
        self.calls: list[tuple[object, tuple[object, ...], dict[str, object]]] = []

    def add_task(self, func, *args, **kwargs) -> None:
        self.calls.append((func, args, kwargs))


class StaticPartnerStore:
    def __init__(self, partner: MerchantPartner) -> None:
        self.partner = partner

    def eligible(self, partner_key: str) -> MerchantPartner | None:
        if partner_key == self.partner.merchant_id:
            return self.partner
        return None


class StaticOfferStore:
    def __init__(self, offer: MerchantOffer) -> None:
        self.offer = offer

    def eligible_offer(self, offer_id: str) -> MerchantOffer | None:
        if offer_id == self.offer.offer_id:
            return self.offer
        return None


class CapturingClickoutTracker:
    def __init__(self) -> None:
        self.calls: list[tuple[MerchantOffer, dict[str, object]]] = []

    def record(self, offer: MerchantOffer, **kwargs) -> str:
        self.calls.append((offer, kwargs))
        return "qa-click-id"


@pytest.mark.asyncio
async def test_partner_clickout_correlates_session_and_acquisition(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    partner = MerchantPartner(
        merchant_id="qa-partner",
        merchant_name="QA Partner",
        status="active",
        affiliate_url="https://example.com/partner",
        last_verified_at=datetime(2026, 9, 30, 12, 0, tzinfo=UTC),
    )
    monkeypatch.setattr(
        main_module,
        "partner_store",
        StaticPartnerStore(partner),
    )
    tasks = CapturingBackgroundTasks()

    response = await main_module.merchant_partner_clickout(
        "qa-partner",
        tasks,
        src=" tiktok ",
        cmp=" launch_01 ",
        content=" partner_card_01 ",
        sid=" session-partner-123456 ",
    )

    assert response.status_code == 302
    assert response.headers["location"] == "https://example.com/partner"
    assert len(tasks.calls) == 1

    func, args, kwargs = tasks.calls[0]
    assert func == main_module.analytics_tracker.record
    assert args == ()
    assert kwargs == {
        "session_id": "session-partner-123456",
        "event": "merchant_clickout",
        "source": "qa-partner",
        "acquisition_source": "tiktok",
        "campaign_id": "launch_01",
        "content_id": "partner_card_01",
        "surface": "merchant_discovery",
    }


@pytest.mark.asyncio
async def test_offer_clickout_correlates_session_and_acquisition(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    offer = MerchantOffer(
        offer_id="qa-offer",
        product_id="SC-QA-100",
        merchant_id="qa-merchant",
        merchant_name="QA Merchant",
        merchant_product_id="qa-sku",
        price=99.0,
        currency="EUR",
        shipping_cost=0.0,
        in_stock=True,
        product_url="https://example.com/product",
        affiliate_url="https://network.example/click",
        last_updated_at=datetime(2026, 9, 30, 12, 0, tzinfo=UTC),
    )
    clickouts = CapturingClickoutTracker()
    monkeypatch.setattr(
        main_module,
        "offer_store",
        StaticOfferStore(offer),
    )
    monkeypatch.setattr(
        main_module,
        "clickout_tracker",
        clickouts,
    )
    monkeypatch.setattr(
        main_module,
        "_live_dufynd_offer_product",
        lambda product_id: product_id == "SC-QA-100",
    )
    tasks = CapturingBackgroundTasks()

    response = await main_module.merchant_clickout(
        "qa-offer",
        tasks,
        src=" instagram ",
        cmp=" launch_02 ",
        content=" offer_card_02 ",
        sid=" session-offer-123456 ",
    )

    assert response.status_code == 302
    assert response.headers["location"] == "https://network.example/click"
    assert clickouts.calls == [
        (
            offer,
            {
                "acquisition_source": "instagram",
                "campaign_id": "launch_02",
                "content_id": "offer_card_02",
            },
        )
    ]
    assert len(tasks.calls) == 1

    func, args, kwargs = tasks.calls[0]
    assert func == main_module.analytics_tracker.record
    assert args == ()
    assert kwargs == {
        "session_id": "session-offer-123456",
        "event": "merchant_clickout",
        "product_id": "SC-QA-100",
        "source": "qa-merchant",
        "acquisition_source": "instagram",
        "campaign_id": "launch_02",
        "content_id": "offer_card_02",
        "surface": "merchant_offer",
    }
