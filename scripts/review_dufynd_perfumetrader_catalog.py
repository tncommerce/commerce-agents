"""Private, bounded DE feed review; never approves offers or downloads images.

Only the existing publisher secret and official Awin feed-list URL are used.
Raw feed bytes live in a temporary directory. The only persisted output is a
recipient-encrypted, allowlisted report for the 37 public fragrance profiles.
"""

from __future__ import annotations

import argparse
import base64
import hashlib
import json
import os
import re
import sys
import tempfile
from datetime import UTC, datetime, timedelta
from decimal import Decimal, InvalidOperation
from pathlib import Path
from urllib.parse import parse_qsl, unquote, urlsplit

from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric.x25519 import X25519PrivateKey, X25519PublicKey
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.hkdf import HKDF

if __package__:
    from .fetch_dufynd_awin_data_feed import download_feed_from_list
    from .report_dufynd_public_photo_feed_leads import VOLUME, feed_name_matches, norm
else:
    from fetch_dufynd_awin_data_feed import download_feed_from_list
    from report_dufynd_public_photo_feed_leads import VOLUME, feed_name_matches, norm

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "examples"))
from retail.api.merchant_feed_reader import read_merchant_feed_rows  # noqa: E402

ADVERTISER, FEED, PUBLISHER = "11672", "29975", "3099222"
AAD = b"DUFYND/awin/11672/29975/public-catalog-private-review/v1"
CATALOG = ROOT / "examples/retail/storefront-web/lib/generated/public-fragrances.json"
MAPPINGS = ROOT / "examples/retail/data/merchant_product_mappings.json"
ALLOWED_FIELDS = (
    "aw_product_id",
    "merchant_product_id",
    "product_name",
    "brand_name",
    "brand",
    "ean",
    "gtin",
    "product_GTIN",
    "upc",
    "size",
    "product_size",
    "specifications",
    "search_price",
    "price",
    "currency",
    "last_updated",
    "last_update",
    "in_stock",
    "stock_status",
    "stock_quantity",
    "availability",
    "is_for_sale",
    "delivery_cost",
    "delivery_time",
    "delivery_restrictions",
    "delivery_weight",
    "shipping_cost",
    "shipping_country",
    "delivery_country",
    "condition",
    "merchant_deep_link",
    "aw_deep_link",
    "merchant_image_url",
)
URL_FIELDS = {"merchant_deep_link", "aw_deep_link", "merchant_image_url"}
GTIN_FIELDS = ("ean", "gtin", "product_GTIN", "upc")


def contains_secret(value: str, secret: str) -> bool:
    if not secret:
        return True
    forms = (
        secret,
        base64.b64encode(secret.encode()).decode(),
        base64.urlsafe_b64encode(secret.encode()).decode(),
        secret.encode().hex(),
    )
    for _ in range(5):
        if any(form in value for form in forms):
            return True
        decoded = unquote(value)
        if decoded == value:
            return False
        value = decoded
    return True


def safe_url(value: str, field: str, secret: str, depth: int = 0) -> bool:
    if depth > 1 or len(value) > 4096 or contains_secret(value, secret):
        return False
    try:
        p = urlsplit(value)
        if (
            p.scheme != "https"
            or p.port is not None
            or p.username
            or p.password
            or p.fragment
            or re.search(r"[\s\\\x00-\x1f\x7f]", unquote(value))
        ):
            return False
        pairs = parse_qsl(p.query, keep_blank_values=True, strict_parsing=True)
        if len({k for k, _ in pairs}) != len(pairs):
            return False
        params = dict(pairs)
        if field == "aw_deep_link":
            if p.hostname not in {"awin1.com", "www.awin1.com"}:
                return False
            if p.path == "/pclick.php":
                return (
                    set(params) == {"a", "m", "p"}
                    and params["a"] == PUBLISHER
                    and params["m"] == ADVERTISER
                    and bool(re.fullmatch(r"[0-9]{1,20}", params["p"]))
                )
            if p.path == "/cread.php":
                return (
                    set(params) == {"awinaffid", "awinmid", "ued"}
                    and params["awinaffid"] == PUBLISHER
                    and params["awinmid"] == ADVERTISER
                    and safe_url(params["ued"], "merchant_deep_link", secret, depth + 1)
                )
            return False
        return (
            p.hostname in {"perfumetrader.de", "www.perfumetrader.de"}
            and not pairs
            and bool(p.path)
            and p.path != "/"
        )
    except ValueError:
        return False


