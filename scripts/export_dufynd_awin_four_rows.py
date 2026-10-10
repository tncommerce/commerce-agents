"""Export four allowlisted source rows, filtered before recipient-only encryption.

Never logs row values and never writes plaintext. This does not grant offer,
stock, freshness, image or tracking approval. Uses the existing bounded reader.
"""

from __future__ import annotations

import argparse
import base64
import hashlib
import json
import os
import re
import sys
from datetime import UTC, datetime
from pathlib import Path
from urllib.parse import parse_qsl, unquote, urlsplit

from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric.x25519 import X25519PrivateKey, X25519PublicKey
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.hkdf import HKDF

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "examples"))
from retail.api.merchant_feed_reader import read_merchant_feed_rows  # noqa: E402

TARGETS = ("780879", "825869", "787670", "856448")
URL_FIELDS = ("merchant_deep_link", "aw_deep_link", "merchant_image_url")
FIELD_PATTERNS = {
    "aw_product_id": r"[0-9]{1,20}",
    "merchant_product_id": r"[0-9]{1,20}",
    "search_price": r"[0-9]{1,7}(?:[.,][0-9]{1,4})?",
    "price": r"[0-9]{1,7}(?:[.,][0-9]{1,4})?",
    "currency": r"[A-Z]{3}",
    "last_updated": r"[0-9]{4}-[0-9]{2}-[0-9]{2}[ T][0-9: .+Z-]{5,24}",
    "ean": r"[0-9]{8,14}",
    "gtin": r"[0-9]{8,14}",
    "product_GTIN": r"[0-9]{8,14}",
    "upc": r"[0-9]{8,14}",
    "in_stock": r"(?i:true|false|yes|no|0|1)",
    "stock_status": r"(?i:in stock|out of stock|instock|outofstock|preorder|backorder)",
    "availability": r"(?i:in stock|out of stock|instock|outofstock|preorder|backorder)",
    "stock_quantity": r"[0-9]{1,8}",
}
FIELDS = (*FIELD_PATTERNS, *URL_FIELDS)
AAD = b"DUFYND/awin/31081/91379/four-row-evidence/v1"


def _contains_secret(value: str, secret: str) -> bool:
    if not secret:
        return False
    forms = (
        secret,
        base64.b64encode(secret.encode()).decode(),
        base64.urlsafe_b64encode(secret.encode()).decode(),
        secret.encode().hex(),
    )
    return any(form in value for form in forms)


def safe_url(value: str, field: str, secret: str = "", depth: int = 0) -> bool:
    """Reject whole unsafe values; never redact/re-encode a credential URL."""
    if not value or len(value) > 4096 or depth > 1:
        return False
    decoded = value
    for _ in range(5):
        if _contains_secret(decoded, secret):
            return False
        updated = unquote(decoded)
        if updated == decoded:
            break
        decoded = updated
    else:
        return False
    if re.search(r"[\s\\\x00-\x1f\x7f]", decoded):
        return False
    try:
        url = urlsplit(value)
        if (
            url.scheme != "https"
            or url.username
            or url.password
            or url.fragment
            or url.port is not None
        ):
            return False
        query = parse_qsl(url.query, keep_blank_values=True, strict_parsing=True)
        if len({k for k, _ in query}) != len(query):
            return False
        if field == "aw_deep_link":
            if url.hostname not in {"awin1.com", "www.awin1.com"}:
                return False
            params = dict(query)
            if url.path == "/pclick.php":
                expected = {"a": "3099222", "m": "31081"}
                allowed = {*expected, "p"}
                if not re.fullmatch(r"[0-9]{1,20}", params.get("p", "")):
                    return False
            elif url.path == "/cread.php":
                expected = {"awinaffid": "3099222", "awinmid": "31081"}
                allowed = {*expected, "ued"}
                if not safe_url(params.get("ued", ""), "merchant_deep_link", secret, depth + 1):
                    return False
            else:
                return False
            return set(params) == allowed and all(params.get(k) == v for k, v in expected.items())
        if url.hostname not in {"topparfuemerie.de", "www.topparfuemerie.de"}:
            return False
        if field == "merchant_image_url":
            return not query and bool(
                re.fullmatch(
                    r"/media/catalog/product/(?:[a-z0-9]/){0,3}[0-9_]+\.(?:png|jpg|jpeg|webp)",
                    url.path,
                )
            )
        if not re.fullmatch(r"/[a-z0-9]+(?:-[a-z0-9]+)*(?:\.html)?", url.path):
            return False
        # Only known store/variant selectors; no arbitrary IDs, tokens or redirects.
        return all(
            (key == "___store" and val in {"default", "de"}) or (key == "sku" and val in TARGETS)
            for key, val in query
        )
    except ValueError:
        return False


