"""Five fixed candidates, official current acquisition, recipient-only evidence.

No arbitrary SKU/search inputs, no plaintext report and no activation semantics.
The existing downloader, PR776 identity guards and four-row crypto/filter are reused.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import sys
import tempfile
from collections import Counter
from datetime import UTC, datetime, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scripts.dufynd_feed_review_identity import VOLUME, feed_name_matches  # noqa: E402
from scripts.export_dufynd_awin_four_rows import (  # noqa: E402
    _contains_secret,
    encrypt_report,
    extract_evidence_fields,
    read_merchant_feed_rows,
)
from scripts.fetch_dufynd_awin_data_feed import download_feed_from_list  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
PROFILE = "merchant-review-v1"
RECIPIENT_SHA256 = "bcb22abbb93c9bbc1f4fd814da5d2b435c49e2d9d858c254bf5f63089e83ea4c"
TARGETS = (
    ("rabanne-100", "Rabanne", "1 Million", "Eau de Toilette", 100, "707368"),
    ("layton-125", "Parfums de Marly", "Layton", "Eau de Parfum", 125, "812773"),
    ("gris-charnel-100", "BDK Parfums", "Gris Charnel", "Eau de Parfum", 100, None),
    ("arabians-tonka-100", "Montale", "Arabians Tonka", "Eau de Parfum", 100, None),
    ("valaya-75", "Parfums de Marly", "Valaya", "Eau de Parfum", 75, None),
)
MANIFEST_SHA256 = hashlib.sha256(json.dumps(TARGETS).encode()).hexdigest()


def verify_source(metadata: dict, rights: dict, now: datetime) -> dict:
    checked = datetime.fromisoformat(str(metadata.get("checked_at", "")))
    if (
        checked.tzinfo is None
        or not timedelta(0) <= now - checked <= timedelta(hours=1)
        or metadata.get("source") != "awin_product_feed_list"
        or str(metadata.get("advertiser_id")) != "31081"
        or str(metadata.get("feed_id")) != "91379"
        or metadata.get("joined") is not True
        or metadata.get("downloaded") is not True
    ):
        raise ValueError("current_joined_feed_required")
    entries = [
        entry
        for entry in rights.get("entries", [])
        if entry.get("rights_basis_id") == "awin_top_parfuemerie_feed_materials_20260928"
        and entry.get("merchant_id") == "top-parfuemerie"
        and str(entry.get("advertiser_id")) == "31081"
        and entry.get("program_status") == "approved"
        and entry.get("rights_status") == "verified_for_publisher_service"
        and entry.get("asset_scope")
        == "unaltered_advertiser_materials_from_official_awin_product_feed"
    ]
    if rights.get("status") != "active" or len(entries) != 1:
        raise ValueError("rights_registry_required")
    return {
        "advertiser_id": "31081",
        "feed_id": "91379",
        "checked_at": checked.isoformat(),
        "last_imported": (
            metadata["last_imported"]
            if isinstance(metadata.get("last_imported"), str)
            and re.fullmatch(
                r"[0-9]{4}-[0-9]{2}-[0-9]{2}[ T][0-9: .+Z-]{5,24}", metadata["last_imported"]
            )
            else None
        ),
        "rights_basis_id": entries[0]["rights_basis_id"],
    }


def size_verified(target: dict, row: dict) -> bool:
    """Never derive volume or GTIN from image filenames or a default merchant page."""
    quantities = VOLUME.findall(str(row.get("product_name") or ""))
    for field in ("size", "product_size", "volume"):
        value = row.get(field)
        if value:
            if not isinstance(value, str) or not VOLUME.fullmatch(value.strip()):
                return False
            quantities.extend(VOLUME.findall(value))
    return bool(quantities) and all(
        float(q.replace(",", ".")) == target["volume_ml"] for q in quantities
    )


def build_review(rows: list[dict], metadata: dict, rights: dict, secret: str, *, now=None) -> dict:
    if not secret:
        raise ValueError("secret_scan_required")
    source = verify_source(metadata, rights, now or datetime.now(UTC))
    # Count all SKU rows before checking title, size or image safety (PR776 invariant).
    counts = Counter(str(row.get("merchant_product_id") or "").strip() for row in rows)
    results = []
    for key, brand, name, concentration, volume, sku in TARGETS:
        target = {
            "product_id": key,
            "brand": brand,
            "name": name,
            "concentration": concentration,
            "volume_ml": volume,
        }
        matches = [
            row
            for row in rows
            if (
                str(row.get("merchant_product_id") or "").strip() == sku
                if sku
                else feed_name_matches(target, row)
            )
        ]
        item = {
            **target,
            "requested_sku": sku,
            "status": "UNKNOWN",
            "absence_proven": False,
            "match_count": len(matches),
            "activation_allowed": False,
            "image_registration_allowed": False,
            "tracking_verified": False,
        }
        if len(matches) > 1:
            item["status"] = "HOLD_AMBIGUOUS"
        elif len(matches) == 1:
            row = matches[0]
            found_sku = str(row.get("merchant_product_id") or "").strip()
            if not re.fullmatch(r"[0-9]{5,20}", found_sku) or counts[found_sku] != 1:
                item["status"] = "HOLD_AMBIGUOUS_SKU"
            elif not feed_name_matches(target, row):
                item["status"] = "HOLD_IDENTITY_CONFLICT"
            else:
                item["status"] = (
                    "EXACT_VARIANT_REVIEW_REQUIRED"
                    if size_verified(target, row)
                    else "HOLD_SIZE_UNVERIFIED"
                )
                item["merchant_product_id"] = found_sku
                item["evidence"] = extract_evidence_fields(row, secret, allowed_skus=(found_sku,))
                # Retain only the bounded identity text actually accepted by the guards.
                item["identity_evidence"] = {
                    field: row[field]
                    for field in ("product_name", "size", "product_size", "volume")
                    if isinstance(row.get(field), str)
                    and len(row[field]) <= 200
                    and not _contains_secret(row[field], secret)
                    and (field == "product_name" or VOLUME.fullmatch(row[field].strip()))
                }
        results.append(item)
    report = {
        "version": 1,
        "profile": PROFILE,
        "manifest_sha256": MANIFEST_SHA256,
        "source": source,
        "feed_row_count": len(rows),
        "results": results,
        "activation_allowed": False,
        "tracking_verified": False,
        "rights_revalidation_required_before_registration": True,
    }
    if _contains_secret(json.dumps(report), secret):
        raise ValueError("secret_scan_rejected")
    return report


def atomic_encrypted_write(output: Path, payload: bytes) -> None:
    """Publish only a complete encrypted file, with no clobber on concurrent retries."""
    temp_path = None
    try:
        with tempfile.NamedTemporaryFile(
            dir=output.parent, prefix=".encrypted-", delete=False
        ) as handle:
            temp_path = Path(handle.name)
            os.chmod(temp_path, 0o600)
            handle.write(payload)
            handle.flush()
            os.fsync(handle.fileno())
        os.link(temp_path, output)
    finally:
        if temp_path is not None:
            temp_path.unlink(missing_ok=True)


def run_review(recipient_path: Path, output: Path) -> None:
    secret = os.environ.get("AWIN_DATA_FEED_API_KEY", "").strip()
    if not secret or output.exists():
        raise ValueError("secret_required_or_output_exists")
    recipient = bytes.fromhex(recipient_path.read_text().strip())
    if hashlib.sha256(recipient).hexdigest() != RECIPIENT_SHA256:
        raise ValueError("recipient_drift")
    rights = json.loads(
        (ROOT / "examples/retail/data/dufynd_affiliate_feed_image_rights.json").read_text()
    )
    with tempfile.TemporaryDirectory(prefix="dufynd-feed-review-") as work:
        feed = Path(work) / "source.csv"
        # Function API avoids the existing downloader CLI's feed-derived diagnostics.
        metadata = download_feed_from_list(
            api_key=secret,
            advertiser_id="31081",
            feed_id="91379",
            output_path=feed,
            report_path=None,
        )
        os.chmod(feed, 0o600)
        report = build_review(read_merchant_feed_rows(feed), metadata, rights, secret)
        report["source"]["feed_sha256"] = hashlib.sha256(feed.read_bytes()).hexdigest()
        if _contains_secret(json.dumps(report), secret):
            raise ValueError("secret_scan_rejected")
        # Hash and source are inside encryption too; never upload a raw-feed artifact.
        atomic_encrypted_write(output, encrypt_report(report, recipient))


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--recipient", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    try:
        run_review(args.recipient, args.output)
    except (Exception, KeyboardInterrupt):
        print("bounded_feed_review_failed_closed", file=sys.stderr)
        return 2
    print("bounded_feed_review_encrypted; no approvals or activation")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