def canonical_gtin(value: object) -> str | None:
    text = str(value or "").strip()
    if not re.fullmatch(r"(?:\d{8}|\d{12}|\d{13}|\d{14})", text):
        return None
    total = sum(int(ch) * (3 if i % 2 == 0 else 1) for i, ch in enumerate(text[-2::-1]))
    return text.zfill(14) if (10 - total % 10) % 10 == int(text[-1]) else None


def public_profiles(catalog: dict) -> list[dict]:
    products = [
        p
        for p in catalog["products"]
        if p.get("validation", {}).get("catalog_ready")
        and not any(str(x).strip() for x in p.get("validation", {}).get("blockers", []))
    ]
    if len(products) != 37 or len({p["product_id"] for p in products}) != 37:
        raise ValueError("public_catalog_scope_changed")
    return [
        {k: p[k] for k in ("product_id", "brand", "name", "concentration", "volume_ml")}
        for p in products
    ]


def safe_fields(row: dict, secret: str) -> tuple[dict, list[str]]:
    fields, withheld = {}, []
    for name in ALLOWED_FIELDS:
        if name not in row:
            continue
        value = row[name]
        if (
            (
                not isinstance(value, str)
                or len(value) > 4096
                or contains_secret(value, secret)
                or any(ord(c) < 32 or ord(c) == 127 for c in value)
            )
            or name in URL_FIELDS
            and value
            and not safe_url(value, name, secret)
        ):
            withheld.append(name)
        else:
            fields[name] = value
    return fields, withheld


def valid_amount(value: str, *, allow_zero: bool) -> bool:
    if not re.fullmatch(r"[0-9]{1,7}(?:[.,][0-9]{1,4})?", value):
        return False
    try:
        amount = Decimal(value.replace(",", "."))
        return amount >= 0 if allow_zero else amount > 0
    except InvalidOperation:
        return False


def row_timestamp(row: dict) -> tuple[str | None, datetime | None]:
    original = row.get("last_updated") or row.get("last_update") or None
    if not original:
        return None, None
    try:
        stamps = [
            datetime.fromisoformat(row[f].replace("Z", "+00:00"))
            for f in ("last_updated", "last_update")
            if row.get(f)
        ]
        if any(dt.tzinfo is None for dt in stamps):
            return original, None
        normalized = {dt.astimezone(UTC) for dt in stamps}
        return original, next(iter(normalized)) if len(normalized) == 1 else None
    except (ValueError, TypeError):
        return original, None