def extract_rows(rows: list[dict], secret: str = "") -> dict:
    selected = {sku: [] for sku in TARGETS}
    for row in rows:
        sku = row.get("merchant_product_id")
        if sku in selected:
            selected[sku].append(row)
    # Duplicates are ambiguous: never silently pick a row or export extra rows.
    if any(len(matches) != 1 for matches in selected.values()):
        raise ValueError("exactly_one_row_per_target_required")
    output = []
    for sku, matches in selected.items():
        row = matches[0]
        fields, withheld, missing, empty = {}, [], [], []
        for name in FIELDS:
            if name not in row:
                missing.append(name)
                continue
            value = row[name]
            if value == "":
                fields[name] = value
                empty.append(name)
                continue
            safe = isinstance(value, str) and not _contains_secret(value, secret)
            if safe:
                safe = (
                    safe_url(value, name, secret)
                    if name in URL_FIELDS
                    else bool(re.fullmatch(FIELD_PATTERNS[name], value))
                )
            if safe:
                fields[name] = value
            else:
                withheld.append(name)
        output.append(
            {
                "merchant_product_id": sku,
                "fields": fields,
                "missing_fields": missing,
                "empty_fields": empty,
                "withheld_fields": withheld,
            }
        )
    return {
        "version": 1,
        "advertiser_id": "31081",
        "feed_id": "91379",
        "checked_at": datetime.now(UTC).isoformat(),
        "rows": output,
        "activation_allowed": False,
        "tracking_verified": False,
    }


def encrypt_report(report: dict, recipient: bytes) -> bytes:
    public = X25519PublicKey.from_public_bytes(recipient)
    ephemeral = X25519PrivateKey.generate()
    ephemeral_public = ephemeral.public_key().public_bytes_raw()
    salt, nonce = os.urandom(32), os.urandom(12)
    key = HKDF(
        algorithm=hashes.SHA256(), length=32, salt=salt, info=AAD + recipient + ephemeral_public
    ).derive(ephemeral.exchange(public))
    ciphertext = AESGCM(key).encrypt(nonce, json.dumps(report).encode(), AAD)
    return json.dumps(
        {
            "version": 1,
            "recipient_sha256": hashlib.sha256(recipient).hexdigest(),
            **{
                name: base64.b64encode(value).decode()
                for name, value in {
                    "ephemeral_public": ephemeral_public,
                    "salt": salt,
                    "nonce": nonce,
                    "ciphertext": ciphertext,
                }.items()
            },
        }
    ).encode()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--feed", required=True, type=Path)
    parser.add_argument("--recipient", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    try:
        recipient = bytes.fromhex(args.recipient.read_text().strip())
        secret = os.environ.get("AWIN_DATA_FEED_API_KEY", "")
        if not secret:
            raise ValueError("secret_scan_unavailable")
        rows = read_merchant_feed_rows(args.feed)
        report = extract_rows(rows, secret)
        if _contains_secret(json.dumps(report), secret):
            raise ValueError("secret_scan_rejected")
        encrypted = encrypt_report(report, recipient)
        with args.output.open("xb") as handle:
            os.chmod(args.output, 0o600)
            handle.write(encrypted)
    except Exception:
        # Reader/parser exceptions may contain feed-derived values. Never echo them.
        print("four_row_export_failed_closed", file=sys.stderr)
        return 2
    print("four_row_evidence_encrypted; no activation or tracking approval")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
