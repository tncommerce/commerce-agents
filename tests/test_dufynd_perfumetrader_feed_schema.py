from __future__ import annotations

import csv
import io
import json
from email.message import Message
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from cryptography.hazmat.primitives.asymmetric.x25519 import X25519PrivateKey
from scripts import fetch_dufynd_awin_data_feed as download
from scripts import review_dufynd_perfumetrader_catalog as review
from tests.test_dufynd_perfumetrader_private_catalog import (
    MAPPING,
    META,
    NOW,
    PRODUCT,
    SECRET,
    source_row,
)

HTTP = {"http_status": 200, "content_type": "text/csv"}


def inspect(tmp_path, payload, http=None):
    source = tmp_path / "source.csv"
    source.write_bytes(payload)
    return review.verified_product_rows(source, HTTP if http is None else http)


def csv_bytes(rows, delimiter=","):
    result = io.StringIO()
    writer = csv.DictWriter(result, fieldnames=list(rows[0]), delimiter=delimiter)
    writer.writeheader()
    writer.writerows(rows)
    return result.getvalue().encode()


@pytest.mark.parametrize("delimiter,label", [(",", "comma"), (";", "semicolon"), ("\t", "tab")])
def test_real_csv_requires_product_headers_and_counted_rows(tmp_path, delimiter, label):
    rows, schema = inspect(tmp_path, csv_bytes([source_row()], delimiter))
    assert rows == [source_row()]
    assert schema["status"] == "VERIFIED_PRODUCT_CSV"
    assert schema["delimiter"] == label
    assert schema["row_count"] == schema["valid_identity_row_count"] == 1
    assert "product_name" in schema["recognized_headers"]
    report = review.review_rows([PRODUCT], MAPPING, rows, META, SECRET, NOW, feed_validation=schema)
    assert report["profiles"][0]["status"] == "EXACT_AND_FRESH"


@pytest.mark.parametrize(
    "payload",
    [
        b"error,message\n403,Access denied\n",
        b"<!DOCTYPE html><html><body>Access denied, retry</body></html>",
        b"<?xml version='1.0'?><error>Denied</error>",
        b'{"error":"denied"}',
        b"PK\x03\x04fake zip",
        b"",
        b"product_name,merchant_product_id,search_price\n",
        b"product_name,merchant_product_id,search_price,search_price\nx,1,2,3\n",
        b"product_name,merchant_product_id,search_price\nx,1\n",
        b"product_name,merchant_product_id,search_price\nx,1,2,extra\n",
    ],
)
def test_error_empty_wrong_header_or_malformed_response_never_becomes_not_found(tmp_path, payload):
    rows, schema = inspect(tmp_path, payload)
    assert rows == []
    assert schema["status"] == "BLOCKED_UNVERIFIED_SCHEMA"
    assert schema["reasons"]
    report = review.review_rows([PRODUCT], MAPPING, rows, META, SECRET, NOW, feed_validation=schema)
    assert report["profiles"][0]["status"] == "BLOCKED"
    assert report["profiles"][0]["source_schema_status"] == "BLOCKED_UNVERIFIED_SCHEMA"
    assert report["profiles"][0]["offer_activation_allowed"] is False


@pytest.mark.parametrize(
    "http",
    [
        {},
        {"http_status": 206, "content_type": "text/csv"},
        {"http_status": 200, "content_type": "text/html"},
        {"http_status": 200, "content_type": "unrecognized"},
    ],
)
def test_missing_partial_or_wrong_protocol_evidence_blocks_even_parseable_csv(tmp_path, http):
    rows, schema = inspect(tmp_path, csv_bytes([source_row()]), http)
    assert rows == []
    assert schema["status"] == "BLOCKED_UNVERIFIED_SCHEMA"


def test_missing_schema_proof_blocks_absence_without_freshening_sources():
    report = review.review_rows([PRODUCT], MAPPING, [], META, SECRET, NOW)
    assert report["profiles"][0]["status"] == "BLOCKED"
    assert report["source_metadata"]["last_imported"] == "2026-10-27 16:02:27"
    assert report["feed_validation"]["reasons"] == ["schema_evidence_missing"]


def test_not_found_only_after_valid_schema_with_other_products(tmp_path):
    rows, schema = inspect(
        tmp_path, csv_bytes([source_row(product_name="Different brand product 50 ml", ean="")])
    )
    report = review.review_rows([PRODUCT], MAPPING, rows, META, SECRET, NOW, feed_validation=schema)
    assert report["profiles"][0]["status"] == "NOT_FOUND"


def test_diagnostics_never_export_arbitrary_header_or_body_values(tmp_path):
    payload = csv_bytes([source_row() | {SECRET: "private customer record"}])
    _, schema = inspect(tmp_path, payload)
    assert schema["unknown_header_count"] == 1
    assert SECRET not in json.dumps(schema)
    assert "private customer record" not in json.dumps(schema)


