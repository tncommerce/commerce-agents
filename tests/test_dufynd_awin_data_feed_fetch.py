from __future__ import annotations

import gzip
import hashlib
import json
from pathlib import Path
from urllib.request import Request

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
    def read_url(
        url: str, *, max_bytes: int, expected_feed_id: str | None = None
    ) -> bytes:
        if "/datafeed/list/" in url:
            assert expected_feed_id is None
            return CSV.encode("utf-8")
        assert expected_feed_id == "91379"
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
    assert (
        json.loads(report_text)["download_sha256"]
        == hashlib.sha256(b"product_id\n123\n").hexdigest()
    )
    assert json.loads(report_text)["downloaded_bytes"] == len(b"product_id\n123\n")
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


@pytest.mark.parametrize(
    "redirect_url",
    [
        "https://external.example/feed?apikey=SECRET",
        "http://datafeed.api.productserve.com/feed?apikey=SECRET",
        "https://user:SECRET@datafeed.api.productserve.com/feed",
    ],
)
def test_credentialed_awin_request_cannot_redirect_outside_allowed_https_hosts(
    redirect_url: str,
) -> None:
    request = Request("https://productdata.awin.com/datafeed/list/apikey/SECRET")

    with pytest.raises(ValueError, match="awin_redirect_host_not_allowed") as exc:
        awin.AwinRedirectHandler().redirect_request(request, None, 302, "Found", {}, redirect_url)
    assert "SECRET" not in str(exc.value)


def test_awin_request_can_redirect_to_allowed_https_feed_host() -> None:
    request = Request("https://productdata.awin.com/datafeed/list/apikey/SECRET")
    redirected = awin.AwinRedirectHandler().redirect_request(
        request, None, 302, "Found", {}, "https://datafeed.api.productserve.com/feed"
    )

    assert redirected.full_url == "https://datafeed.api.productserve.com/feed"


def test_active_awin_membership_is_treated_as_joined() -> None:
    csv_payload = CSV.replace(",Joined,91379,", ",active,91379,", 1)
    row = find_feed(
        parse_feed_list(csv_payload.encode("utf-8")),
        advertiser_id="31081",
        feed_id="91379",
    )

    metadata = sanitized_feed_metadata(row)

    assert metadata["membership_status"] == "active"
    assert metadata["joined"] is True


@pytest.mark.parametrize(
    "header",
    [
        "Advertiser-ID,Advertiser ID,Feed ID,URL",
        "Advertiser ID,Feed-ID,Feed ID,URL",
        "Advertiser ID,,Feed ID,URL",
    ],
)
def test_feed_list_rejects_ambiguous_normalized_headers(header: str) -> None:
    payload = (header + "\n31081,31081,91379,https://example.test/file\n").encode()
    with pytest.raises(ValueError, match="awin_feed_list_"):
        parse_feed_list(payload)


def test_feed_list_rejects_rows_with_extra_undeclared_fields() -> None:
    payload = b"Advertiser ID,Feed ID\n31081,91379,unapproved-extra\n"
    with pytest.raises(ValueError, match="row_exceeds_declared_columns"):
        parse_feed_list(payload)


def test_exact_awin_feed_lookup_rejects_duplicate_target_rows() -> None:
    rows = parse_feed_list(CSV.encode("utf-8"))
    duplicate = rows[0].copy()
    duplicate["URL"] = "https://datafeed.api.productserve.com/other"
    with pytest.raises(ValueError, match="target_awin_feed_ambiguous_duplicate"):
        find_feed(
            [*rows, duplicate],
            advertiser_id="31081",
            feed_id="91379",
        )


def test_two_distinct_awin_advertisers_keep_separate_identities() -> None:
    rows = parse_feed_list(CSV.encode("utf-8"))
    assert find_feed(rows, advertiser_id="31081", feed_id="91379") is rows[0]
    assert find_feed(rows, advertiser_id="11672", feed_id="99999") is rows[1]


