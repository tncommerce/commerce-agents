from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from pathlib import Path

from retail.api.merchant_partners import (
    MerchantPartner,
    MerchantPartnerStore,
    customer_partner_payload,
)

NOW = datetime(2026, 9, 18, 20, 0, tzinfo=UTC)


def write_payload(tmp_path, partners: list[dict]):
    path = tmp_path / "merchant_partners.json"
    path.write_text(
        json.dumps({"partners": partners}),
        encoding="utf-8",
    )
    return path


def test_active_partner_requires_https_and_recent_verification(tmp_path) -> None:
    path = write_payload(
        tmp_path,
        [
            {
                "merchant_id": "douglas",
                "merchant_name": "Douglas",
                "status": "active",
                "affiliate_url": "https://example.com/track",
                "last_verified_at": (NOW - timedelta(hours=2)).isoformat(),
                "description": "Parfum und Beauty",
            },
            {
                "merchant_id": "notino",
                "merchant_name": "Notino",
                "status": "pending_affiliate_link",
                "affiliate_url": "https://example.com/notino",
                "last_verified_at": NOW.isoformat(),
            },
            {
                "merchant_id": "unsafe",
                "merchant_name": "Unsafe",
                "status": "active",
                "affiliate_url": "http://example.com/unsafe",
                "last_verified_at": NOW.isoformat(),
            },
        ],
    )

    store = MerchantPartnerStore(path)
    active = store.active(now=NOW)

    assert [partner.merchant_id for partner in active] == ["douglas"]


def test_stale_partner_is_hidden(tmp_path) -> None:
    path = write_payload(
        tmp_path,
        [
            {
                "merchant_id": "douglas",
                "merchant_name": "Douglas",
                "status": "active",
                "affiliate_url": "https://example.com/track",
                "last_verified_at": (NOW - timedelta(hours=721)).isoformat(),
            }
        ],
    )

    store = MerchantPartnerStore(path)

    assert store.active(now=NOW) == []
    assert store.eligible("douglas", now=NOW) is None


def test_eligible_partner_uses_exact_configured_id(tmp_path) -> None:
    path = write_payload(
        tmp_path,
        [
            {
                "merchant_id": "douglas",
                "merchant_name": "Douglas",
                "status": "active",
                "affiliate_url": "https://example.com/track",
                "last_verified_at": NOW.isoformat(),
            }
        ],
    )

    store = MerchantPartnerStore(path)

    assert store.eligible("douglas", now=NOW) is not None
    assert store.eligible("Douglas", now=NOW) is None


def test_customer_payload_does_not_expose_tracking_url() -> None:
    partner = MerchantPartner(
        merchant_id="douglas",
        merchant_name="Douglas",
        status="active",
        affiliate_url="https://example.com/private-tracking-link",
        last_verified_at=NOW,
        description="Parfum und Beauty",
    )

    payload = customer_partner_payload(partner)

    assert payload == {
        "merchant_id": "douglas",
        "merchant_name": "Douglas",
        "description": "Parfum und Beauty",
    }
    assert "affiliate_url" not in payload


def test_perfumetrader_fixture_uses_verified_awin_partner_link() -> None:
    path = Path(__file__).resolve().parents[2] / "data" / "merchant_partners.json"
    store = MerchantPartnerStore(path)

    partner = next(
        item
        for item in store.all()
        if item.merchant_id == "perfumetrader"
    )

    assert partner.status == "active"
    assert partner.affiliate_url is not None
    assert partner.affiliate_url.startswith("https://www.awin1.com/cread.php?")
    assert "awinmid=11672" in partner.affiliate_url
    assert "awinaffid=3099222" in partner.affiliate_url
    assert partner.last_verified_at is not None
