import json
from datetime import UTC, datetime, timedelta

from retail.api.merchant_offers import (
    MerchantClickoutTracker,
    MerchantOffer,
    MerchantOfferStore,
    customer_offer_payload,
    offer_clickout_target,
    rank_offers,
)
from retail.api.mock_retail import MockRetail

NOW = datetime(2026, 9, 15, 12, 0, tzinfo=UTC)


def offer(
    offer_id: str,
    *,
    merchant: str,
    price: float,
    shipping: float | None,
    in_stock: bool = True,
    age_hours: float = 1,
    commission: float | None = None,
) -> MerchantOffer:
    return MerchantOffer(
        offer_id=offer_id,
        product_id="SC-TEST-100",
        merchant_id=merchant.casefold(),
        merchant_name=merchant,
        merchant_product_id=f"{merchant}-sku",
        price=price,
        currency="EUR",
        shipping_cost=shipping,
        in_stock=in_stock,
        product_url=f"https://example.com/{offer_id}",
        last_updated_at=NOW - timedelta(hours=age_hours),
        commission_rate=commission,
    )


def test_excludes_out_of_stock_and_stale_offers() -> None:
    ranked = rank_offers(
        [
            offer("good", merchant="A", price=90, shipping=0),
            offer("sold-out", merchant="B", price=70, shipping=0, in_stock=False),
            offer("stale", merchant="C", price=60, shipping=0, age_hours=80),
        ],
        now=NOW,
    )

    assert [item.offer_id for item in ranked] == ["good"]


def test_rejects_materially_future_dated_offer() -> None:
    ranked = rank_offers(
        [
            offer(
                "future",
                merchant="Future Merchant",
                price=70,
                shipping=0,
                age_hours=-1,
            ),
            offer("current", merchant="Current Merchant", price=90, shipping=0),
        ],
        now=NOW,
    )

    assert [item.offer_id for item in ranked] == ["current"]


def test_small_clock_skew_is_tolerated_without_freshness_bonus() -> None:
    ranked = rank_offers(
        [
            offer(
                "slight-future",
                merchant="Z Merchant",
                price=90,
                shipping=0,
                age_hours=-(2 / 60),
            ),
            offer(
                "current",
                merchant="A Merchant",
                price=90,
                shipping=0,
                age_hours=0,
            ),
        ],
        now=NOW,
    )

    assert [item.offer_id for item in ranked] == ["current", "slight-future"]


def test_invalid_affiliate_url_falls_back_to_valid_product_url() -> None:
    candidate = offer("fallback", merchant="Merchant", price=90, shipping=0)
    candidate.affiliate_url = "javascript:alert(1)"

    ranked = rank_offers([candidate], now=NOW)

    assert [item.offer_id for item in ranked] == ["fallback"]
    assert offer_clickout_target(candidate) == candidate.product_url
    assert customer_offer_payload(candidate)["affiliate_link"] is False


def test_offer_without_valid_http_clickout_is_excluded() -> None:
    candidate = offer("invalid", merchant="Merchant", price=90, shipping=0)
    candidate.product_url = "javascript:alert(1)"
    candidate.affiliate_url = "data:text/plain,invalid"

    assert rank_offers([candidate], now=NOW) == []
    assert offer_clickout_target(candidate) is None


def test_known_customer_total_beats_unknown_shipping() -> None:
    ranked = rank_offers(
        [
            offer("known", merchant="A", price=90, shipping=0),
            offer("unknown", merchant="B", price=85, shipping=None),
        ],
        now=NOW,
    )

    assert [item.offer_id for item in ranked] == ["known", "unknown"]


def test_lowest_known_total_wins() -> None:
    ranked = rank_offers(
        [
            offer("a", merchant="A", price=88, shipping=5),
            offer("b", merchant="B", price=91, shipping=0),
        ],
        now=NOW,
    )

    assert ranked[0].offer_id == "b"


def test_commission_does_not_change_customer_ranking() -> None:
    ranked = rank_offers(
        [
            offer("customer-best", merchant="A", price=89, shipping=0, commission=0.03),
            offer("higher-commission", merchant="B", price=94, shipping=0, commission=0.15),
        ],
        now=NOW,
    )

    assert ranked[0].offer_id == "customer-best"


def test_equal_total_prefers_affiliate_then_higher_commission() -> None:
    direct = offer("direct", merchant="A", price=90, shipping=0)
    low = offer("low", merchant="B", price=90, shipping=0, commission=0.03)
    high = offer("high", merchant="C", price=90, shipping=0, commission=0.08)
    low.affiliate_url = "https://network.example/low"
    high.affiliate_url = "https://network.example/high"

    ranked = rank_offers([direct, low, high], now=NOW)

    assert [row.offer_id for row in ranked] == ["high", "low", "direct"]


def test_materially_fresher_direct_offer_beats_equal_price_affiliate() -> None:
    direct = offer("direct", merchant="A", price=90, shipping=0, age_hours=2)
    affiliate = offer(
        "affiliate",
        merchant="B",
        price=90,
        shipping=0,
        age_hours=30,
        commission=0.20,
    )
    affiliate.affiliate_url = "https://network.example/click"

    assert rank_offers([affiliate, direct], now=NOW)[0].offer_id == "direct"


def test_fresher_offer_wins_exact_price_tie() -> None:
    ranked = rank_offers(
        [
            offer("older", merchant="A", price=90, shipping=0, age_hours=20),
            offer("newer", merchant="B", price=90, shipping=0, age_hours=2),
        ],
        now=NOW,
    )

    assert ranked[0].offer_id == "newer"


