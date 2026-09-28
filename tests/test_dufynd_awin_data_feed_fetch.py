from __future__ import annotations

import gzip
import json
from pathlib import Path

import pytest
from scripts import fetch_dufynd_awin_data_feed as awin
from scripts.fetch_dufynd_awin_data_feed import (
    _maybe_decompress,
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


def test_compressed_payload_cannot_exceed_expanded_limit() -> None:
    payload = gzip.compress(b"x" * 10_000)
    with pytest.raises(ValueError, match="awin_response_exceeds_max_bytes"):
        _maybe_decompress(payload, max_bytes=1_000)


def test_plain_payload_cannot_exceed_limit() -> None:
    with pytest.raises(ValueError, match="awin_response_exceeds_max_bytes"):
        _maybe_decompress(b"x" * 1_001, max_bytes=1_000)


def test_download_report_is_parseable_and_excludes_secret_url(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    def read_url(url: str, *, max_bytes: int) -> bytes:
        if "/datafeed/list/" in url:
            return CSV.encode("utf-8")
        return gzip.compress(b"product_id\n123\n")

    monkeypatch.setattr(awin, "_read_url", read_url)
    report_path = tmp_path / "metadata.json"
    feed_path = tmp_path / "feed.csv"
    awin.download_feed_from_list(
        api_key="SECRET",
        advertiser_id="31081",
        feed_id="91379",
        output_path=feed_path,
        report_path=report_path,
    )

    report_text = report_path.read_text(encoding="utf-8")
    assert json.loads(report_text)["downloaded"] is True
    assert "SECRET" not in report_text
    assert feed_path.read_bytes() == b"product_id\n123\n"


def test_find_feed_selects_exact_advertiser_and_feed() -> None:
    row = find_feed(
        parse_feed_list(CSV.encode("utf-8")),
        advertiser_id="31081",
        feed_id="91379",
    )
    assert row["Advertiser Name"] == "top Parfümerie"


def test_find_feed_rejects_missing_target() -> None:
    try:
        find_feed(
            parse_feed_list(CSV.encode("utf-8")),
            advertiser_id="31081",
            feed_id="missing",
        )
    except ValueError as exc:
        assert str(exc) == "target_awin_feed_not_found"
    else:
        raise AssertionError("missing target feed must be rejected")


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
