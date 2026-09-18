from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta

from retail.api.merchant_partners import MerchantPartnerStore


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
                "last_verified_at": (
                    NOW - timedelta(hours=2)
                ).isoformat(),
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

    assert [partner.merchant_id for partner in active] == [
        "douglas"
    ]


def test_stale_partner_is_hidden(tmp_path) -> None:
    path = write_payload(
        tmp_path,
        [
            {
                "merchant_id": "douglas",
                "merchant_name": "Douglas",
                "status": "active",
                "affiliate_url": "https://example.com/track",
                "last_verified_at": (
                    NOW - timedelta(hours=721)
                ).isoformat(),
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
