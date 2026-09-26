from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from retail.api.merchant_partners import (
    MerchantPartner,
    MerchantPartnerStore,
    customer_partner_payload,
    partner_clickout_url,
    partner_product_deeplink_url,
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


def test_active_partner_rejects_loopback_and_credential_urls(tmp_path) -> None:
    path = write_payload(
        tmp_path,
        [
            {
                "merchant_id": "localhost",
                "merchant_name": "Localhost",
                "status": "active",
                "affiliate_url": "https://localhost/track",
                "last_verified_at": NOW.isoformat(),
            },
            {
                "merchant_id": "loopback",
                "merchant_name": "Loopback",
                "status": "active",
                "affiliate_url": "https://127.0.0.1/track",
                "last_verified_at": NOW.isoformat(),
            },
            {
                "merchant_id": "credentials",
                "merchant_name": "Credentials",
                "status": "active",
                "affiliate_url": "https://user:pass@example.com/track",
                "last_verified_at": NOW.isoformat(),
            },
        ],
    )

    store = MerchantPartnerStore(path)

    assert store.active(now=NOW) == []


def test_small_future_clock_skew_keeps_active_partner_visible(tmp_path) -> None:
    path = write_payload(
        tmp_path,
        [
            {
                "merchant_id": "slight-future",
                "merchant_name": "Slight Future",
                "status": "active",
                "affiliate_url": "https://example.com/track",
                "last_verified_at": (NOW + timedelta(minutes=2)).isoformat(),
            }
        ],
    )

    store = MerchantPartnerStore(path)

    assert [partner.merchant_id for partner in store.active(now=NOW)] == ["slight-future"]


def test_material_future_partner_verification_is_hidden(tmp_path) -> None:
    path = write_payload(
        tmp_path,
        [
            {
                "merchant_id": "future",
                "merchant_name": "Future",
                "status": "active",
                "affiliate_url": "https://example.com/track",
                "last_verified_at": (NOW + timedelta(minutes=10)).isoformat(),
            }
        ],
    )

    store = MerchantPartnerStore(path)

    assert store.active(now=NOW) == []


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

    partner = next(item for item in store.all() if item.merchant_id == "perfumetrader")

    assert partner.status == "active"
    assert partner.affiliate_url is not None
    assert partner.affiliate_url.startswith("https://www.awin1.com/cread.php?")
    assert "awinmid=11672" in partner.affiliate_url
    assert "awinaffid=3099222" in partner.affiliate_url
    assert partner.last_verified_at is not None


def test_awin_partner_clickout_adds_content_clickref() -> None:
    partner = MerchantPartner(
        merchant_id="perfumetrader",
        merchant_name="Perfumetrader",
        status="active",
        affiliate_url=(
            "https://www.awin1.com/cread.php?"
            "awinmid=11672&awinaffid=3099222&"
            "ued=https%3A%2F%2Fwww.perfumetrader.de%2Fde%2F"
        ),
        last_verified_at=NOW,
    )

    target = partner_clickout_url(
        partner,
        clickref="genesis_naxos_01",
    )

    assert target is not None
    query = parse_qs(urlparse(target).query)
    assert query["awinmid"] == ["11672"]
    assert query["awinaffid"] == ["3099222"]
    assert query["ued"] == ["https://www.perfumetrader.de/de/"]
    assert query["clickref"] == ["genesis_naxos_01"]


def test_awin_partner_clickout_replaces_existing_clickref() -> None:
    partner = MerchantPartner(
        merchant_id="perfumetrader",
        merchant_name="Perfumetrader",
        status="active",
        affiliate_url=(
            "https://www.awin1.com/cread.php?"
            "awinmid=11672&awinaffid=3099222&clickref=old_ref&"
            "ued=https%3A%2F%2Fwww.perfumetrader.de%2Fde%2F"
        ),
        last_verified_at=NOW,
    )

    target = partner_clickout_url(
        partner,
        clickref="static_naxos_editorial_001",
    )

    assert target is not None
    query = parse_qs(urlparse(target).query)
    assert query["clickref"] == ["static_naxos_editorial_001"]


def test_non_awin_partner_clickout_is_unchanged() -> None:
    partner = MerchantPartner(
        merchant_id="example",
        merchant_name="Example",
        status="active",
        affiliate_url="https://example.com/track?foo=bar",
        last_verified_at=NOW,
    )

    assert partner_clickout_url(partner, clickref="genesis_naxos_01") == partner.affiliate_url


def perfumetrader_partner() -> MerchantPartner:
    return MerchantPartner(
        merchant_id="perfumetrader",
        merchant_name="Perfumetrader",
        status="active",
        affiliate_url=(
            "https://www.awin1.com/cread.php?"
            "awinmid=11672&awinaffid=3099222&"
            "ued=https%3A%2F%2Fwww.perfumetrader.de%2Fde%2F"
        ),
        last_verified_at=NOW,
    )


def test_awin_product_deeplink_replaces_verified_destination() -> None:
    target = partner_product_deeplink_url(
        perfumetrader_partner(),
        destination_url=(
            "https://www.perfumetrader.de/de/dior-hypnotic-poison-eau-de-toilette-100-ml"
        ),
        clickref="release01_hypnotic_poison",
    )

    assert target is not None
    query = parse_qs(urlparse(target).query)
    assert query["awinmid"] == ["11672"]
    assert query["awinaffid"] == ["3099222"]
    assert query["ued"] == [
        "https://www.perfumetrader.de/de/dior-hypnotic-poison-eau-de-toilette-100-ml"
    ]
    assert query["clickref"] == ["release01_hypnotic_poison"]


def test_awin_product_deeplink_accepts_www_equivalent_host() -> None:
    target = partner_product_deeplink_url(
        perfumetrader_partner(),
        destination_url="https://perfumetrader.de/de/product",
    )

    assert target is not None
    assert parse_qs(urlparse(target).query)["ued"] == ["https://perfumetrader.de/de/product"]


def test_awin_product_deeplink_rejects_external_destination() -> None:
    assert (
        partner_product_deeplink_url(
            perfumetrader_partner(),
            destination_url="https://example.com/product",
        )
        is None
    )
    assert (
        partner_product_deeplink_url(
            perfumetrader_partner(),
            destination_url="https://www.perfumetrader.de.evil.example/product",
        )
        is None
    )


def test_awin_product_deeplink_rejects_non_https_destination() -> None:
    assert (
        partner_product_deeplink_url(
            perfumetrader_partner(),
            destination_url="http://www.perfumetrader.de/de/product",
        )
        is None
    )


def test_awin_product_deeplink_requires_verified_ued_template() -> None:
    partner = MerchantPartner(
        merchant_id="perfumetrader",
        merchant_name="Perfumetrader",
        status="active",
        affiliate_url=("https://www.awin1.com/cread.php?awinmid=11672&awinaffid=3099222"),
        last_verified_at=NOW,
    )

    assert (
        partner_product_deeplink_url(
            partner,
            destination_url="https://www.perfumetrader.de/de/product",
        )
        is None
    )
