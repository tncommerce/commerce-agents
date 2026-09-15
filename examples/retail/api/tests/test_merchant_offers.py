from datetime import datetime, timedelta, timezone

from retail.api.merchant_offers import MerchantOffer, rank_offers


NOW = datetime(2026, 9, 15, 12, 0, tzinfo=timezone.utc)


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


def test_fresher_offer_wins_exact_price_tie() -> None:
    ranked = rank_offers(
        [
            offer("older", merchant="A", price=90, shipping=0, age_hours=20),
            offer("newer", merchant="B", price=90, shipping=0, age_hours=2),
        ],
        now=NOW,
    )

    assert ranked[0].offer_id == "newer"
