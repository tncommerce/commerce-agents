from retail.api.merchant_feed_guard import (
    find_duplicate_offer_ids,
)


def test_duplicate_offer_ids_are_detected() -> None:
    rows = [
        {"offer_id": "offer-1"},
        {"offer_id": "offer-2"},
        {"offer_id": "offer-1"},
    ]

    assert find_duplicate_offer_ids(rows) == [
        "offer-1"
    ]


def test_duplicate_detection_ignores_outer_whitespace() -> None:
    rows = [
        {"offer_id": "offer-1"},
        {"offer_id": " offer-1 "},
    ]

    assert find_duplicate_offer_ids(rows) == [
        "offer-1"
    ]
