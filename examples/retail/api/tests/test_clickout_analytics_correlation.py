from __future__ import annotations

from datetime import UTC, datetime
from types import SimpleNamespace
from urllib.parse import parse_qs, urlparse

import pytest

from retail.api import main as main_module
from retail.api.analytics import AnalyticsEventRequest
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
        return self.partner if partner_key == self.partner.merchant_id else None


class StaticOfferStore:
    def __init__(self, offer: MerchantOffer) -> None:
        self.offer = offer

    def eligible_offer(self, offer_id: str) -> MerchantOffer | None:
        return self.offer if offer_id == self.offer.offer_id else None


class CapturingClickoutTracker:
    def __init__(self) -> None:
        self.calls: list[tuple[MerchantOffer, dict[str, object]]] = []

    def record(self, offer: MerchantOffer, **kwargs) -> str:
        self.calls.append((offer, kwargs))
        return "12345678-1234-4234-8234-123456789abc"


class CapturingAnalyticsTracker:
    def __init__(self) -> None:
        self.calls: list[dict[str, object]] = []

    async def record(self, **kwargs):
        self.calls.append(kwargs)
        return "12345678-1234-4234-8234-123456789abc", "test-memory"


@pytest.mark.asyncio
async def test_partner_copied_grant_redirect_is_measurement_free(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    partner = MerchantPartner(
        merchant_id="qa-partner",
        merchant_name="QA Partner",
        status="active",
        affiliate_url="https://example.com/partner",
        last_verified_at=datetime(2026, 9, 30, 12, 0, tzinfo=UTC),
    )
    monkeypatch.setattr(main_module, "partner_store", StaticPartnerStore(partner))
    tasks = CapturingBackgroundTasks()

    response = await main_module.merchant_partner_clickout(
        "qa-partner",
        tasks,
        measurement="granted-v1",
        src=" tiktok ",
        cmp=" launch_01 ",
        content=" partner_card_01 ",
        sid=" session-partner-123456 ",
    )

    assert response.status_code == 302
    assert response.headers["location"] == partner.affiliate_url
    assert response.headers["cache-control"] == "no-store"
    assert response.headers["referrer-policy"] == "no-referrer"
    assert tasks.calls == []


@pytest.mark.asyncio
async def test_offer_copied_grant_redirect_is_measurement_free(
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
    monkeypatch.setattr(main_module, "offer_store", StaticOfferStore(offer))
    monkeypatch.setattr(main_module, "clickout_tracker", clickouts)
    monkeypatch.setattr(main_module, "_live_dufynd_offer_product", lambda _: True)
    tasks = CapturingBackgroundTasks()

    response = await main_module.merchant_clickout(
        "qa-offer",
        tasks,
        measurement="granted-v1",
        src=" instagram ",
        cmp=" launch_02 ",
        content=" offer_card_02 ",
        sid=" session-offer-123456 ",
    )

    assert response.status_code == 302
    assert response.headers["location"] == offer.affiliate_url
    assert response.headers["cache-control"] == "no-store"
    assert response.headers["referrer-policy"] == "no-referrer"
    assert clickouts.calls == []
    assert tasks.calls == []


@pytest.mark.asyncio
async def test_awin_copied_context_does_not_generate_clickrefs(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    offer = MerchantOffer(
        offer_id="awin-offer",
        product_id="SC-QA-100",
        merchant_id="perfumetrader",
        merchant_name="Perfumetrader",
        merchant_product_id="16978322",
        price=71.9,
        currency="EUR",
        shipping_cost=4.99,
        in_stock=True,
        product_url="https://www.perfumetrader.de/product",
        affiliate_url=(
            "https://www.awin1.com/cread.php?"
            "awinmid=11672&awinaffid=3099222&clickref=static_old&"
            "ued=https%3A%2F%2Fwww.perfumetrader.de%2Fproduct"
        ),
        last_updated_at=datetime(2026, 9, 30, 12, 0, tzinfo=UTC),
    )
    monkeypatch.setattr(main_module, "offer_store", StaticOfferStore(offer))
    monkeypatch.setattr(main_module, "_live_dufynd_offer_product", lambda _: True)
    tasks = CapturingBackgroundTasks()

    response = await main_module.merchant_clickout(
        "awin-offer",
        tasks,
        measurement="granted-v1",
        src="youtube",
        cmp="campaign_01",
        content="content_01",
        sid="session-1234567890",
    )

    assert response.status_code == 302
    assert response.headers["location"] == offer.affiliate_url
    query = parse_qs(urlparse(response.headers["location"]).query)
    assert query["clickref"] == ["static_old"]
    assert "clickref2" not in query
    assert "clickref3" not in query
    assert "clickref4" not in query
    assert "clickref5" not in query
    assert "clickref6" not in query
    assert tasks.calls == []


@pytest.mark.asyncio
@pytest.mark.parametrize("session_id", ["session-cj-1234567890", None])
async def test_cj_copied_grant_does_not_replace_static_destination_sid(
    monkeypatch: pytest.MonkeyPatch, session_id: str | None
) -> None:
    offer = MerchantOffer(
        offer_id="notino-pdm-delina-edp-75",
        product_id="SC-PDM-DELINA-EDP-75",
        merchant_id="notino",
        merchant_name="Notino",
        price=285,
        shipping_cost=0,
        in_stock=True,
        product_url="https://www.notino.de/exact-delina-75/",
        affiliate_url=(
            "https://www.jdoqocy.com/click-101884613-12260695?"
            "SID=old&sid=older&url=https%3A%2F%2Fwww.notino.de%2Fexact-delina-75%2F"
        ),
        network="CJ Affiliate",
        last_updated_at=datetime.now(UTC),
    )
    monkeypatch.setattr(main_module, "offer_store", StaticOfferStore(offer))
    monkeypatch.setattr(main_module, "_live_dufynd_offer_product", lambda _: True)
    tasks = CapturingBackgroundTasks()

    response = await main_module.merchant_clickout(
        offer.offer_id,
        tasks,
        measurement="granted-v1",
        src="instagram",
        cmp="qa_campaign",
        content="qa_content",
        sid=session_id,
    )

    assert response.status_code == 302
    assert response.headers["location"] == offer.affiliate_url
    query = parse_qs(urlparse(response.headers["location"]).query)
    assert query["SID"] == ["old"]
    assert query["sid"] == ["older"]
    assert query["url"] == [offer.product_url]
    assert tasks.calls == []


@pytest.mark.asyncio
async def test_live_consent_analytics_post_correlates_offer_and_acquisition(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    tracker = CapturingAnalyticsTracker()
    monkeypatch.setattr(main_module, "analytics_tracker", tracker)
    payload = AnalyticsEventRequest(
        event="merchant_clickout",
        analytics_session_id="measurement-session-1234567890",
        product_id="SC-QA-100",
        offer_id="qa-offer",
        source="qa-merchant",
        acquisition_source="instagram",
        campaign_id="launch_02",
        content_id="offer_card_02",
        surface="merchant_offer",
    )

    response = await main_module.analytics_event(
        payload,
        SimpleNamespace(session_id="functional-session-1234567890"),
        measurement="granted-v1",
    )

    assert response == {
        "ok": True,
        "event_id": "12345678-1234-4234-8234-123456789abc",
        "storage": "test-memory",
    }
    assert len(tracker.calls) == 1
    call = tracker.calls[0]
    assert call["session_id"] == "measurement-session-1234567890"
    assert call["event"] == "merchant_clickout"
    assert call["product_id"] == "SC-QA-100"
    assert call["offer_id"] == "qa-offer"
    assert call["source"] == "qa-merchant"
    assert call["acquisition_source"] == "instagram"
    assert call["campaign_id"] == "launch_02"
    assert call["content_id"] == "offer_card_02"
    assert call["surface"] == "merchant_offer"
