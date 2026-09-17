import json

import pytest

from retail.api.merchant_feed_reader import (
    detect_feed_format,
    read_merchant_feed_rows,
)


def test_detect_feed_format_from_extension(
    tmp_path,
) -> None:
    assert detect_feed_format(
        tmp_path / "feed.json"
    ) == "json"

    assert detect_feed_format(
        tmp_path / "feed.csv"
    ) == "csv"


def test_read_json_object_feed(
    tmp_path,
) -> None:
    path = tmp_path / "feed.json"

    path.write_text(
        json.dumps(
            {
                "offers": [
                    {
                        "offer_id": "offer-1",
                        "price": 89.95,
                    }
                ]
            }
        ),
        encoding="utf-8",
    )

    rows = read_merchant_feed_rows(path)

    assert rows == [
        {
            "offer_id": "offer-1",
            "price": 89.95,
        }
    ]


def test_read_json_list_feed(
    tmp_path,
) -> None:
    path = tmp_path / "feed.json"

    path.write_text(
        json.dumps(
            [
                {
                    "offer_id": "offer-1",
                }
            ]
        ),
        encoding="utf-8",
    )

    assert read_merchant_feed_rows(path) == [
        {
            "offer_id": "offer-1",
        }
    ]


def test_read_csv_feed(
    tmp_path,
) -> None:
    path = tmp_path / "feed.csv"

    path.write_text(
        (
            "external_offer,external_sku,external_price\n"
            "offer-1,SKU-123,89.95\n"
        ),
        encoding="utf-8",
    )

    rows = read_merchant_feed_rows(path)

    assert rows == [
        {
            "external_offer": "offer-1",
            "external_sku": "SKU-123",
            "external_price": "89.95",
        }
    ]


def test_explicit_format_can_override_extension(
    tmp_path,
) -> None:
    path = tmp_path / "provider-export.txt"

    path.write_text(
        "offer_id,price\noffer-1,89.95\n",
        encoding="utf-8",
    )

    rows = read_merchant_feed_rows(
        path,
        feed_format="csv",
    )

    assert rows[0]["offer_id"] == "offer-1"


def test_unsupported_feed_extension_is_rejected(
    tmp_path,
) -> None:
    path = tmp_path / "feed.xml"

    path.write_text(
        "<feed />",
        encoding="utf-8",
    )

    with pytest.raises(
        ValueError,
        match="Unsupported merchant feed format",
    ):
        read_merchant_feed_rows(path)


def test_invalid_json_shape_is_rejected(
    tmp_path,
) -> None:
    path = tmp_path / "feed.json"

    path.write_text(
        json.dumps(
            {
                "unexpected": []
            }
        ),
        encoding="utf-8",
    )

    with pytest.raises(
        ValueError,
        match="must be a list",
    ):
        read_merchant_feed_rows(path)
