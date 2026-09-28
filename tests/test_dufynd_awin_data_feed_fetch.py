from __future__ import annotations

import gzip

import pytest
from scripts.fetch_dufynd_awin_data_feed import (
    find_feed,
    parse_feed_list,
    sanitized_feed_metadata,
)


CSV = """Advertiser ID,Advertiser Name,Primary Region,Membership Status,Feed ID,Feed Name,Language,Last Imported,URL
31081,top Parfümerie,DE,Joined,91379,Default,German,2026-09-28 09:00:00,https://datafeed.api.productserve.com/datafeed/download/apikey/SECRET/fid/91379/format/csv/
11672,Perfumetrader,DE,Joined,99999,Default,German,2026-09-27 09:00:00,https://datafeed.api.productserve.com/datafeed/download/apikey/OTHER/fid/99999/format/csv/
"""


def test_parse_feed_list_accepts_plain_csv() -> None:
    rows = parse_feed_list(CSV.encode("utf-8"))
    assert len(rows) == 2
    assert rows[0]["Advertiser ID"] == "31081"


def test_parse_feed_list_accepts_gzip_csv() -> None:
    rows = parse_feed_list(gzip.compress(CSV.encode("utf-8")))
    assert len(rows) == 2
    assert rows[0]["Feed ID"] == "91379"


def test_find_feed_selects_exact_advertiser_and_feed() -> None:
    row = find_feed(
        parse_feed_list(CSV.encode("utf-8")),
        advertiser_id="31081",
        feed_id="91379",
    )
    assert row["Advertiser Name"] == "top Parfümerie"


def test_find_feed_rejects_missing_target() -> None:
    with pytest.raises(ValueError, match="target_awin_feed_not_found"):
        find_feed(
            parse_feed_list(CSV.encode("utf-8")),
            advertiser_id="31081",
            feed_id="missing",
        )


def test_sanitized_metadata_never_contains_secret_download_url() -> None:
    row = find_feed(
        parse_feed_list(CSV.encode("utf-8")),
        advertiser_id="31081",
        feed_id="91379",
    )
    metadata = sanitized_feed_metadata(row)

    assert metadata["advertiser_id"] == "31081"
    assert metadata["feed_id"] == "91379"
    assert metadata["joined"] is True
    assert metadata["download_host"] == "datafeed.api.productserve.com"
    assert "URL" not in metadata
    assert "SECRET" not in str(metadata)