def review_rows(
    profiles: list[dict],
    mappings: dict,
    rows: list[dict],
    metadata: dict,
    secret: str,
    now: datetime,
) -> dict:
    if (
        metadata.get("advertiser_id") != ADVERTISER
        or metadata.get("feed_id") != FEED
        or metadata.get("joined") is not True
        or metadata.get("primary_region") != "DE"
        or str(metadata.get("language")).casefold() not in {"german", "de", "deutsch"}
    ):
        raise ValueError("feed_identity_or_membership_not_verified")
    results = []
    for product in profiles:
        pid = product["product_id"]
        expected = {
            canonical_gtin(m.get("gtin") or m.get("ean"))
            for m in mappings.get("mappings", [])
            if m.get("product_id") == pid
        }
        expected.discard(None)
        candidates = []
        for row in rows:
            gtins = {canonical_gtin(row.get(f)) for f in GTIN_FIELDS}
            gtins.discard(None)
            title_tokens = set(norm(row.get("product_name")).split())
            relevant = (
                set(norm(product["name"]).split()) <= title_tokens
                and set(norm(product["brand"]).split()) <= title_tokens
            ) or bool(expected & gtins)
            if not relevant:
                continue
            volumes = [
                float(v.replace(",", ".")) for v in VOLUME.findall(row.get("product_name") or "")
            ]
            title_exact = feed_name_matches(product, row) and volumes == [product["volume_ml"]]
            gtin_exact = len(expected) == 1 and gtins == expected
            contradictory_gtin = len(gtins) > 1 or bool(expected and gtins and not expected & gtins)
            explicit_sizes = [
                float(v.replace(",", "."))
                for field in ("size", "product_size")
                for v in VOLUME.findall(row.get(field) or "")
            ]
            size_conflict = any(v != product["volume_ml"] for v in explicit_sizes)
            size_incomplete = any(
                row.get(f) and not VOLUME.fullmatch(row[f].strip())
                for f in ("size", "product_size")
            )
            fields, withheld = safe_fields(row, secret)
            original, dt = row_timestamp(fields)
            reasons = []
            if not gtin_exact:
                reasons.append("verified_unique_gtin_match_missing")
            if not title_exact:
                reasons.append("exact_name_concentration_volume_refill_match_missing")
            if contradictory_gtin:
                reasons.append("gtin_mismatch")
            if size_conflict:
                reasons.append("explicit_size_conflict")
            if size_incomplete:
                reasons.append("explicit_size_field_unverified")
            stock_values = [
                fields.get(f, "").strip().casefold()
                for f in ("in_stock", "stock_status", "availability")
                if fields.get(f, "").strip()
            ]
            positives = {"1", "true", "yes", "in stock", "instock", "in_stock", "available"}
            negatives = {
                "0",
                "false",
                "no",
                "out of stock",
                "outofstock",
                "out_of_stock",
                "unavailable",
            }
            stock_known = bool(stock_values) and all(
                v in positives | negatives for v in stock_values
            )
            stock_conflict = bool(set(stock_values) & positives and set(stock_values) & negatives)
            quantity = fields.get("stock_quantity", "").strip()
            if quantity:
                if not valid_amount(quantity, allow_zero=True):
                    stock_conflict = True
                else:
                    zero = Decimal(quantity.replace(",", ".")) == 0
                    stock_conflict = stock_conflict or bool(
                        (zero and set(stock_values) & positives)
                        or (not zero and set(stock_values) & negatives)
                    )
            if not stock_known or stock_conflict:
                reasons.append("explicit_unambiguous_stock_missing")
            stock_available = bool(
                stock_known and not stock_conflict and set(stock_values) <= positives
            )
            sale_value = fields.get("is_for_sale", "").strip().casefold()
            purchase_allowed = sale_value in {"1", "true", "yes"}
            if not purchase_allowed:
                reasons.append("explicit_purchase_permission_missing_or_false")
            if not stock_available:
                reasons.append("source_not_confirmed_orderable")
            shipping_costs = [
                fields[f].strip()
                for f in ("delivery_cost", "shipping_cost")
                if fields.get(f, "").strip()
            ]
            countries = [
                fields[f].strip().casefold()
                for f in ("delivery_country", "shipping_country")
                if fields.get(f, "").strip()
            ]
            cost_valid = bool(shipping_costs) and all(
                valid_amount(c, allow_zero=True) for c in shipping_costs
            )
            costs_agree = (
                cost_valid and len({Decimal(c.replace(",", ".")) for c in shipping_costs}) == 1
            )
            if (
                not costs_agree
                or not countries
                or any(c not in {"de", "germany", "deutschland"} for c in countries)
            ):
                reasons.append("explicit_unambiguous_de_shipping_cost_or_destination_missing")
            if (
                not valid_amount(
                    fields.get("search_price") or fields.get("price") or "", allow_zero=False
                )
                or fields.get("currency") != "EUR"
            ):
                reasons.append("price_or_eur_missing")
            if dt is None or dt > now:
                reasons.append("original_product_timestamp_with_timezone_missing_or_future")
            if not fields.get("merchant_product_id"):
                reasons.append("merchant_sku_missing")
            if not fields.get("aw_deep_link"):
                reasons.append("official_publisher_advertiser_bound_tracking_link_missing")
            if withheld:
                reasons.append("unsafe_or_nonallowlisted_values_withheld")
            if contradictory_gtin or size_conflict or not title_exact:
                status = "MISMATCH"
            elif dt is not None and dt <= now and now - dt > timedelta(hours=72):
                status = "STALE"
            else:
                status = "EXACT_BUT_INCOMPLETE" if reasons else "EXACT_AND_FRESH"
            candidates.append(
                {
                    "status": status,
                    "title_exact": title_exact,
                    "gtin_exact": gtin_exact,
                    "fields": fields,
                    "withheld_fields": withheld,
                    "reasons": reasons,
                    "source_row_sha256": hashlib.sha256(
                        json.dumps(row, sort_keys=True, ensure_ascii=False).encode()
                    ).hexdigest(),
                    "original_product_timestamp": original,
                    "original_product_timestamp_utc": dt.isoformat() if dt else None,
                    "stock_available": stock_available,
                    "source_purchase_eligible": stock_available and purchase_allowed,
                    "tracking_status": "OFFICIAL_FEED_LINK_PRESENT_UNCLICKED"
                    if fields.get("aw_deep_link")
                    else "HOLD",
                    "tracking_click_verified": False,
                }
            )
        candidates.sort(
            key=lambda x: (not x["title_exact"], not x["gtin_exact"], x["source_row_sha256"])
        )
        exact = [
            c
            for c in candidates
            if c["title_exact"]
            and not {"gtin_mismatch", "explicit_size_conflict"} & set(c["reasons"])
        ]
        status = (
            "NOT_FOUND"
            if not candidates
            else ("BLOCKED" if len(exact) > 1 else exact[0]["status"] if exact else "MISMATCH")
        )
        results.append(
            {
                **product,
                "status": status,
                "candidate_count": len(candidates),
                "candidates": candidates[:3],
                "candidate_truncation": len(candidates) > 3,
                "ambiguous_exact_rows": len(exact) > 1,
                "image_rights_status": "OFFICIAL_FEED_ROUTE_ONLY_ASSET_LICENSE_AND_OWNER_REVIEW_REQUIRED",
                "image_publication_allowed": False,
                "offer_activation_allowed": False,
            }
        )
    return {
        "schema_version": 1,
        "advertiser_id": ADVERTISER,
        "feed_id": FEED,
        "publisher_id": PUBLISHER,
        "observed_at_utc": now.isoformat(),
        "source_metadata": metadata,
        "profiles": results,
        "source_timestamp_policy": "feed-list last_imported is preserved verbatim, never product freshness; naive row timestamps remain timezone-unknown",
        "raw_feed_exported": False,
        "image_bytes_downloaded": False,
        "affiliate_clicks": 0,
        "offer_activation_allowed": False,
        "image_publication_allowed": False,
    }