def test_scentai_customer_product_uses_live_merchant_price(tmp_path) -> None:
    path = tmp_path / "merchant_offers.json"
    path.write_text(
        json.dumps(
            {
                "offers": [
                    {
                        "offer_id": "live-bois",
                        "product_id": "SC-ESSENTIAL-PARFUMS-BOIS-IMPERIAL-100",
                        "merchant_id": "merchant-a",
                        "merchant_name": "Merchant A",
                        "merchant_product_id": "sku-1",
                        "price": 94.0,
                        "currency": "EUR",
                        "shipping_cost": 0.0,
                        "in_stock": True,
                        "product_url": "https://example.com/bois",
                        "last_updated_at": datetime.now(UTC).isoformat(),
                    }
                ]
            }
        ),
        encoding="utf-8",
    )
    backend = MockRetail(offer_store=MerchantOfferStore(path))

    product = backend.customer_product("SC-ESSENTIAL-PARFUMS-BOIS-IMPERIAL-100")

    assert product is not None
    assert product.price == 94.0
    assert product.attributes["price_source"] == "current_merchant_offer"
    assert product.attributes["price_merchant"] == "Merchant A"


def test_scentai_customer_product_marks_catalog_only_price_as_reference(tmp_path) -> None:
    path = tmp_path / "merchant_offers.json"
    path.write_text('{"offers": []}', encoding="utf-8")
    backend = MockRetail(offer_store=MerchantOfferStore(path))

    product = backend.customer_product("SC-XERJOFF-NAXOS-100")

    assert product is not None
    assert product.attributes["price_source"] == "market_reference"


def test_commission_does_not_break_customer_equivalent_tie() -> None:
    ranked = rank_offers(
        [
            offer(
                "lower-commission",
                merchant="A",
                price=94,
                shipping=0,
                age_hours=2,
                commission=0.05,
            ),
            offer(
                "higher-commission",
                merchant="B",
                price=94,
                shipping=0,
                age_hours=2,
                commission=0.10,
            ),
        ],
        now=NOW,
    )

    assert ranked[0].offer_id == "lower-commission"


def test_materially_fresher_offer_beats_higher_commission() -> None:
    ranked = rank_offers(
        [
            offer(
                "fresh",
                merchant="A",
                price=94,
                shipping=0,
                age_hours=2,
                commission=0.03,
            ),
            offer(
                "older-higher-commission",
                merchant="B",
                price=94,
                shipping=0,
                age_hours=30,
                commission=0.15,
            ),
        ],
        now=NOW,
    )

    assert ranked[0].offer_id == "fresh"


def test_eligible_offer_rejects_stale_or_unavailable_offer(tmp_path) -> None:
    path = tmp_path / "merchant_offers.json"
    path.write_text(
        json.dumps(
            {
                "offers": [
                    {
                        "offer_id": "stale-offer",
                        "product_id": "SC-TEST-100",
                        "merchant_id": "merchant-a",
                        "merchant_name": "Merchant A",
                        "price": 90.0,
                        "currency": "EUR",
                        "shipping_cost": 0.0,
                        "in_stock": True,
                        "product_url": "https://example.com/stale",
                        "last_updated_at": (NOW - timedelta(hours=80)).isoformat(),
                    },
                    {
                        "offer_id": "sold-out-offer",
                        "product_id": "SC-TEST-100",
                        "merchant_id": "merchant-b",
                        "merchant_name": "Merchant B",
                        "price": 90.0,
                        "currency": "EUR",
                        "shipping_cost": 0.0,
                        "in_stock": False,
                        "product_url": "https://example.com/sold-out",
                        "last_updated_at": NOW.isoformat(),
                    },
                ]
            }
        ),
        encoding="utf-8",
    )
    store = MerchantOfferStore(path)

    assert store.eligible_offer("stale-offer", now=NOW) is None
    assert store.eligible_offer("sold-out-offer", now=NOW) is None


def test_clickout_tracker_writes_anonymous_event(tmp_path) -> None:
    log_path = tmp_path / "clickouts.jsonl"
    tracker = MerchantClickoutTracker(log_path)
    tracked_offer = offer(
        "tracked",
        merchant="Merchant A",
        price=90,
        shipping=0,
        commission=0.08,
    )

    click_id = tracker.record(tracked_offer, now=NOW)

    row = json.loads(log_path.read_text(encoding="utf-8").strip())
    assert row["click_id"] == click_id
    assert row["offer_id"] == "tracked"
    assert row["product_id"] == "SC-TEST-100"
    assert row["merchant_name"] == "Merchant A"
    assert "commission_rate" not in row
    assert "user_id" not in row


def test_clickout_tracker_does_not_mark_invalid_affiliate_url(tmp_path) -> None:
    log_path = tmp_path / "clickouts.jsonl"
    tracker = MerchantClickoutTracker(log_path)
    tracked_offer = offer(
        "invalid-affiliate-tracked",
        merchant="Merchant A",
        price=90,
        shipping=0,
    )
    tracked_offer.affiliate_url = "javascript:alert(1)"

    tracker.record(tracked_offer, now=NOW)

    row = json.loads(log_path.read_text(encoding="utf-8").strip())
    assert row["affiliate_link"] is False


def test_clickout_tracker_preserves_content_attribution(tmp_path) -> None:
    log_path = tmp_path / "clickouts.jsonl"
    tracker = MerchantClickoutTracker(log_path)
    tracked_offer = offer(
        "tracked-attributed",
        merchant="Merchant A",
        price=90,
        shipping=0,
    )

    tracker.record(
        tracked_offer,
        now=NOW,
        acquisition_source="tiktok",
        campaign_id="launch01",
        content_id="genesis_naxos_01",
    )

    row = json.loads(log_path.read_text(encoding="utf-8").strip())
    assert row["acquisition_source"] == "tiktok"
    assert row["campaign_id"] == "launch01"
    assert row["content_id"] == "genesis_naxos_01"
