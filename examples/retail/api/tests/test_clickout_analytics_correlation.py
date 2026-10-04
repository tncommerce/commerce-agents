from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from urllib.parse import parse_qs, urlparse

import pytest

from retail.api import main as main_module
from retail.api.analytics import FirstPartyAnalyticsTracker
from retail.api.merchant_offers import MerchantClickoutTracker, MerchantOffer
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
        return "12345678-1234-4234-8234-123456789abc"


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
                "session_id": "session-offer-123456",
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
        "offer_id": "qa-offer",
        "event_id": "12345678-1234-4234-8234-123456789abc",
    }


@pytest.mark.asyncio
async def test_offer_clickout_forwards_attribution_into_awin_clickrefs(
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
    clickouts = CapturingClickoutTracker()
    monkeypatch.setattr(main_module, "offer_store", StaticOfferStore(offer))
    monkeypatch.setattr(main_module, "clickout_tracker", clickouts)
    monkeypatch.setattr(
        main_module,
        "_live_dufynd_offer_product",
        lambda product_id: product_id == "SC-QA-100",
    )
    tasks = CapturingBackgroundTasks()

    response = await main_module.merchant_clickout(
        "awin-offer",
        tasks,
        src="youtube",
        cmp="campaign_01",
        content="content_01",
        sid="session-1234567890",
    )

    assert response.status_code == 302
    query = parse_qs(urlparse(response.headers["location"]).query)
    assert query["clickref"] == ["content_01"]
    assert query["clickref2"] == ["campaign_01"]
    assert query["clickref3"] == ["youtube"]
    assert query["clickref4"] == ["session-1234567890"]
    assert query["clickref5"] == ["SC-QA-100"]
    assert query["clickref6"] == ["awin-offer"]


@pytest.mark.asyncio
@pytest.mark.parametrize("session_id", ["session-cj-1234567890", None])
async def test_cj_sid_joins_durable_clickout_without_changing_destination(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, session_id: str | None
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
    tracker = FirstPartyAnalyticsTracker(tmp_path / "analytics.jsonl")
    tracker.supabase_url = ""
    monkeypatch.setattr(main_module, "analytics_tracker", tracker)
    monkeypatch.setattr(
        main_module, "clickout_tracker", MerchantClickoutTracker(tmp_path / "clicks.jsonl")
    )
    monkeypatch.setattr(main_module, "offer_store", StaticOfferStore(offer))
    monkeypatch.setattr(main_module, "_live_dufynd_offer_product", lambda _: True)
    tasks = CapturingBackgroundTasks()
    response = await main_module.merchant_clickout(
        offer.offer_id,
        tasks,
        src="instagram",
        cmp="qa_campaign",
        content="qa_content",
        sid=session_id,
    )
    for func, args, kwargs in tasks.calls:
        await func(*args, **kwargs)
    row = json.loads(tracker.path.read_text())
    local = json.loads((tmp_path / "clicks.jsonl").read_text())
    target = urlparse(response.headers["location"])
    query = parse_qs(target.query)
    assert target.netloc == "www.jdoqocy.com"
    assert target.path == "/click-101884613-12260695"
    assert query["url"] == [offer.product_url]
    assert query["sid"] == [row["event_id"].replace("-", "")]
    assert len(query["sid"][0]) == 32
    assert "SID" not in query
    assert row["event_id"] == local["click_id"]
    assert row["session_key"] == local["session_key"]
    assert row["offer_id"] == offer.offer_id
    assert row["product_id"] == offer.product_id
    assert row["campaign_id"] == "qa_campaign"
    assert row["content_id"] == "qa_content"
    assert row["acquisition_source"] == "instagram"
    assert row["source"] == "notino"
    assert "session_id" not in row