def encrypt_report(report: dict, recipient: bytes) -> bytes:
    ephemeral = X25519PrivateKey.generate()
    public = ephemeral.public_key().public_bytes_raw()
    salt, nonce = os.urandom(32), os.urandom(12)
    key = HKDF(
        algorithm=hashes.SHA256(), length=32, salt=salt, info=AAD + recipient + public
    ).derive(ephemeral.exchange(X25519PublicKey.from_public_bytes(recipient)))
    cipher = AESGCM(key).encrypt(nonce, json.dumps(report, ensure_ascii=False).encode(), AAD)
    return json.dumps(
        {
            "version": 1,
            "recipient_sha256": hashlib.sha256(recipient).hexdigest(),
            **{
                k: base64.b64encode(v).decode()
                for k, v in {
                    "ephemeral_public": public,
                    "salt": salt,
                    "nonce": nonce,
                    "ciphertext": cipher,
                }.items()
            },
        }
    ).encode()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--recipient", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    try:
        secret = os.environ.get("AWIN_DATA_FEED_API_KEY", "")
        if not secret:
            raise ValueError("awin_secret_not_configured")
        recipient = bytes.fromhex(args.recipient.read_text().strip())
        profiles = public_profiles(json.loads(CATALOG.read_text()))
        mappings = json.loads(MAPPINGS.read_text())
        with tempfile.TemporaryDirectory(
            prefix="dufynd-pt-", dir=os.environ.get("RUNNER_TEMP")
        ) as tmp:
            feed_path = Path(tmp) / "source.csv"
            metadata = download_feed_from_list(
                api_key=secret,
                advertiser_id=ADVERTISER,
                feed_id=FEED,
                output_path=feed_path,
                report_path=None,
                feed_max_bytes=64 * 1024 * 1024,
            )
            report = review_rows(
                profiles,
                mappings,
                read_merchant_feed_rows(feed_path, max_bytes=64 * 1024 * 1024),
                metadata,
                secret,
                datetime.now(UTC),
            )
        if contains_secret(json.dumps(report, ensure_ascii=False), secret):
            raise ValueError("secret_scan_rejected")
        encrypted = encrypt_report(report, recipient)
        with args.output.open("xb") as target:
            os.chmod(args.output, 0o600)
            target.write(encrypted)
    except Exception:
        # Feed/parser/network exceptions can contain sensitive source values.
        print("perfumetrader_private_review_failed_closed", file=sys.stderr)
        return 2
    print("perfumetrader_private_review_encrypted; no offers or images activated")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
