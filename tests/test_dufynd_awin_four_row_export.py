from __future__ import annotations

import base64
import json
import os
import subprocess
import sys
from pathlib import Path
from urllib.parse import quote

import pytest
from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric.x25519 import X25519PrivateKey, X25519PublicKey
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.hkdf import HKDF
from scripts.export_dufynd_awin_four_rows import (
    AAD,
    TARGETS,
    encrypt_report,
    extract_rows,
    safe_url,
)

MERCHANT = "https://www.topparfuemerie.de/yves-saint-laurent-libre-edp-vapo"
TRACKING = "https://www.awin1.com/pclick.php?p=37127262034&a=3099222&m=31081"
IMAGE = "https://www.topparfuemerie.de/media/catalog/product/8/5/856448_3614272648425_051.png"


def rows() -> list[dict]:
    return [
        {
            "merchant_product_id": sku,
            "aw_product_id": "37127262034",
            "merchant_deep_link": MERCHANT,
            "aw_deep_link": TRACKING,
            "merchant_image_url": IMAGE,
            "search_price": "153.95",
            "currency": "EUR",
            "last_updated": "2026-10-07 01:21:17",
            "description": "DO_NOT_EXPORT",
        }
        for sku in TARGETS
    ]


def decrypt(envelope: bytes, private: X25519PrivateKey) -> dict:
    data = json.loads(envelope)
    binary = {
        k: base64.b64decode(data[k]) for k in ("ephemeral_public", "salt", "nonce", "ciphertext")
    }
    public = private.public_key().public_bytes_raw()
    ephemeral = binary["ephemeral_public"]
    key = HKDF(
        algorithm=hashes.SHA256(), length=32, salt=binary["salt"], info=AAD + public + ephemeral
    ).derive(private.exchange(X25519PublicKey.from_public_bytes(ephemeral)))
    return json.loads(AESGCM(key).decrypt(binary["nonce"], binary["ciphertext"], AAD))


def test_only_four_rows_and_allowlisted_fields_preserve_original_values() -> None:
    source = rows() + [{"merchant_product_id": "OTHER", "aw_deep_link": "SECRET"}]
    result = extract_rows(source)
    assert len(result["rows"]) == 4
    assert not result["activation_allowed"] and not result["tracking_verified"]
    assert "DO_NOT_EXPORT" not in json.dumps(result)
    assert "OTHER" not in json.dumps(result)
    for row in result["rows"]:
        assert row["fields"]["last_updated"] == "2026-10-07 01:21:17"
        assert row["fields"]["aw_deep_link"] == TRACKING
        assert "gtin" in row["missing_fields"]
        assert "in_stock" in row["missing_fields"]
        assert not row["withheld_fields"]


@pytest.mark.parametrize("source", [rows()[:-1], rows() + [rows()[0]]])
def test_missing_or_duplicate_rows_fail_closed(source: list[dict]) -> None:
    with pytest.raises(ValueError, match="exactly_one_row"):
        extract_rows(source)


@pytest.mark.parametrize(
    "url",
    [
        MERCHANT + "?api_key=secret",
        MERCHANT + "?%74oken=secret",
        MERCHANT + "?x=eyJzdXBlciI6InNlY3JldCJ9",
        MERCHANT + "#access_token=secret",
        MERCHANT.replace("https://", "https://user:secret@"),
        MERCHANT.replace("https://", "http://"),
        MERCHANT.replace(".de/", ".de:443/"),
        MERCHANT.replace(".de/", ".de.evil.test/"),
        MERCHANT + "?sku=856448&sku=780879",
        "https://www.topparfuemerie.de/media/apikey/secret",
        MERCHANT + "?sku=secret",
        MERCHANT + "\n",
        MERCHANT + "?___store=default%2526token%253Dsecret",
    ],
)
def test_unsafe_merchant_values_are_not_exportable(url: str) -> None:
    assert not safe_url(url, "merchant_deep_link")