@pytest.mark.parametrize("value", ["ERROR", "NaN", "Inf", "-Infinity", "EUR 10.00"])
def test_product_shaped_errors_and_non_numeric_prices_cannot_count_as_verified_rows(
    tmp_path, value
):
    row = {"product_name": "Access denied", "merchant_product_id": "ERROR", "search_price": value}
    rows, schema = inspect(tmp_path, csv_bytes([row]))
    assert rows == []
    assert schema["valid_identity_row_count"] == 0
    assert schema["status"] == "BLOCKED_UNVERIFIED_SCHEMA"


def test_awin_id_fallback_requires_numeric_id(tmp_path):
    rows, schema = inspect(
        tmp_path,
        csv_bytes(
            [
                {
                    "product_name": "Unverified response",
                    "aw_product_id": "ERROR",
                    "search_price": "3.95",
                }
            ]
        ),
    )
    assert rows == []
    assert schema["status"] == "BLOCKED_UNVERIFIED_SCHEMA"


def test_zero_price_is_structural_evidence_but_cannot_pass_commerce_completeness(tmp_path):
    rows, schema = inspect(tmp_path, csv_bytes([source_row(search_price="0")]))
    assert schema["status"] == "VERIFIED_PRODUCT_CSV"
    report = review.review_rows([PRODUCT], MAPPING, rows, META, SECRET, NOW, feed_validation=schema)
    assert report["profiles"][0]["status"] == "EXACT_BUT_INCOMPLETE"


def test_schema_proof_does_not_infer_eur_for_missing_or_other_currency(tmp_path):
    for currency in ("", "USD"):
        rows, schema = inspect(tmp_path, csv_bytes([source_row(currency=currency)]))
        assert schema["status"] == "VERIFIED_PRODUCT_CSV"
        report = review.review_rows(
            [PRODUCT], MAPPING, rows, META, SECRET, NOW, feed_validation=schema
        )
        assert report["profiles"][0]["status"] == "EXACT_BUT_INCOMPLETE"


@pytest.mark.parametrize(
    "content_type,expected",
    [
        ("text/csv; charset=utf-8", "text/csv"),
        ("text/html", "text/html"),
        (SECRET + "/plain", "unrecognized"),
        (None, "unrecognized"),
    ],
)
def test_http_metadata_is_opt_in_and_only_protocol_enums(content_type, expected):
    response = MagicMock()
    response.__enter__.return_value = response
    response.status = 200
    response.headers = Message()
    if content_type is not None:
        response.headers["Content-Type"] = content_type
    response.read.side_effect = [b"fixture", b""]
    opener = MagicMock()
    opener.open.return_value = response
    metadata = {}
    with patch.object(download, "build_opener", return_value=opener):
        payload = download._read_url(
            "https://example.invalid", max_bytes=64, response_metadata=metadata
        )
    assert payload == b"fixture"
    assert metadata == {"http_status": 200, "content_type": expected}
    assert SECRET not in json.dumps(metadata)


def test_bad_schema_exports_only_encrypted_blocker_and_cleans_temp(tmp_path, monkeypatch, capsys):
    public = tmp_path / "recipient.pub"
    public.write_text(X25519PrivateKey.generate().public_key().public_bytes_raw().hex())
    output = tmp_path / "evidence.encrypted.json"
    monkeypatch.setenv("AWIN_DATA_FEED_API_KEY", SECRET)
    monkeypatch.setenv("RUNNER_TEMP", str(tmp_path))
    captured = {}

    def source_download(**kwargs):
        assert kwargs["capture_product_response_metadata"] is True
        kwargs["output_path"].write_text("error,message\n403," + SECRET + "\n")
        return META | {"product_http": HTTP}

    def encryption(report, recipient):
        captured.update(report)
        assert len(recipient) == 32
        return b"opaque-synthetic-ciphertext"

    monkeypatch.setattr(review, "download_feed_from_list", source_download)
    monkeypatch.setattr(review, "encrypt_report", encryption)
    monkeypatch.setattr("sys.argv", ["review", "--recipient", str(public), "--output", str(output)])
    assert review.main() == 0
    assert len(captured["profiles"]) == 57
    assert {p["status"] for p in captured["profiles"]} == {"BLOCKED"}
    assert captured["feed_validation"]["status"] == "BLOCKED_UNVERIFIED_SCHEMA"
    assert output.read_bytes() == b"opaque-synthetic-ciphertext"
    assert not list(Path(tmp_path).glob("dufynd-pt-*"))
    log = capsys.readouterr()
    assert SECRET not in log.out + log.err + json.dumps(captured)