@pytest.mark.parametrize(
    "bad_url",
    [
        # A row for the chosen feed must not download a different feed.
        (
            "https://datafeed.api.productserve.com/datafeed/download/apikey/"
            "SECRET/fid/99999/format/csv/"
        ),
        (
            "https://datafeed.api.productserve.com/datafeed/download/apikey/"
            "SECRET/format/csv/"
        ),
        (
            "https://datafeed.api.productserve.com/datafeed/download/apikey/"
            "SECRET/fid/91379/fid/99999/"
        ),
        (
            "https://datafeed.api.productserve.com/datafeed/download/apikey/"
            "SECRET/fid/91379/?fid=99999"
        ),
        (
            "https://datafeed.api.productserve.com/datafeed/download/apikey/"
            "SECRET/fid/91379/?fid=91379&fid=99999"
        ),
        (
            "https://datafeed.api.productserve.com/datafeed/download/apikey/"
            "SECRET/fid/91379/?FID=99999"
        ),
        (
            "https://datafeed.api.productserve.com/datafeed/download/apikey/"
            "SECRET/fid/91" + chr(10) + "379/"
        ),
        # A correct-looking ID does not waive URL-origin restrictions.
        (
            "http://datafeed.api.productserve.com/datafeed/download/apikey/"
            "SECRET/fid/91379/"
        ),
        (
            "https://user:pw@datafeed.api.productserve.com/datafeed/download/apikey/"
            "SECRET/fid/91379/"
        ),
        (
            "https://datafeed.api.productserve.com:4443/datafeed/download/apikey/"
            "SECRET/fid/91379/"
        ),
        (
            "https://datafeed.api.productserve.com/datafeed/download/apikey/"
            "SECRET/fid/91379/#wrong"
        ),
        "https://outside.example/datafeed/download/apikey/SECRET/fid/91379/",
    ],
)
def test_awin_feed_download_rejects_false_provenance_or_unsafe_url(
    bad_url: str,
) -> None:
    with pytest.raises(ValueError, match="awin_feed_download_") as exc:
        awin._validate_feed_download_url(bad_url, feed_id="91379")
    assert "SECRET" not in str(exc.value)


@pytest.mark.parametrize(
    "redirect_url",
    [
        (
            "https://datafeed.api.productserve.com/datafeed/download/apikey/"
            "SECRET/fid/99999/format/csv/"
        ),
        (
            "https://productdata.awin.com/datafeed/download/apikey/"
            "SECRET/fid/91379/?fid=99999"
        ),
        "https://datafeed.api.productserve.com/other-path",
    ],
)
def test_awin_download_redirect_cannot_change_selected_feed(
    redirect_url: str,
) -> None:
    request = Request(
        "https://productdata.awin.com/datafeed/download/apikey/SECRET/fid/91379/"
    )
    with pytest.raises(ValueError, match="awin_redirect_feed_id_mismatch") as exc:
        awin.AwinRedirectHandler(expected_feed_id="91379").redirect_request(
            request, None, 302, "Found", {}, redirect_url
        )
    assert "SECRET" not in str(exc.value)


def test_awin_download_redirect_can_remain_on_same_feed() -> None:
    request = Request(
        "https://productdata.awin.com/datafeed/download/apikey/SECRET/fid/91379/"
    )
    url = (
        "https://datafeed.api.productserve.com/datafeed/download/apikey/"
        "SECRET/fid/91379/format/csv/"
    )
    redirected = awin.AwinRedirectHandler(expected_feed_id="91379").redirect_request(
        request, None, 302, "Found", {}, url
    )
    assert redirected.full_url == url


def test_wrong_feed_list_url_stops_before_private_download(monkeypatch) -> None:
    calls: list[str] = []
    wrong_list = CSV.replace("/fid/91379/", "/fid/99999/", 1)

    def fake_read(url: str, *, max_bytes: int, expected_feed_id=None) -> bytes:
        calls.append(url)
        return wrong_list.encode("utf-8")

    monkeypatch.setattr(awin, "_read_url", fake_read)
    with pytest.raises(ValueError, match="awin_feed_download_feed_id_mismatch"):
        awin.download_feed_from_list(
            api_key="SECRET",
            advertiser_id="31081",
            feed_id="91379",
            output_path=Path("never-created.csv"),
            report_path=None,
        )
    assert len(calls) == 1 and "/datafeed/list/" in calls[0]