@pytest.mark.parametrize(
    "url",
    [
        TRACKING + "&token=secret",
        TRACKING.replace("3099222", "123"),
        TRACKING.replace("31081", "999"),
        TRACKING.replace("p=37127262034", "p=secret"),
        TRACKING + "&clickref=secret",
        TRACKING + "&a=3099222",
        "https://productdata.awin.com/datafeed/download/apikey/secret",
        "https://www.awin1.com/cread.php?awinaffid=3099222&awinmid=31081&ued="
        + quote(MERCHANT + "?token=secret", safe=""),
        "https://www.awin1.com/cread.php?awinaffid=3099222&awinmid=31081&ued="
        + quote("https://evil.test/", safe=""),
    ],
)
def test_unsafe_tracking_and_nested_destinations_are_rejected(url: str) -> None:
    assert not safe_url(url, "aw_deep_link")


def test_safe_nested_destination_and_explicit_variant_selector() -> None:
    assert safe_url(MERCHANT + "?sku=856448", "merchant_deep_link")
    assert safe_url(
        "https://www.awin1.com/cread.php?awinaffid=3099222&awinmid=31081&ued="
        + quote(MERCHANT, safe=""),
        "aw_deep_link",
    )
    assert safe_url(IMAGE, "merchant_image_url")
    assert not safe_url(IMAGE + "?signature=secret", "merchant_image_url")


def test_unsafe_value_is_absent_even_in_encrypted_plaintext() -> None:
    source = rows()
    source[0]["aw_deep_link"] = TRACKING + "&api_key=NEVER_EXPORT"
    source[0]["currency"] = "NEVER_EXPORT"
    source[1]["gtin"] = ""
    source[1]["in_stock"] = "false"
    result = extract_rows(source, "NEVER_EXPORT")
    assert "NEVER_EXPORT" not in json.dumps(result)
    assert set(result["rows"][0]["withheld_fields"]) == {"aw_deep_link", "currency"}
    assert "gtin" in result["rows"][1]["empty_fields"]
    assert result["rows"][1]["fields"]["in_stock"] == "false"
    key = X25519PrivateKey.generate()
    encrypted = encrypt_report(result, key.public_key().public_bytes_raw())
    assert decrypt(encrypted, key) == result
    assert b"merchant_deep_link" not in encrypted and MERCHANT.encode() not in encrypted
    with pytest.raises(InvalidTag):
        decrypt(encrypted, X25519PrivateKey.generate())
    tampered = json.loads(encrypted)
    raw = bytearray(base64.b64decode(tampered["ciphertext"]))
    raw[0] ^= 1
    tampered["ciphertext"] = base64.b64encode(raw).decode()
    with pytest.raises(InvalidTag):
        decrypt(json.dumps(tampered).encode(), key)


@pytest.mark.parametrize("secret", ["3099222", "856448", "libre"])
def test_known_secret_scan_covers_otherwise_allowed_values(secret: str) -> None:
    result = extract_rows(rows(), secret)
    assert all(secret not in str(row["fields"]) for row in result["rows"])


def test_cli_does_not_echo_feed_parser_errors_or_secret(tmp_path: Path) -> None:
    feed = tmp_path / "feed.csv"
    feed.write_text("merchant_product_id,aw_deep_link\n780879,TOPSECRET\n")
    recipient = tmp_path / "recipient.pub"
    recipient.write_text(X25519PrivateKey.generate().public_key().public_bytes_raw().hex())
    output = tmp_path / "encrypted.json"
    run = subprocess.run(
        [
            sys.executable,
            "scripts/export_dufynd_awin_four_rows.py",
            "--feed",
            str(feed),
            "--recipient",
            str(recipient),
            "--output",
            str(output),
        ],
        capture_output=True,
        text=True,
        env={**os.environ, "AWIN_DATA_FEED_API_KEY": "TOPSECRET"},
    )
    assert run.returncode == 2
    assert run.stderr.strip() == "four_row_export_failed_closed"
    assert "TOPSECRET" not in run.stdout + run.stderr
    assert not output.exists()


def test_public_repository_upload_is_encrypted_and_expires_in_one_day() -> None:
    workflow = Path(".github/workflows/dufynd-awin-feed-revalidation.yml").read_text()
    block = workflow.split("name: Upload recipient-encrypted evidence only")[1].split("- name:")[0]
    assert "retention-days: 1" in block
    assert "path: ${{ runner.temp }}/four-row-evidence.encrypted.json" in block
    assert "*.json" not in block and "top-parfuemerie.csv" not in block
    assert "branches: [scentai-mvp]" in workflow
    assert "paths: [.github/dufynd-awin-evidence-recipient.pub]" in workflow
